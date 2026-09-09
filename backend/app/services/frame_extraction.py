import asyncio
from pathlib import Path
from typing import List, Optional
import cv2
from app.core.config import settings
from app.core.logging import logger
from app.models.video import ExtractedFrame, Scene, VideoMetadata
from app.services.storage import storage_service

class FrameExtractionService:
    """
    Candidate frame extraction service.
    Extracts representative frames around the start, middle, and end of each detected scene,
    and saves them through StorageService.
    """

    def __init__(self, frames_per_scene: Optional[int] = None):
        self.frames_per_scene = frames_per_scene or settings.FRAMES_PER_SCENE
        logger.info(f"[FrameExtractionService] Initialized (frames_per_scene={self.frames_per_scene})")

    async def extract_scene_frames(
        self,
        video_path: str,
        scenes: List[Scene],
        production_id: str,
        job_id: str,
        metadata: Optional[VideoMetadata] = None,
    ) -> List[ExtractedFrame]:
        """Extract candidate frames for all scenes in video."""
        path = Path(video_path)
        if not path.exists():
            logger.warning(f"[FrameExtractionService] Video file not found: {video_path}")
            return []

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            logger.warning(f"[FrameExtractionService] Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        extracted_frames: List[ExtractedFrame] = []

        for scene in scenes:
            scene_frames = await self._extract_for_single_scene(
                cap=cap,
                scene=scene,
                production_id=production_id,
                job_id=job_id,
                fps=fps,
                width=width,
                height=height,
            )
            extracted_frames.extend(scene_frames)
            scene.representative_frames = [f.local_path for f in scene_frames]

        cap.release()
        logger.info(f"[FrameExtractionService] Extracted {len(extracted_frames)} total candidate frames across {len(scenes)} scenes")
        return extracted_frames

    async def _extract_for_single_scene(
        self,
        cap: cv2.VideoCapture,
        scene: Scene,
        production_id: str,
        job_id: str,
        fps: float,
        width: int,
        height: int,
    ) -> List[ExtractedFrame]:
        """Calculate timestamps for start, middle, end of scene and extract images."""
        dur = scene.duration
        s_time = scene.start_time

        # Calculate sample positions
        timestamps = []
        if self.frames_per_scene <= 1:
            timestamps.append((s_time + dur / 2.0, "middle"))
        elif self.frames_per_scene == 2:
            timestamps.append((s_time + 0.1 * dur, "start"))
            timestamps.append((s_time + 0.9 * dur, "end"))
        else:
            # 3 frames: start, middle, end
            timestamps.append((s_time + max(0.1, 0.15 * dur), "start"))
            timestamps.append((s_time + 0.5 * dur, "middle"))
            timestamps.append((s_time + min(dur - 0.1, 0.85 * dur), "end"))

            # If additional frames requested
            for extra_i in range(3, self.frames_per_scene):
                fraction = (extra_i - 2) / (self.frames_per_scene - 1)
                timestamps.append((s_time + fraction * dur, f"sample_{extra_i}"))

        results: List[ExtractedFrame] = []
        for ts, pos in timestamps:
            frame_number = int(ts * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Encode as JPEG
            success, encoded_img = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not success:
                continue

            # Save frame via StorageService
            rel_path = f"frames/{production_id}/{job_id}/scene{scene.scene_number:02d}_{int(ts*10):05d}.jpg"
            saved_uri = await storage_service.save_file(rel_path, encoded_img.tobytes())

            extracted_frame = ExtractedFrame(
                scene_id=scene.scene_id,
                scene_number=scene.scene_number,
                frame_number=frame_number,
                video_timestamp=round(ts, 2),
                frame_path=saved_uri,
                local_path=saved_uri,
                width=width,
                height=height,
                position_in_scene=pos,
            )
            results.append(extracted_frame)

        return results

frame_extraction_service = FrameExtractionService()
