from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from app.core.logging import logger
from app.models.video import ExtractedFrame, OCRResult

class OCRService:
    """
    Local OCR processing service.
    Detects visible words, storefront text, signage, posters, and product labels on candidate frames.
    Integrates with EasyOCR / PyTesseract / OpenCV EAST text region detection.
    """

    def __init__(self):
        self._reader = None
        self._init_reader()

    def _init_reader(self):
        try:
            import easyocr
            # Attempt to initialize without forced model download
            try:
                self._reader = easyocr.Reader(['en'], gpu=False, verbose=False, download_enabled=False)
            except TypeError:
                self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("[OCRService] Initialized EasyOCR engine (CPU)")
        except Exception as e:
            logger.info(f"[OCRService] EasyOCR unavailable ({e}), using OpenCV morphological text candidate detector")
            self._reader = None

    def process_frame(self, frame_path: str, frame: ExtractedFrame) -> List[OCRResult]:
        """Perform OCR detection on a candidate frame."""
        path = Path(frame_path)
        if not path.exists():
            return []

        if self._reader:
            return self._process_with_easyocr(str(path), frame)
        return self._process_with_opencv_contours(str(path), frame)

    def _process_with_easyocr(self, img_path: str, frame: ExtractedFrame) -> List[OCRResult]:
        try:
            img = cv2.imread(img_path)
            if img is None:
                return []
            orig_h, orig_w = img.shape[:2]

            # Fast downscale if image is larger than 960px width for 2-3x inference speedup
            max_dim = 960
            if max(orig_h, orig_w) > max_dim:
                scale = max_dim / float(max(orig_h, orig_w))
                proc_img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
            else:
                proc_img = img

            results = self._reader.readtext(proc_img)
            ocr_results: List[OCRResult] = []
            h, w = proc_img.shape[:2]

            from app.services.clearance_filter import (
                RE_REFERENCE_PREFIX,
                RE_SLATE_CODE,
                PRODUCTION_ACRONYMS,
                LEGIT_SHORT_BRANDS,
            )

            for bbox, text, conf in results:
                clean_text = text.strip()
                if len(clean_text) < 2 or conf < 0.35:
                    continue

                lower_text = clean_text.lower()
                # Suppress camera/slate/reference prefixes and production acronyms
                if RE_REFERENCE_PREFIX.search(clean_text):
                    continue
                if lower_text in PRODUCTION_ACRONYMS:
                    continue

                # Suppress slate codes unless known short brand
                if lower_text not in LEGIT_SHORT_BRANDS:
                    tokens = clean_text.split()
                    if any(RE_SLATE_CODE.match(t) and sum(1 for c in t if c.isdigit()) >= 2 and sum(1 for c in t if c.isalpha()) >= 2 for t in tokens):
                        continue

                # Normalized bounding box [x, y, width, height]
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                min_x, max_x = max(0, min(xs)), min(w, max(xs))
                min_y, max_y = max(0, min(ys)), min(h, max(ys))

                norm_box = [
                    round(min_x / w, 4),
                    round(min_y / h, 4),
                    round((max_x - min_x) / w, 4),
                    round((max_y - min_y) / h, 4),
                ]

                # Brand-like heuristic (Title Case or uppercase brand, not numeric slate codes)
                is_brand = (clean_text.istitle() or (clean_text.isupper() and len(clean_text) <= 8)) and not any(c.isdigit() for c in clean_text)

                ocr_results.append(
                    OCRResult(
                        frame_id=frame.frame_id,
                        text=clean_text,
                        confidence=round(float(conf), 3),
                        bounding_box=norm_box,
                        bounding_boxes=[{
                            "x": norm_box[0],
                            "y": norm_box[1],
                            "width": norm_box[2],
                            "height": norm_box[3],
                        }],
                        timestamp=frame.video_timestamp,
                        is_brand_candidate=is_brand,
                    )
                )

            logger.debug(f"[OCRService] EasyOCR found {len(ocr_results)} text regions in frame {frame.frame_id}")
            return ocr_results
        except Exception as e:
            logger.warning(f"[OCRService] EasyOCR execution failed: {e}, falling back to OpenCV")
            return self._process_with_opencv_contours(img_path, frame)

    def _process_with_opencv_contours(self, img_path: str, frame: ExtractedFrame) -> List[OCRResult]:
        """
        Morphological text region and edge density detector.
        Extracts high-contrast rectangular candidate regions (signs, logos, labels).
        """
        try:
            img = cv2.imread(img_path)
            if img is None:
                return []

            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, -1)
            grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, -1)
            gradient = cv2.subtract(grad_x, grad_y)
            gradient = cv2.convertScaleAbs(gradient)

            blurred = cv2.blur(gradient, (9, 9))
            _, thresh = cv2.threshold(blurred, 180, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 9))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            closed = cv2.erode(closed, None, iterations=4)
            closed = cv2.dilate(closed, None, iterations=4)

            contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            candidates: List[OCRResult] = []
            for c in contours:
                x, y, cw, ch = cv2.boundingRect(c)
                aspect_ratio = cw / float(ch) if ch > 0 else 0
                area = cw * ch
                if 1.2 <= aspect_ratio <= 8.0 and area > (w * h * 0.005):
                    norm_box = [
                        round(x / w, 4),
                        round(y / h, 4),
                        round(cw / w, 4),
                        round(ch / h, 4),
                    ]
                    candidates.append(
                        OCRResult(
                            text="SIGNAGE_TEXT_CANDIDATE",
                            confidence=0.75,
                            bounding_box=norm_box,
                            frame_id=frame.frame_id,
                            timestamp=frame.video_timestamp,
                            is_brand_candidate=True,
                        )
                    )

            return candidates[:8]
        except Exception as e:
            logger.error(f"[OCRService] OpenCV contour text detector error: {e}")
            return []

ocr_service = OCRService()
