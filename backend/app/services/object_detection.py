from pathlib import Path
from typing import List, Optional
import cv2
from app.core.config import settings
from app.core.logging import logger
from app.models.video import ExtractedFrame, ObjectDetection, ObjectDetectionResult

class ObjectDetectionService:
    """
    Local object detection stage.
    Identifies candidate clearance objects (cup, bottle, phone, laptop, car, book, poster, sign, person).
    Integrates with Ultralytics YOLO or OpenCV DNN.
    """

    TARGET_CLASSES = {
        "person", "bottle", "cup", "cell phone", "laptop", "car",
        "book", "clock", "tv", "chair", "couch", "backpack",
        "handbag", "suitcase", "traffic light", "stop sign", "poster", "sign"
    }

    def __init__(self, confidence_threshold: Optional[float] = None):
        self.threshold = confidence_threshold or getattr(settings, "YOLO_CONFIDENCE_THRESHOLD", 0.45)
        self._model = None
        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            # Lightweight YOLOv8 nano model from workspace or local dir
            weights_paths = [
                Path("yolov8n.pt"),
                Path(__file__).resolve().parent.parent.parent / "yolov8n.pt",
                Path(__file__).resolve().parent.parent.parent.parent / "yolov8n.pt",
            ]
            weights_file = next((p for p in weights_paths if p.exists()), Path("yolov8n.pt"))
            self._model = YOLO(str(weights_file))
            logger.info(f"[ObjectDetectionService] Initialized Ultralytics YOLOv8n detector from {weights_file}")
        except Exception as e:
            logger.info(f"[ObjectDetectionService] YOLO not loaded ({e}), using OpenCV cascade fallback")
            self._model = None

    def detect_objects(self, frame_path: str, frame: ExtractedFrame) -> List[ObjectDetection]:
        """Run candidate object detection on frame."""
        path = Path(frame_path)
        if not path.exists():
            return []

        if self._model:
            return self._detect_with_yolo(str(path), frame)
        return self._detect_with_opencv_fallback(str(path), frame)

    def _detect_with_yolo(self, img_path: str, frame: ExtractedFrame) -> List[ObjectDetection]:
        try:
            results = self._model(img_path, conf=self.threshold, verbose=False)
            detections: List[ObjectDetection] = []

            img = cv2.imread(img_path)
            h, w = img.shape[:2] if img is not None else (frame.height, frame.width)

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    cls_name = r.names.get(cls_id, f"obj_{cls_id}").lower()
                    conf = float(box.conf[0])

                    if conf < self.threshold:
                        continue

                    # Bounding box xyxy format
                    raw_box = box.xyxy[0]
                    xyxy = raw_box.tolist() if hasattr(raw_box, "tolist") else list(raw_box)
                    norm_box = [
                        round(xyxy[0] / w, 4),
                        round(xyxy[1] / h, 4),
                        round((xyxy[2] - xyxy[0]) / w, 4),
                        round((xyxy[3] - xyxy[1]) / h, 4),
                    ]

                    detections.append(
                        ObjectDetection(
                            frame_id=frame.frame_id,
                            label=cls_name,
                            class_name=cls_name,
                            confidence=round(conf, 3),
                            bbox=norm_box,
                            bounding_box=norm_box,
                            timestamp=frame.video_timestamp,
                        )
                    )

            logger.debug(f"[ObjectDetectionService] YOLO found {len(detections)} candidate objects in {frame.frame_id}")
            return detections
        except Exception as e:
            logger.warning(f"[ObjectDetectionService] YOLO error ({e}), falling back to OpenCV")
            return self._detect_with_opencv_fallback(img_path, frame)

    def _detect_with_opencv_fallback(self, img_path: str, frame: ExtractedFrame) -> List[ObjectDetectionResult]:
        """OpenCV contour based candidate object detection fallback."""
        try:
            img = cv2.imread(img_path)
            if img is None:
                return []

            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            detections: List[ObjectDetectionResult] = []
            for c in contours:
                area = cv2.contourArea(c)
                if area > (w * h * 0.02):
                    x, y, cw, ch = cv2.boundingRect(c)
                    detections.append(
                        ObjectDetectionResult(
                            class_name="candidate_product",
                            confidence=0.70,
                            bounding_box=[
                                round(x / w, 4),
                                round(y / h, 4),
                                round(cw / w, 4),
                                round(ch / h, 4),
                            ],
                            frame_id=frame.frame_id,
                            timestamp=frame.video_timestamp,
                        )
                    )
                    if len(detections) >= 4:
                        break

            return detections
        except Exception as e:
            logger.error(f"[ObjectDetectionService] OpenCV fallback error: {e}")
            return []

object_detection_service = ObjectDetectionService()
