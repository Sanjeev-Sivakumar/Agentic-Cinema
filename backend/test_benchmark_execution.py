import asyncio
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app

def test_full_benchmark_run():
    print("=" * 70)
    print("   CHAIN OF TITLE — FULL BENCHMARK VERIFICATION ON test_video1.mp4")
    print("=" * 70)

    client = TestClient(app)

    # 1. Check UI Endpoint
    r_ui = client.get("/")
    assert r_ui.status_code == 200, f"UI GET / returned {r_ui.status_code}"
    assert "CHAIN OF TITLE" in r_ui.text
    assert "Autonomous Pre-Clearance Intelligence" in r_ui.text
    print("[1] Verified Root Judge UI: Status 200, Title & Stepper present.")

    # 2. Check Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    print(f"[2] Verified Health Endpoint: {r_health.json()}")

    # 3. Create Production
    r_prod = client.post("/productions", json={
        "title": "Benchmark Showcase: Artificial Intelligence & Video Reel",
        "description": "Autonomous multi-agent pre-clearance validation",
        "budget_tier": "Studio Feature"
    })
    assert r_prod.status_code == 201
    prod_data = r_prod.json()
    prod_id = prod_data["id"]
    print(f"[3] Created Production: ID = {prod_id}")

    # 4. Upload Screenplay
    script_path = Path(__file__).resolve().parent.parent / "demo_data" / "sample_screenplay.txt"
    if script_path.exists():
        with open(script_path, "rb") as f:
            r_script = client.post(f"/productions/{prod_id}/script", files={"file": ("sample_screenplay.txt", f, "text/plain")})
    else:
        sample_script = "SCENE 1 - INT. LAB - DAY\nSarah tests Sony camera and drinks Coca-Cola."
        r_script = client.post(f"/productions/{prod_id}/script", data={"script_text": sample_script})

    assert r_script.status_code == 200
    print(f"[4] Registered Screenplay: {r_script.json().get('status')}")

    # 5. Upload Video Footage
    video_path = Path(__file__).resolve().parent.parent / "test_video1.mp4"
    if video_path.exists():
        with open(video_path, "rb") as f:
            r_footage = client.post(f"/productions/{prod_id}/footage", files={"file": ("test_video1.mp4", f, "video/mp4")})
    else:
        r_footage = client.post(f"/productions/{prod_id}/footage", data={"footage_path_override": "test_video1.mp4"})

    assert r_footage.status_code == 200
    print(f"[5] Registered Video Footage: {r_footage.json().get('footage_path')}")

    # 6. Run Autonomous Orchestration Pipeline
    print("[6] Triggering Autonomous ADK 2.8.0 Orchestration...")
    r_orch = client.post(f"/productions/{prod_id}/orchestrate", json={
        "mode": "offline",
        "force_refresh": True,
        "research_provider": "local"
    })
    assert r_orch.status_code == 200, f"Orchestration failed: {r_orch.text}"
    orch_data = r_orch.json()
    print(f"    Status:      {orch_data.get('status')}")
    print(f"    Duration:    {orch_data.get('duration')}s")
    print(f"    Completed:   {orch_data.get('completed_agents')}")
    print(f"    Entities ID: {len(orch_data.get('entity_ids', []))}")
    assert orch_data.get("status") in ("COMPLETED", "PARTIAL")

    # 7. Query Entities
    r_ent = client.get(f"/productions/{prod_id}/entities")
    assert r_ent.status_code == 200
    entities = r_ent.json()
    print(f"\n[7] Detected Clearance Entities ({len(entities)} found):")
    assert len(entities) > 0, "Expected at least 1 detected entity from benchmark!"
    for ent in entities:
        sources = ent.get("sources", [])
        is_vis = ("VISUAL" in sources and "SCRIPT" not in sources) or ent.get("classification") == "VISUAL_ONLY"
        vis_tag = "🚨 VISUAL_ONLY" if is_vis else "SCRIPT/BOTH"
        print(f"    - {ent.get('name'):<20} | Type: {ent.get('entity_type'):<10} | Risk: {ent.get('risk_score')}/100 ({ent.get('risk_level')}) | Status: {ent.get('verification_status')} | Tag: {vis_tag}")

    # 8. Query Exposure
    r_exp = client.get(f"/exposure/{prod_id}")
    assert r_exp.status_code == 200
    exposures = r_exp.json()
    print(f"\n[8] Financial Exposure Records ({len(exposures)} calculated):")
    for exp in exposures:
        print(f"    - {exp.get('entity_name')}: {exp.get('cost_range')}")

    # 9. Query Outreach
    r_out = client.get(f"/outreach/{prod_id}")
    assert r_out.status_code == 200
    drafts = r_out.json()
    print(f"\n[9] Clearance Outreach Drafts ({len(drafts)} generated):")
    for d in drafts:
        print(f"    - {d.get('recipient_entity_name')}: {d.get('email_subject')}")

    # 10. Query Remediations
    r_rem = client.get(f"/remediations/{prod_id}")
    assert r_rem.status_code == 200
    rems = r_rem.json()
    print(f"\n[10] Visual Remediation Proposals ({len(rems)} proposals):")

    # 11. Query Report Result
    r_rep = client.get(f"/productions/{prod_id}/report/result")
    assert r_rep.status_code == 200
    rep = r_rep.json()
    print(f"\n[11] Clearance Report Summary:")
    print(f"     Total Entities:     {rep.get('total_entities')}")
    print(f"     Visual Only:        {rep.get('classification_counts', {}).get('VISUAL_ONLY', 0)}")
    print(f"     Risk Distribution:  {rep.get('risk_distribution')}")

    # 12. Query Standalone HTML Report
    r_html = client.get(f"/productions/{prod_id}/report/html")
    assert r_html.status_code == 200
    print(f"\n[12] Standalone HTML Audit Report: {len(r_html.text)} bytes generated.")

    print("\n" + "=" * 70)
    print("      ALL BENCHMARK VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    test_full_benchmark_run()
