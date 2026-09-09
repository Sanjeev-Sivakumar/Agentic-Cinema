import os
from pathlib import Path
from typing import Any, Dict, Optional
import cv2
from app.core.config import settings
from app.core.logging import logger
from app.models.video import VideoMetadata

class VideoReadError(ValueError):
    """Raised when video file cannot be opened or parsed."""
    pass

class VideoDurationLimitExceededError(ValueError):
    """Raised when video exceeds configured maximum duration for cost control."""
    pass

class VideoService:
    """
    Core Video Ingestion service using OpenCV / FFmpeg.
    Extracts filename, duration, FPS, resolution, frame counts, and container codecs.
    Validates file existence, readability, FPS > 0, frame_count > 0, duration > 0.
    """

    def __init__(self, max_duration_seconds: Optional[int] = None):
        self.max_duration_seconds = max_duration_seconds or getattr(settings, "MAX_VIDEO_DURATION_SECONDS", 300)
        logger.info(f"[VideoService] Initialized real VideoService with OpenCV backend (max_duration={self.max_duration_seconds}s)")

    def inspect_video(self, video_path: str) -> VideoMetadata:
        """Inspect and parse real video file metadata with strict validation."""
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: '{video_path}'")

        if not path.is_file():
            raise VideoReadError(f"Specified path is not a file: '{video_path}'")

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise VideoReadError(f"Failed to open video capture for: '{video_path}' (corrupt or unsupported format)")

        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fourcc_val = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)

            # Decode FOURCC codec identifier
            codec = "mp4v"
            if fourcc_val > 0:
                codec_chars = [chr((fourcc_val >> 8 * i) & 0xFF) for i in range(4)]
                codec = "".join(codec_chars).strip()

            duration = round(total_frames / fps, 2) if fps > 0 else 0.0

            # Validate extraction
            if fps <= 0:
                raise VideoReadError(f"Invalid video FPS: {fps}. Video must have FPS > 0.")
            if total_frames <= 0:
                raise VideoReadError(f"Invalid video frame count: {total_frames}. Video must have frame_count > 0.")
            if duration <= 0:
                raise VideoReadError(f"Invalid video duration: {duration}s. Video must have duration > 0.")

            # Cost Control: Safety limit check
            if duration > self.max_duration_seconds:
                raise VideoDurationLimitExceededError(
                    f"Video duration ({duration}s) exceeds safety limit of {self.max_duration_seconds}s. "
                    "Analysis halted for cost control."
                )

            metadata = VideoMetadata(
                filename=path.name,
                file_path=str(path.resolve()),
                duration_seconds=duration,
                fps=round(fps, 2),
                width=width,
                height=height,
                frame_count=total_frames,
                codec=codec or "mp4v",
            )
            logger.info(f"[VideoService] Inspected video '{path.name}': {width}x{height} @ {fps}fps, {duration}s ({total_frames} frames, codec: {codec})")
            return metadata

        finally:
            cap.release()

video_service = VideoService()
