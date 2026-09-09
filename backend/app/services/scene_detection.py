from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from app.core.logging import logger
from app.models.video import Scene, VideoMetadata

class SceneDetectionService:
    """
    Scene boundary detection service using PySceneDetect with adaptive OpenCV histogram difference fallback.
    Detects scene transitions and cuts rather than processing every raw frame.
    """

    def __init__(self, threshold: float = 27.0, min_scene_len_sec: float = 0.8):
        self.threshold = threshold
        self.min_scene_len_sec = min_scene_len_sec
        logger.info("[SceneDetectionService] Initialized scene detection service")

    def detect_scenes(
        self,
        video_path: str,
        production_id: str,
        job_id: str,
        metadata: Optional[VideoMetadata] = None,
    ) -> List[Scene]:
        """Detect scene boundaries in video file."""
        path = Path(video_path)
        if not path.exists():
            logger.warning(f"[SceneDetectionService] Video path does not exist: {video_path}")
            return []

        scenes = self._detect_with_scenedetect(str(path), production_id, job_id)
        if not scenes:
            logger.info("[SceneDetectionService] Using adaptive OpenCV frame-difference scene detector")
            scenes = self._detect_with_opencv(str(path), production_id, job_id, metadata)

        # Ensure at least one scene exists if video has duration
        if not scenes:
            duration = metadata.duration_seconds if metadata else 10.0
            scenes.append(
                Scene(
                    production_id=production_id,
                    job_id=job_id,
                    scene_number=1,
                    start_time=0.0,
                    end_time=duration,
                    duration=duration,
                )
            )

        logger.info(f"[SceneDetectionService] Detected {len(scenes)} scenes in {video_path}")
        return scenes

    def _detect_with_scenedetect(self, video_path: str, production_id: str, job_id: str) -> List[Scene]:
        """Attempt scene detection using scenedetect package."""
        try:
            from scenedetect import open_video, SceneManager, ContentDetector

            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self.threshold))
            scene_manager.detect_scenes(video)
            scene_list = scene_manager.get_scene_list()

            scenes: List[Scene] = []
            for idx, (start_time, end_time) in enumerate(scene_list, 1):
                s_sec = round(getattr(start_time, "seconds", None) if getattr(start_time, "seconds", None) is not None else start_time.get_seconds(), 2)
                e_sec = round(getattr(end_time, "seconds", None) if getattr(end_time, "seconds", None) is not None else end_time.get_seconds(), 2)
                dur = round(e_sec - s_sec, 2)
                s_frame = getattr(start_time, "frame_num", None)
                if s_frame is None:
                    s_frame = start_time.get_frames() if hasattr(start_time, "get_frames") else 0
                e_frame = getattr(end_time, "frame_num", None)
                if e_frame is None:
                    e_frame = end_time.get_frames() if hasattr(end_time, "get_frames") else 0

                scenes.append(
                    Scene(
                        production_id=production_id,
                        job_id=job_id,
                        scene_number=idx,
                        start_time=s_sec,
                        end_time=e_sec,
                        duration_seconds=dur,
                        duration=dur,
                        start_frame=int(s_frame),
                        end_frame=int(e_frame),
                    )
                )
            return scenes
        except Exception as e:
            logger.debug(f"[SceneDetectionService] scenedetect detection unavailable or failed: {e}")
            return []

    def _detect_with_opencv(
        self,
        video_path: str,
        production_id: str,
        job_id: str,
        metadata: Optional[VideoMetadata] = None,
    ) -> List[Scene]:
        """Adaptive frame-difference scene cut detector using OpenCV HSV color histograms."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or (metadata.fps if metadata else 24.0)
        if fps <= 0:
            fps = 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or (metadata.frame_count if metadata else 0)
        min_frames = int(fps * self.min_scene_len_sec)

        cut_timestamps = [0.0]
        cut_frames = [0]
        prev_hist = None
        frame_idx = 0
        step = max(1, int(fps / 4))  # sample 4 times per second for speed

        while cap.isOpened():
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            # Calculate HSV histogram
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

            if prev_hist is not None:
                # Chi-Square or Correlation difference
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                curr_time = round(frame_idx / fps, 2)

                # High difference indicates camera cut
                if diff > 15.0 and (frame_idx - cut_frames[-1]) >= min_frames:
                    cut_timestamps.append(curr_time)
                    cut_frames.append(frame_idx)
                    logger.debug(f"[SceneDetectionService] Cut detected at {curr_time}s (frame {frame_idx}, diff: {diff:.2f})")

            prev_hist = hist
            frame_idx += step
            if frame_idx >= total_frames:
                break

        cap.release()

        total_duration = round(total_frames / fps, 2) if total_frames > 0 else (metadata.duration_seconds if metadata else 10.0)
        if total_duration > cut_timestamps[-1]:
            cut_timestamps.append(total_duration)
            cut_frames.append(total_frames)

        scenes: List[Scene] = []
        for i in range(len(cut_timestamps) - 1):
            s_time = cut_timestamps[i]
            e_time = cut_timestamps[i + 1]
            dur = round(e_time - s_time, 2)
            s_frame = cut_frames[i] if i < len(cut_frames) else int(s_time * fps)
            e_frame = cut_frames[i + 1] if (i + 1) < len(cut_frames) else int(e_time * fps)
            if dur > 0.1:
                scenes.append(
                    Scene(
                        production_id=production_id,
                        job_id=job_id,
                        scene_number=len(scenes) + 1,
                        start_time=s_time,
                        end_time=e_time,
                        duration_seconds=dur,
                        duration=dur,
                        start_frame=s_frame,
                        end_frame=e_frame,
                    )
                )

        return scenes

scene_detection_service = SceneDetectionService()
