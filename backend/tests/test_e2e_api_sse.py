import asyncio
import cv2
import numpy as np
import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.analysis import JobStatus
from app.models.events import EventType
from app.services.vision_provider import LocalHeuristicVisionProvider

def create_synthetic_mp4(path: str, duration_sec: int = 2, fps: int = 24):
    width, height = 640, 360
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    total = duration_sec * fps
    half = total // 2
    for f in range(total):
        if f < half:
            img = np.full((height, width, 3), (120, 60, 20), dtype=np.uint8)
            cv2.putText(img, "STARLIGHT COFFEE", (60, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.rectangle(img, (350, 100), (450, 250), (200, 200, 200), -1)
        else:
            img = np.full((height, width, 3), (20, 100, 40), dtype=np.uint8)
            cv2.putText(img, "APEX PHONE", (80, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            cv2.circle(img, (400, 180), 50, (0, 200, 255), -1)
        out.write(img)
    out.release()
    return path

@pytest.mark.asyncio
@patch("app.agents.visual_agent.get_vision_provider", return_value=LocalHeuristicVisionProvider())
async def test_e2e_api_lifecycle_and_sse_events(mock_prov, tmp_path):
    video_file = str(tmp_path / "e2e_clip.mp4")
    create_synthetic_mp4(video_file, duration_sec=2, fps=24)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        h_res = await client.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["status"] == "HEALTHY"

        # 2. Create production
        p_res = await client.post("/productions", json={
            "title": "E2E Automated Test Film",
            "description": "Validating real video pipeline API",
            "director": "Director Test",
            "studio": "Chain of Title Studios",
            "budget_tier": "Studio Feature"
        })
        assert p_res.status_code == 201
        prod_data = p_res.json()
        prod_id = prod_data["id"]

        # 3. Upload screenplay text (mentions APEX PHONE, omits STARLIGHT COFFEE)
        s_res = await client.post(
            f"/productions/{prod_id}/script",
            data={"script_text": "SCENE 1: Character checks their Apex Phone on the table."}
        )
        assert s_res.status_code == 200

        # 4. Upload footage override
        f_res = await client.post(
            f"/productions/{prod_id}/footage",
            data={"footage_path_override": video_file}
        )
        assert f_res.status_code == 200

        # 5. Start Analysis
        a_res = await client.post(f"/productions/{prod_id}/analyze")
        assert a_res.status_code == 202
        job_data = a_res.json()
        job_id = job_data["job_id"]

        # 6. Listen to SSE stream for live events
        received_event_types = []
        visual_only_found = False

        async with client.stream("GET", f"/productions/{prod_id}/analysis/{job_id}/events") as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    ev_type = line[len("event: "):].strip()
                    received_event_types.append(ev_type)
                    if ev_type == "VISUAL_ONLY_DISCOVERED":
                        visual_only_found = True
                    if ev_type in ("ANALYSIS_COMPLETED", "ANALYSIS_FAILED"):
                        break

        # Verify essential events were captured
        assert EventType.ANALYSIS_STARTED.value in received_event_types
        assert EventType.SCENE_DETECTED.value in received_event_types
        assert EventType.FRAME_EXTRACTED.value in received_event_types
        assert EventType.OCR_COMPLETED.value in received_event_types
        assert EventType.FRAME_SELECTED_FOR_VISION.value in received_event_types
        assert EventType.VISION_ANALYSIS_COMPLETED.value in received_event_types
        assert EventType.ENTITY_DETECTED.value in received_event_types
        assert EventType.ANALYSIS_COMPLETED.value in received_event_types
        assert visual_only_found is True

        # 7. Check finalized entities endpoint
        e_res = await client.get(f"/productions/{prod_id}/entities")
        assert e_res.status_code == 200
        entities = e_res.json()
        assert len(entities) >= 1

        # Check visual-only entity classification
        visual_only_entities = [e for e in entities if e["classification"] == "VISUAL_ONLY"]
        assert len(visual_only_entities) >= 1
        assert any("STARLIGHT" in e["name"].upper() for e in visual_only_entities)

        # Check evidence frames
        ev_res = await client.get(f"/productions/{prod_id}/evidence")
        assert ev_res.status_code == 200
        evidence_list = ev_res.json()
        assert len(evidence_list) >= 1
