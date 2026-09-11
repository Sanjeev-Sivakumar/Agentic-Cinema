import asyncio
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app

def test_all_three_ingestion_modes():
    print("=" * 80)
    print("   CHAIN OF TITLE — 3-MODE INGESTION & PIPELINE VERIFICATION SUITE")
    print("=" * 80)

    client = TestClient(app)

    # -------------------------------------------------------------------------
    # TEST 1: SCREENPLAY ONLY MODE
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing SCREENPLAY ONLY Mode (Pre-Production Clearance)...")
    r_prod1 = client.post("/productions", json={
        "title": "Script Only Clearance Test",
        "description": "Pre-production screenplay clearance evaluation",
        "budget_tier": "Studio Feature"
    })
    assert r_prod1.status_code == 201
    prod1_id = r_prod1.json()["id"]

    script_text1 = (
        "SCENE 1 - INT. CAFE - DAY\n"
        "Alex orders a Starbucks latte and checks his Apple Watch.\n"
        "On the counter sits a can of Red Bull and a copy of The New York Times."
    )
    r_s1 = client.post(f"/productions/{prod1_id}/script", data={"script_text": script_text1})
    assert r_s1.status_code == 200
    print(f"  • Screenplay registered for {prod1_id}")

    r_orch1 = client.post(f"/productions/{prod1_id}/orchestrate", json={
        "mode": "offline",
        "force_refresh": True,
        "research_provider": "local"
    })
    assert r_orch1.status_code == 200, f"Script only orchestration failed: {r_orch1.text}"
    orch1 = r_orch1.json()
    assert orch1["status"] in ("COMPLETED", "PARTIAL")
    print(f"  • Orchestration finished with status: {orch1['status']} in {orch1['duration']}s")
    print(f"  • Completed Agents: {orch1['completed_agents']}")
    print(f"  • Skipped Agents: {orch1['skipped_agents']}")
    assert "screenplay" in orch1["completed_agents"]
    assert "visual" in orch1["skipped_agents"]

    r_ent1 = client.get(f"/productions/{prod1_id}/entities")
    entities1 = r_ent1.json()
    assert len(entities1) >= 2, f"Expected detected entities in script, got {len(entities1)}"
    print(f"  • Entities Detected ({len(entities1)}): {[e['name'] for e in entities1]}")

    # -------------------------------------------------------------------------
    # TEST 2: VIDEO REEL ONLY MODE
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing VIDEO REEL ONLY Mode (Visual-Only Detection & Triage)...")
    r_prod2 = client.post("/productions", json={
        "title": "Video Only Clearance Test",
        "description": "Footage post-production triage evaluation",
        "budget_tier": "Studio Feature"
    })
    assert r_prod2.status_code == 201
    prod2_id = r_prod2.json()["id"]

    video_path = Path(__file__).resolve().parent.parent / "test_video1.mp4"
    if video_path.exists():
        with open(video_path, "rb") as f:
            r_v2 = client.post(f"/productions/{prod2_id}/footage", files={"file": ("test_video1.mp4", f, "video/mp4")})
    else:
        r_v2 = client.post(f"/productions/{prod2_id}/footage", data={"footage_path_override": "test_video1.mp4"})
    assert r_v2.status_code == 200
    print(f"  • Video footage registered for {prod2_id}")

    r_orch2 = client.post(f"/productions/{prod2_id}/orchestrate", json={
        "mode": "offline",
        "force_refresh": True,
        "research_provider": "local"
    })
    assert r_orch2.status_code == 200, f"Video only orchestration failed: {r_orch2.text}"
    orch2 = r_orch2.json()
    assert orch2["status"] in ("COMPLETED", "PARTIAL")
    print(f"  • Orchestration finished with status: {orch2['status']} in {orch2['duration']}s")
    print(f"  • Completed Agents: {orch2['completed_agents']}")
    print(f"  • Skipped Agents: {orch2['skipped_agents']}")
    assert "visual" in orch2["completed_agents"]
    assert "screenplay" in orch2["skipped_agents"]

    r_ent2 = client.get(f"/productions/{prod2_id}/entities")
    entities2 = r_ent2.json()
    print(f"  • Entities Detected ({len(entities2)}): {[e['name'] for e in entities2]}")
    for e in entities2:
        sources = e.get("sources", [])
        assert "VISUAL" in sources or e.get("classification") == "VISUAL_ONLY", f"Expected visual entity, got {sources}"

    # -------------------------------------------------------------------------
    # TEST 3: MULTIMODAL (BOTH SCRIPT + VIDEO) MODE
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing MULTIMODAL Mode (Both Screenplay + Video Reel Discrepancy)...")
    r_prod3 = client.post("/productions", json={
        "title": "Multimodal Clearance Benchmark",
        "description": "Full cross-modal discrepancy and liability evaluation",
        "budget_tier": "Studio Feature"
    })
    assert r_prod3.status_code == 201
    prod3_id = r_prod3.json()["id"]

    script_text3 = (
        "SCENE 1 - INT. TECH LAB - DAY\n"
        "Sarah tests Sony camera and drinks Coca-Cola."
    )
    r_s3 = client.post(f"/productions/{prod3_id}/script", data={"script_text": script_text3})
    assert r_s3.status_code == 200

    if video_path.exists():
        with open(video_path, "rb") as f:
            r_v3 = client.post(f"/productions/{prod3_id}/footage", files={"file": ("test_video1.mp4", f, "video/mp4")})
    else:
        r_v3 = client.post(f"/productions/{prod3_id}/footage", data={"footage_path_override": "test_video1.mp4"})
    assert r_v3.status_code == 200

    r_orch3 = client.post(f"/productions/{prod3_id}/orchestrate", json={
        "mode": "offline",
        "force_refresh": True,
        "research_provider": "local"
    })
    assert r_orch3.status_code == 200, f"Multimodal orchestration failed: {r_orch3.text}"
    orch3 = r_orch3.json()
    assert orch3["status"] in ("COMPLETED", "PARTIAL")
    print(f"  • Orchestration finished with status: {orch3['status']} in {orch3['duration']}s")
    print(f"  • Completed Agents: {orch3['completed_agents']}")
    assert "screenplay" in orch3["completed_agents"]
    assert "visual" in orch3["completed_agents"]

    r_ent3 = client.get(f"/productions/{prod3_id}/entities")
    entities3 = r_ent3.json()
    print(f"  • Entities Detected ({len(entities3)}):")
    for e in entities3:
        sources = e.get("sources", [])
        is_vis = ("VISUAL" in sources and "SCRIPT" not in sources) or e.get("classification") == "VISUAL_ONLY"
        vis_tag = "🚨 VISUAL_ONLY" if is_vis else "SCRIPT/BOTH"
        print(f"    - {e['name']} [{e['entity_type']}] | Risk: {e['risk_score']}/100 | Tag: {vis_tag}")

    # Check Exposure, Outreach, Remediation, Report
    r_exp = client.get(f"/exposure/{prod3_id}")
    assert r_exp.status_code == 200
    r_out = client.get(f"/outreach/{prod3_id}")
    assert r_out.status_code == 200
    r_rem = client.get(f"/remediations/{prod3_id}")
    assert r_rem.status_code == 200
    r_rep = client.get(f"/productions/{prod3_id}/report/html")
    assert r_rep.status_code == 200
    print(f"  • HTML Report generated: {len(r_rep.text)} bytes")

    print("\n" + "=" * 80)
    print("   ALL 3 INGESTION MODES (SCRIPT, VIDEO, BOTH) PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    test_all_three_ingestion_modes()
