from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator

class VideoMetadata(BaseModel):
    video_id: str = Field(default_factory=lambda: f"vid_{uuid.uuid4().hex[:10]}")
    filename: str = ""
    file_path: str = ""
    duration_seconds: float = 0.0
    fps: float = 24.0
    width: int = 1920
    height: int = 1080
    frame_count: int = 0
    codec: Optional[str] = "mp4v"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_file_paths(cls, data: Any) -> Any:
        if isinstance(data, dict):
            fn = data.get("filename") or data.get("file_path") or ""
            data["filename"] = fn
            data["file_path"] = data.get("file_path") or fn
        return data


class Scene(BaseModel):
    scene_id: str = Field(default_factory=lambda: f"scn_{uuid.uuid4().hex[:10]}")
    production_id: str = ""
    job_id: str = ""
    scene_number: int = 1
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0
    duration: float = 0.0
    start_frame: int = 0
    end_frame: int = 0
    representative_frames: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_duration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            dur = data.get("duration_seconds")
            if dur is None:
                dur = data.get("duration")
            if dur is None and "start_time" in data and "end_time" in data:
                dur = round(float(data["end_time"]) - float(data["start_time"]), 2)
            dur_val = float(dur or 0.0)
            data["duration_seconds"] = dur_val
            data["duration"] = dur_val
        return data


class ExtractedFrame(BaseModel):
    frame_id: str = Field(default_factory=lambda: f"frm_{uuid.uuid4().hex[:10]}")
    scene_id: str = ""
    scene_number: int = 1
    frame_number: int = 0
    video_timestamp: float = 0.0
    frame_path: str = ""
    local_path: str = ""
    width: int = 1920
    height: int = 1080
    position_in_scene: str = "middle"  # "start", "middle", "end", "sample"

    @model_validator(mode="before")
    @classmethod
    def sync_paths(cls, data: Any) -> Any:
        if isinstance(data, dict):
            p = data.get("frame_path") or data.get("local_path") or ""
            data["frame_path"] = p
            data["local_path"] = data.get("local_path") or p
        return data


class OCRResult(BaseModel):
    frame_id: str
    text: str
    confidence: float
    bounding_boxes: List[Dict[str, Any]] = Field(default_factory=list)
    bounding_box: List[float] = Field(default_factory=list)  # [x, y, w, h] normalized
    timestamp: float = 0.0
    is_brand_candidate: bool = False

    @model_validator(mode="before")
    @classmethod
    def sync_boxes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            bb = data.get("bounding_box", [])
            bbs = data.get("bounding_boxes", [])
            if bb and not bbs:
                # convert [x, y, w, h] to dict
                if len(bb) >= 4:
                    data["bounding_boxes"] = [{"x": bb[0], "y": bb[1], "width": bb[2], "height": bb[3]}]
            elif bbs and not bb:
                b0 = bbs[0]
                if isinstance(b0, dict) and "x" in b0 and "y" in b0:
                    data["bounding_box"] = [b0.get("x", 0.0), b0.get("y", 0.0), b0.get("width", 0.0), b0.get("height", 0.0)]
        return data


class ObjectDetection(BaseModel):
    frame_id: str
    label: str = ""
    class_name: str = ""
    confidence: float = 0.0
    bbox: List[float] = Field(default_factory=list)  # [x, y, w, h] normalized
    bounding_box: List[float] = Field(default_factory=list)  # [x, y, w, h] normalized
    timestamp: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def sync_labels_and_boxes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            lbl = data.get("label") or data.get("class_name") or "object"
            data["label"] = lbl
            data["class_name"] = data.get("class_name") or lbl
            b = data.get("bbox") or data.get("bounding_box") or []
            data["bbox"] = b
            data["bounding_box"] = data.get("bounding_box") or b
        return data

# Backwards compatibility alias
ObjectDetectionResult = ObjectDetection


class RankedFrame(BaseModel):
    frame_id: str
    scene_number: int = 1
    video_timestamp: float = 0.0
    frame_path: str = ""
    score: float = 0.0
    ranking_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    ranking_reasons: List[str] = Field(default_factory=list)
    ocr_count: int = 0
    object_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def sync_scores(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sc = data.get("score") if data.get("score") is not None else data.get("ranking_score", 0.0)
            data["score"] = float(sc)
            data["ranking_score"] = float(sc)
            rs = data.get("reasons") or data.get("ranking_reasons") or []
            data["reasons"] = rs
            data["ranking_reasons"] = data.get("ranking_reasons") or rs
        return data

# Backwards compatibility alias
FrameRanking = RankedFrame

