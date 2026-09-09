import html
from typing import List
from app.models.report import ReportFinding, ReportResult

def _badge(text: str, color_type: str) -> str:
    color_map = {
        "high": "background: #ef444422; color: #ef4444; border: 1px solid #ef444455;",
        "medium": "background: #f59e0b22; color: #f59e0b; border: 1px solid #f59e0b55;",
        "low": "background: #10b98122; color: #10b981; border: 1px solid #10b98155;",
        "critical": "background: #dc262633; color: #f87171; border: 1px solid #dc2626;",
        "visual_only": "background: #8b5cf622; color: #a78bfa; border: 1px solid #8b5cf655;",
        "both": "background: #3b82f622; color: #60a5fa; border: 1px solid #3b82f655;",
        "script_only": "background: #6b728022; color: #9ca3af; border: 1px solid #6b728055;",
        "verified": "background: #10b98122; color: #34d399; border: 1px solid #10b98155;",
        "contradicted": "background: #ef444422; color: #f87171; border: 1px solid #ef444455;",
        "default": "background: #37415133; color: #d1d5db; border: 1px solid #4b556355;",
    }
    style = color_map.get(color_type.lower(), color_map["default"])
    return f'<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; {style}">{html.escape(text)}</span>'

def _render_finding_row(f: ReportFinding) -> str:
    risk_color = "high" if f.risk_level == "HIGH" else ("medium" if f.risk_level == "MEDIUM" else "low")
    cls_color = "visual_only" if f.classification == "VISUAL_ONLY" else ("both" if f.classification == "BOTH" else "script_only")
    
    verif_decision = (f.verification_decision or "UNVERIFIED").upper()
    if verif_decision in ("CONFIRMED", "VERIFIED"):
        verif_color = "verified"
        verif_label = "CONFIRMED"
        verif_subtext = "Substantiated"
    elif verif_decision in ("REVIEW", "HUMAN_REVIEW"):
        verif_color = "medium"
        verif_label = "REVIEW"
        verif_subtext = "Secondary Audit"
    elif verif_decision in ("REJECTED", "CONTRADICTED", "DISPUTED"):
        verif_color = "contradicted"
        verif_label = "CONTRADICTED"
        verif_subtext = "Discrepancy Found"
    elif verif_decision == "INSUFFICIENT_EVIDENCE":
        verif_color = "script_only"
        verif_label = "INCONCLUSIVE"
        verif_subtext = "Missing Records"
    else:
        verif_color = "default"
        verif_label = verif_decision
        verif_subtext = "Pending"

    prio_color = "critical" if f.resolution_priority == "CRITICAL" else ("high" if f.resolution_priority == "HIGH" else ("medium" if f.resolution_priority == "MEDIUM" else "low"))

    ts_str = f"{f.timestamp_start:.1f}s" if f.timestamp_start is not None else "N/A"
    scene_str = f"Sc. {f.scene_number}" if f.scene_number is not None else "N/A"
    owner_str = html.escape(f.resolution_owner or "Unassigned")
    action_str = html.escape((f.resolution_action or "UNRESOLVED").replace("_", " "))

    return f"""
    <tr style="border-bottom: 1px solid #1f2937;">
      <td style="padding: 12px 16px; font-weight: 600; color: #f9fafb;">
        {html.escape(f.entity_name)}
        <div style="font-size: 11px; font-family: monospace; color: #9ca3af; margin-top: 2px;">{html.escape(f.entity_id)} &bull; {html.escape(f.entity_type)}</div>
      </td>
      <td style="padding: 12px 16px;">{_badge(f.classification, cls_color)}</td>
      <td style="padding: 12px 16px;">
        {_badge(f.risk_level, risk_color)}
        <div style="font-size: 11px; color: #9ca3af; margin-top: 4px;">Score: {f.risk_score:.2f}</div>
      </td>
      <td style="padding: 12px 16px;">
        {_badge(verif_label, verif_color)}
        <div style="font-size: 10.5px; color: #9ca3af; margin-top: 3px;">{verif_subtext}</div>
      </td>
      <td style="padding: 12px 16px;">
        <div style="font-weight: 600; color: #e5e7eb; font-size: 12.5px;">{action_str}</div>
        <div style="margin-top: 4px;">{_badge(f.resolution_priority or 'MEDIUM', prio_color)} <span style="font-size: 11px; color: #9ca3af; margin-left: 4px;">Owner: {owner_str}</span></div>
      </td>
      <td style="padding: 12px 16px; font-size: 12px; color: #9ca3af;">
        {scene_str} &bull; {ts_str}
        <div style="margin-top: 2px; color: #6b7280;">Evidence: {f.evidence_count} item(s)</div>
      </td>
    </tr>
    """

def _render_research_intelligence_card(item: dict) -> str:
    ent_name = html.escape(item.get("entity_name", "Unknown"))
    ent_id = html.escape(item.get("entity_id", ""))
    ent_type = html.escape(item.get("entity_type", "brand"))
    prov = html.escape(item.get("research_provider", "Parallel Search API"))
    query = html.escape(item.get("search_query", ""))
    cache_status = item.get("cache_status", "LIVE API")
    status_str = html.escape(item.get("status", "SUCCESS"))
    rights_holder = html.escape(item.get("candidate_rights_holder", "None Identified"))
    confidence = item.get("research_confidence", 0.0)
    retrieved_at = html.escape(str(item.get("retrieved_at", "N/A")))
    results = item.get("results", [])
    trademark_ev = item.get("trademark_evidence", [])
    lineage = item.get("lineage", {})

    cache_badge_color = "verified" if "LIVE" in cache_status.upper() else ("visual_only" if "CACHE" in cache_status.upper() else "both")

    # Render results rows/items
    if results:
        results_html = ""
        for idx, res in enumerate(results, 1):
            title = html.escape(res.get("title", "Research Result"))
            url = res.get("url")
            url_html = f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" style="color: #60a5fa; text-decoration: underline; word-break: break-all;">{html.escape(url)}</a>' if url else '<span style="color: #9ca3af; font-style: italic;">No URL (Local Fixture / Direct Knowledge)</span>'
            excerpt = html.escape(res.get("excerpt", "No snippet available"))
            conf = res.get("confidence", 0.90)

            results_html += f"""
            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px 16px; margin-top: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 6px;">
                <div style="font-weight: 600; color: #f3f4f6; font-size: 13.5px;">{idx}. {title}</div>
                <div>{_badge(f"Confidence: {conf*100:.0f}%" if conf <= 1.0 else f"Confidence: {conf:.0f}%", "verified")}</div>
              </div>
              <div style="font-size: 12px; color: #9ca3af; margin-bottom: 6px;">
                <strong>Source URL:</strong> {url_html}
              </div>
              <div style="font-size: 12.5px; color: #d1d5db; background: #1e293b55; border-left: 3px solid #3b82f6; padding: 6px 10px; border-radius: 4px; line-height: 1.5;">
                <em>&ldquo;{excerpt}&rdquo;</em>
              </div>
            </div>
            """
    else:
        results_html = """
        <div style="background: #0f172a; border: 1px dashed #374151; border-radius: 6px; padding: 12px 16px; margin-top: 8px; color: #9ca3af; font-style: italic; font-size: 13px;">
          No evidence returned from search provider.
        </div>
        """

    trademark_html = "".join(f"<li style='margin-bottom: 2px;'>{html.escape(t)}</li>" for t in trademark_ev) if trademark_ev else "<li>No specific trademark registration record returned</li>"

    lineage_str = f"""
    <div style="font-size: 11.5px; font-family: monospace; background: #0b0f19; border: 1px solid #1e293b; border-radius: 6px; padding: 8px 12px; margin-top: 10px; color: #38bdf8; overflow-x: auto;">
      <strong>8-Stage Lineage:</strong>
      <span style="color: #9ca3af;">FRAME</span> ({html.escape(str(lineage.get('frame_source', 'Camera')))}) &rarr;
      <span style="color: #a78bfa;">ENTITY</span> ({ent_name}) &rarr;
      <span style="color: #fbbf24;">RESEARCH QUERY</span> (<code>{query}</code>) &rarr;
      <span style="color: #34d399;">PARALLEL RESULTS</span> ({len(results)} items) &rarr;
      <span style="color: #60a5fa;">EVIDENCE</span> ({lineage.get('evidence_count', len(results))} records) &rarr;
      <span style="color: #f87171;">RISK</span> ({html.escape(str(lineage.get('risk_level', 'UNKNOWN')))}) &rarr;
      <span style="color: #c084fc;">VERIFICATION</span> ({html.escape(str(lineage.get('verification_decision', 'UNVERIFIED')))}) &rarr;
      <span style="color: #4ade80;">RESOLUTION</span> ({html.escape(str(lineage.get('resolution_action', 'UNRESOLVED')))})
    </div>
    """

    return f"""
    <div style="background: #111827; border: 1px solid #1f2937; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 20px; margin-bottom: 18px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: #f9fafb;">{ent_name}</h3>
          <div style="font-size: 12px; color: #9ca3af; margin-top: 2px;">
            Entity ID: <code style="color: #d1d5db;">{ent_id}</code> &bull; Type: <strong>{ent_type}</strong> &bull; Candidate Rights Holder: <strong style="color: #38bdf8;">{rights_holder}</strong>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          {_badge(prov, "both")}
          {_badge(cache_status, cache_badge_color)}
          {_badge(f"Confidence: {confidence*100:.0f}%" if confidence <= 1.0 else f"Confidence: {confidence:.0f}%", "verified")}
        </div>
      </div>

      <div style="background: #0f172a; border-radius: 6px; padding: 10px 14px; font-size: 12.5px; margin-bottom: 12px;">
        <div style="color: #9ca3af; margin-bottom: 4px;"><strong>Executed Search Query:</strong> <code style="color: #f3f4f6; background: #1e293b; padding: 2px 6px; border-radius: 4px;">{query}</code></div>
        <div style="color: #9ca3af; margin-bottom: 4px;"><strong>Retrieval Status:</strong> <span style="color: #e5e7eb;">{status_str} ({len(results)} search results retrieved at {retrieved_at})</span></div>
        <div style="color: #9ca3af;"><strong>Trademark / Corporate Evidence:</strong> <ul style="margin-left: 20px; margin-top: 3px; color: #cbd5e1;">{trademark_html}</ul></div>
      </div>

      <div style="font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 6px;">
        Retrieved Search Evidence Records ({len(results)} Total):
      </div>
      {results_html}

      {lineage_str}
    </div>
    """

def _render_exposure_card(exp: dict) -> str:
    ent_name = html.escape(exp.get("entity_name", "Unknown"))
    ent_id = html.escape(exp.get("entity_id", ""))
    ent_type = html.escape(exp.get("entity_type", "brand"))
    status = html.escape(exp.get("status", "ESTIMATED"))
    currency = html.escape(exp.get("currency", "USD"))
    low = exp.get("estimated_low", 0.0)
    high = exp.get("estimated_high", 0.0)
    conf = exp.get("confidence", 0.85)
    
    stat_dam = exp.get("statutory_damages") or {}
    lic_bench = exp.get("licensing_benchmark") or {}
    rem_cost = exp.get("remediation_cost") or {}
    cases = exp.get("comparable_cases") or []
    notes = html.escape(exp.get("notes", ""))

    if status == "NOT_ESTIMABLE":
        badge_col = "script_only"
        exposure_display = '<span style="color: #9ca3af; font-size: 18px; font-weight: 700;">NOT ESTIMABLE (Insufficient Precedents)</span>'
    elif status == "LOW_RISK_MINIMAL":
        badge_col = "low"
        exposure_display = '<span style="color: #34d399; font-size: 20px; font-weight: 700;">$0 - Minimal Incidental Exposure</span>'
    else:
        badge_col = "high" if high >= 100000 else "medium"
        exposure_display = f'<span style="color: #f59e0b; font-size: 22px; font-weight: 700;">${low:,.0f} &ndash; ${high:,.0f} {currency}</span>'

    # Cases HTML
    cases_html = ""
    if cases:
        for c in cases:
            c_name = html.escape(c.get("case_name", ""))
            c_cit = html.escape(c.get("citation", ""))
            c_yr = html.escape(str(c.get("year", "")))
            c_settle = html.escape(c.get("award_or_settlement", ""))
            c_hold = html.escape(c.get("key_holding", ""))
            cases_html += f"""
            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 14px; margin-top: 6px; font-size: 12px;">
              <div style="display: flex; justify-content: space-between; font-weight: 600; color: #f3f4f6;">
                <span>{c_name} ({c_yr}) &bull; <code style="color: #9ca3af;">{c_cit}</code></span>
                <span style="color: #f87171;">{c_settle}</span>
              </div>
              <div style="color: #cbd5e1; margin-top: 4px;">{c_hold}</div>
            </div>
            """
    else:
        cases_html = '<div style="color: #9ca3af; font-style: italic; font-size: 12px; margin-top: 4px;">No specific case precedents returned. Applied statutory baseline.</div>'

    # Statutory details
    statute_str = html.escape(stat_dam.get("statute", "15 U.S.C. § 1117 / 17 U.S.C. § 504"))
    stat_min = stat_dam.get("min_damages", 750)
    stat_max = stat_dam.get("max_damages", 30000)
    stat_willful = stat_dam.get("willful_max_damages", 150000)

    # Licensing details
    lic_low = lic_bench.get("typical_fee_low", 2500)
    lic_high = lic_bench.get("typical_fee_high", 15000)
    lic_tier = html.escape(lic_bench.get("industry_tier", "Standard Commercial"))

    # Remediation details
    rem_est = rem_cost.get("estimated_cost", 1500)
    rem_type = html.escape(rem_cost.get("remediation_type", "VFX Paintout"))

    return f"""
    <div style="background: #111827; border: 1px solid #1f2937; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px; margin-bottom: 18px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: #f9fafb;">{ent_name}</h3>
          <div style="font-size: 12px; color: #9ca3af; margin-top: 2px;">
            Entity ID: <code style="color: #d1d5db;">{ent_id}</code> &bull; Type: <strong>{ent_type}</strong>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          {_badge(status, badge_col)}
          {_badge(f"Confidence: {conf*100:.0f}%" if conf <= 1.0 else f"Confidence: {conf:.0f}%", "verified")}
        </div>
      </div>

      <div style="background: #0f172a; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div>
          <div style="font-size: 11px; text-transform: uppercase; color: #9ca3af; font-weight: 600; letter-spacing: 0.05em;">Estimated Operational Cost Exposure Range</div>
          <div style="margin-top: 4px;">{exposure_display}</div>
        </div>
        <div style="font-size: 12px; color: #9ca3af; text-align: right;">
          <div>Market License Benchmark: <strong style="color: #60a5fa;">${lic_low:,.0f} &ndash; ${lic_high:,.0f}</strong> ({lic_tier})</div>
          <div style="margin-top: 2px;">VFX Paintout/Cleanup: <strong style="color: #34d399;">~${rem_est:,.0f}</strong> ({rem_type})</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 12px;">
        <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px 14px; font-size: 12.5px;">
          <div style="font-weight: 600; color: #fbbf24; margin-bottom: 6px;">&#x2696;&#xFE0F; Statutory Reference Framework (Non-Predictive: {statute_str})</div>
          <div style="color: #9ca3af;">Statutory Min: <span style="color: #f3f4f6;">${stat_min:,.0f}</span></div>
          <div style="color: #9ca3af;">Statutory Max (Standard): <span style="color: #f3f4f6;">${stat_max:,.0f}</span></div>
          <div style="color: #9ca3af;">Willful Infringement Ceiling: <span style="color: #f87171; font-weight: 600;">${stat_willful:,.0f}</span></div>
          <div style="font-size: 10.5px; color: #6b7280; margin-top: 4px; font-style: italic;">Reference only &bull; Not a liability prediction.</div>
        </div>
        <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px 14px; font-size: 12.5px;">
          <div style="font-weight: 600; color: #38bdf8; margin-bottom: 6px;">&#x1F4CA; Operational Remediation vs. Settlement Analysis</div>
          <div style="color: #cbd5e1; line-height: 1.4;">{notes if notes else 'Standard commercial rights licensing or VFX paintout replacement recommended.'}</div>
        </div>
      </div>

      <div style="font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 4px;">
        Comparable Case Precedents & Judgments:
      </div>
      {cases_html}
    </div>
    """

def _render_outreach_card(out: dict) -> str:
    ent_name = html.escape(out.get("entity_name", "Unknown"))
    rh = html.escape(out.get("rights_holder", "Rights Holder"))
    email = html.escape(out.get("contact_email", "") or "licensing@rights-inquiries.com")
    subj = html.escape(out.get("subject", "Permission Request"))
    body = html.escape(out.get("body", ""))
    status = html.escape(out.get("status", "DRAFTED"))
    timecode = html.escape(str(out.get("timecode", "N/A") or "N/A"))
    territory = html.escape(out.get("territory", "Worldwide"))
    media = html.escape(out.get("media_rights", "All Media including Theatrical and VOD"))
    term = html.escape(out.get("term", "In Perpetuity"))
    gmail_draft_id = html.escape(out.get("gmail_draft_id", "") or "local-mime-draft")

    return f"""
    <div style="background: #111827; border: 1px solid #1f2937; border-left: 4px solid #10b981; border-radius: 8px; padding: 20px; margin-bottom: 18px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: #f9fafb;">{ent_name} &rarr; {rh}</h3>
          <div style="font-size: 12px; color: #9ca3af; margin-top: 2px;">
            Target Contact: <strong style="color: #38bdf8;">{email}</strong> &bull; Draft Reference: <code style="color: #d1d5db;">{gmail_draft_id}</code>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          {_badge(status, "verified")}
          {_badge("Human Approval Required", "critical")}
        </div>
      </div>

      <div style="background: #0f172a; border-radius: 6px; padding: 10px 14px; font-size: 12.5px; margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 16px;">
        <div><strong style="color: #9ca3af;">Scope:</strong> <span style="color: #f3f4f6;">{media}</span></div>
        <div><strong style="color: #9ca3af;">Territory:</strong> <span style="color: #f3f4f6;">{territory}</span></div>
        <div><strong style="color: #9ca3af;">Term:</strong> <span style="color: #f3f4f6;">{term}</span></div>
        <div><strong style="color: #9ca3af;">Timecode:</strong> <span style="color: #f3f4f6;">{timecode}</span></div>
      </div>

      <div style="font-size: 12.5px; color: #e5e7eb; margin-bottom: 6px;">
        <strong>Subject:</strong> <span style="color: #60a5fa;">{subj}</span>
      </div>

      <div style="background: #0b0f19; border: 1px solid #1e293b; border-left: 3px solid #10b981; border-radius: 6px; padding: 14px; font-family: monospace; font-size: 12px; color: #d1d5db; white-space: pre-wrap; line-height: 1.6; max-height: 250px; overflow-y: auto;">{body}</div>

      <div style="margin-top: 10px; font-size: 11.5px; color: #fbbf24; background: #451a0333; border: 1px solid #b4530944; border-radius: 4px; padding: 6px 10px;">
        &#x26A0;&#xFE0F; <strong>Human Authorization Required:</strong> This clearance outreach letter has been generated as a draft only. Legal counsel or clearance coordinator approval is strictly mandatory before communication is dispatched.
      </div>
    </div>
    """

def _render_remediation_card(rem: dict) -> str:
    ent_name = html.escape(rem.get("entity_name", "Unknown"))
    rem_type = html.escape(rem.get("remediation_type", "GAUSSIAN_BLUR"))
    status = html.escape(rem.get("status", "PROPOSED"))
    orig_path = html.escape(rem.get("original_frame_path", ""))
    rem_path = html.escape(rem.get("proposed_frame_path", "") or rem.get("remediated_frame_path", ""))
    comp_path = html.escape(rem.get("comparison_frame_path", "") or "")
    comp_url = rem.get("comparison_frame_url") or rem.get("proposed_frame_url") or rem.get("remediated_frame_url")
    conf = rem.get("confidence", 0.95)
    vfx_hours = rem.get("vfx_time_estimate_hours", 1.5)
    vfx_cost = rem.get("vfx_cost_estimate_usd", 1200.0)
    disclaimer = html.escape(rem.get("disclaimer", "") or rem.get("human_review_disclaimer", "PROPOSED REMEDIATION — HUMAN/EDITOR REVIEW REQUIRED. Original master footage is unaltered."))

    img_block = ""
    if comp_url:
        img_block = f'<div style="margin-top: 14px;"><img src="{html.escape(comp_url)}" alt="Remediation Side-by-Side Comparison" style="max-width: 100%; border-radius: 6px; border: 1px solid #374151; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4);" /></div>'
    elif comp_path:
        img_block = f'<div style="margin-top: 8px; font-size: 11.5px; font-family: monospace; color: #9ca3af; background: #0b0f19; padding: 8px 12px; border-radius: 4px;"><strong>Comparison Artifact:</strong> {comp_path}</div>'

    return f"""
    <div style="background: #111827; border: 1px solid #1f2937; border-left: 4px solid #8b5cf6; border-radius: 8px; padding: 20px; margin-bottom: 18px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: #f9fafb;">{ent_name} &bull; Proposed Optical Cleanup</h3>
          <div style="font-size: 12px; color: #9ca3af; margin-top: 2px;">
            Remediation Technique: <strong style="color: #c4b5fd;">{rem_type}</strong> &bull; Non-Destructive Optical Layer
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          {_badge(status, "visual_only")}
          {_badge("Human Approval Required", "critical")}
          {_badge(f"Est: ~{vfx_hours}h (${vfx_cost:,.0f})", "low")}
        </div>
      </div>

      <div style="background: #31135e33; border: 1px solid #7c3aed44; border-radius: 6px; padding: 10px 14px; font-size: 12px; color: #ddd6fe; margin-bottom: 10px;">
        &#x1F3A8; <strong>Studio Notice:</strong> {disclaimer}
      </div>

      <div style="font-size: 12px; color: #9ca3af; line-height: 1.6;">
        <div><strong>Original Source Frame:</strong> <code style="color: #cbd5e1;">{orig_path}</code></div>
        <div><strong>Proposed Cleanup Layer:</strong> <code style="color: #cbd5e1;">{rem_path}</code></div>
      </div>

      {img_block}
    </div>
    """

def render_html_report(report: ReportResult) -> str:
    """
    Generate an executive-grade, responsive HTML report.
    Completely standalone with embedded CSS and modern cinema aesthetics.
    """
    findings_rows = "".join(_render_finding_row(f) for f in report.all_findings)
    priority_rows = "".join(_render_finding_row(f) for f in report.priority_findings)
    visual_only_rows = "".join(_render_finding_row(f) for f in report.visual_only_findings)

    # Parallel Research Intelligence Section
    research_intel_items = getattr(report, "parallel_research_intelligence", [])
    research_cards_html = "".join(_render_research_intelligence_card(item) for item in research_intel_items)

    # Phase 10: Financial Exposure Intelligence Section
    exposure_items = getattr(report, "financial_exposure_intelligence", [])
    exposure_cards_html = "".join(_render_exposure_card(item) for item in exposure_items)

    # Phase 11: Clearance Outreach Packages Section
    outreach_items = getattr(report, "clearance_outreach_drafts", [])
    outreach_cards_html = "".join(_render_outreach_card(item) for item in outreach_items)

    # Phase 12: Visual Remediation Studio Section
    remediation_items = getattr(report, "visual_remediation_proposals", [])
    remediation_cards_html = "".join(_render_remediation_card(item) for item in remediation_items)

    generated_date_str = report.generated_at.strftime("%B %d, %Y - %H:%M:%S UTC")

    # Metrics
    vis_count = report.classification_counts.get("VISUAL_ONLY", 0)
    high_risk_count = report.risk_distribution.get("HIGH", 0)
    contradicted_count = report.verification_distribution.get("CONTRADICTED", 0)
    license_req_count = report.resolution_distribution.get("LICENSE_REQUIRED", 0)
    remove_count = report.resolution_distribution.get("REMOVE_OR_REPLACE", 0)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chain of Title Pre-Clearance Intelligence Report - {html.escape(report.production_title or report.production_id)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Calibri', 'Segoe UI', Candara, -apple-system, BlinkMacSystemFont, Arial, sans-serif;
      font-size: 15px;
      background-color: #0b0f19;
      color: #e5e7eb;
      line-height: 1.55;
      padding: 32px 20px;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    .header-card {{
      background: linear-gradient(135deg, #111827 0%, #1e1b4b 100%);
      border: 1px solid #374151;
      border-radius: 12px;
      padding: 32px;
      margin-bottom: 24px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }}
    .header-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .title-area h1 {{
      font-size: 26px;
      font-weight: 700;
      color: #f9fafb;
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      font-size: 14px;
      color: #9ca3af;
      margin-top: 6px;
    }}
    .status-badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      background: #065f46;
      color: #34d399;
      border: 1px solid #059669;
    }}
    .disclaimer-banner {{
      background: #451a03;
      border: 1px solid #b45309;
      border-left: 6px solid #f59e0b;
      padding: 16px 20px;
      border-radius: 8px;
      margin-bottom: 24px;
      font-size: 12.5px;
      color: #fef3c7;
      line-height: 1.6;
    }}
    .disclaimer-title {{
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
      color: #fbbf24;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .grid-kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 20px;
    }}
    .kpi-label {{
      font-size: 11.5px;
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.05em;
      color: #9ca3af;
      margin-bottom: 8px;
    }}
    .kpi-value {{
      font-size: 28px;
      font-weight: 700;
      color: #f9fafb;
    }}
    .kpi-subtext {{
      font-size: 11px;
      color: #6b7280;
      margin-top: 4px;
    }}
    .section-card {{
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 10px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }}
    .section-title {{
      font-size: 18px;
      font-weight: 600;
      color: #f3f4f6;
    }}
    .section-count {{
      font-size: 12px;
      background: #1f2937;
      color: #9ca3af;
      padding: 3px 10px;
      border-radius: 9999px;
      font-weight: 600;
    }}
    .table-container {{
      overflow-x: auto;
      border-radius: 6px;
      border: 1px solid #1f2937;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }}
    th {{
      background: #1f2937;
      color: #9ca3af;
      font-weight: 600;
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 12px 16px;
      border-bottom: 1px solid #374151;
    }}
    .spotlight-banner {{
      background: linear-gradient(90deg, #31135e 0%, #1e1b4b 100%);
      border: 1px solid #7c3aed55;
      border-left: 6px solid #8b5cf6;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 18px;
      font-size: 13px;
    }}
    .footer {{
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #1f2937;
      font-size: 12px;
      color: #6b7280;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    /* Report theme: editorial, print-friendly, and easy to scan. */
    :root {{
      --paper: #f5f3ee;
      --surface: #fffdf9;
      --ink: #17212b;
      --muted: #68727b;
      --line: #d9d6cf;
      --navy: #18344a;
      --amber: #b56a24;
      --red: #a94336;
      --green: #39745b;
    }}
    body {{
      background: var(--paper) !important;
      color: var(--ink) !important;
      font-family: Arial, Helvetica, sans-serif !important;
      font-size: 14px !important;
      line-height: 1.55 !important;
      padding: 42px 24px !important;
    }}
    .container {{ max-width: 1280px !important; }}
    .header-card {{
      background: var(--navy) !important;
      border: 0 !important;
      border-radius: 2px !important;
      padding: 42px 46px !important;
      margin-bottom: 18px !important;
      box-shadow: none !important;
    }}
    .title-area h1 {{
      color: #fffdf9 !important;
      font-family: Georgia, 'Times New Roman', serif !important;
      font-size: clamp(28px, 4vw, 48px) !important;
      font-weight: 400 !important;
      letter-spacing: 0 !important;
      line-height: 1.08 !important;
      max-width: 860px;
    }}
    .subtitle {{ color: #c8d2d8 !important; margin-top: 14px !important; }}
    .subtitle span {{ color: #fffdf9 !important; }}
    .status-badge {{
      background: #e6efe8 !important;
      color: var(--green) !important;
      border: 0 !important;
      border-radius: 2px !important;
      padding: 8px 12px !important;
    }}
    .disclaimer-banner {{
      background: #fff7e7 !important;
      color: #604b35 !important;
      border: 1px solid #e7cfaa !important;
      border-left: 4px solid var(--amber) !important;
      border-radius: 2px !important;
      padding: 16px 20px !important;
      margin-bottom: 18px !important;
    }}
    .disclaimer-title {{ color: var(--amber) !important; }}
    .grid-kpis {{ gap: 10px !important; margin-bottom: 18px !important; }}
    .kpi-card {{
      background: var(--surface) !important;
      border: 1px solid var(--line) !important;
      border-left: 3px solid var(--navy) !important;
      border-radius: 2px !important;
      padding: 18px !important;
    }}
    .kpi-card[style*="8b5cf6"] {{ border-left-color: var(--amber) !important; }}
    .kpi-card[style*="ef4444"] {{ border-left-color: var(--red) !important; }}
    .kpi-label {{ color: var(--muted) !important; letter-spacing: .08em !important; }}
    .kpi-value {{ color: var(--ink) !important; font-family: Georgia, 'Times New Roman', serif !important; font-size: 32px !important; }}
    .kpi-value[style*="c4b5fd"] {{ color: var(--amber) !important; }}
    .kpi-value[style*="f87171"] {{ color: var(--red) !important; }}
    .kpi-subtext {{ color: var(--muted) !important; }}
    .section-card {{
      background: var(--surface) !important;
      border: 1px solid var(--line) !important;
      border-radius: 2px !important;
      padding: 28px !important;
      margin-bottom: 18px !important;
      box-shadow: 0 1px 2px rgba(23, 33, 43, .04) !important;
    }}
    .section-card[style*="border-color"] {{ border-top: 3px solid var(--navy) !important; }}
    .section-header {{ border-bottom: 1px solid var(--line) !important; padding-bottom: 12px !important; margin-bottom: 18px !important; }}
    .section-title {{ color: var(--navy) !important; font-family: Georgia, 'Times New Roman', serif !important; font-size: 22px !important; font-weight: 400 !important; letter-spacing: 0 !important; }}
    .section-count {{ background: #edf0f1 !important; color: var(--muted) !important; border-radius: 2px !important; }}
    .table-container {{ border: 1px solid var(--line) !important; border-radius: 2px !important; }}
    table {{ color: var(--ink) !important; font-size: 13px !important; }}
    th {{ background: #edf0f1 !important; color: var(--navy) !important; border-bottom: 1px solid var(--line) !important; padding: 12px 14px !important; }}
    td {{ border-color: var(--line) !important; }}
    .spotlight-banner {{ background: #fff7e7 !important; border: 1px solid #e7cfaa !important; border-left: 4px solid var(--amber) !important; border-radius: 2px !important; color: #604b35 !important; }}
    .footer {{ border-top-color: var(--line) !important; color: var(--muted) !important; }}
    /* Normalize the legacy card fragments produced by the section renderers. */
    [style*="background: #111827"], [style*="background: #0f172a"], [style*="background: #0b0f19"] {{ background: #f8f7f3 !important; color: var(--ink) !important; }}
    [style*="border: 1px solid #1f2937"], [style*="border: 1px solid #1e293b"] {{ border-color: var(--line) !important; }}
    [style*="color: #f9fafb"], [style*="color: #f3f4f6"], [style*="color: #e5e7eb"], [style*="color: #d1d5db"], [style*="color: #cbd5e1"] {{ color: var(--ink) !important; }}
    [style*="color: #9ca3af"], [style*="color: #6b7280"] {{ color: var(--muted) !important; }}
    [style*="color: #60a5fa"], [style*="color: #38bdf8"] {{ color: var(--navy) !important; }}
    a {{ color: var(--navy) !important; }}
    code {{ color: var(--navy) !important; background: #edf0f1 !important; }}
    @media (max-width: 720px) {{
      body {{ padding: 18px 12px !important; }}
      .header-card {{ padding: 28px 24px !important; }}
      .section-card {{ padding: 20px 16px !important; }}
      .section-header {{ align-items: flex-start !important; flex-direction: column !important; gap: 8px !important; }}
      .table-container {{ margin: 0 -2px; }}
    }}
    @media print {{
      body {{ background: #fff !important; padding: 0 !important; }}
      .section-card, .kpi-card {{ box-shadow: none !important; break-inside: avoid; }}
      .header-card {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    
    <!-- Header -->
    <div class="header-card">
      <div class="header-top">
        <div class="title-area">
          <h1>{html.escape(report.title)}</h1>
          <div class="subtitle">Production ID: <span style="font-family: monospace; color: #d1d5db;">{html.escape(report.production_id)}</span> &bull; Job ID: <span style="font-family: monospace; color: #d1d5db;">{html.escape(report.job_id)}</span> &bull; Generated: {generated_date_str}</div>
        </div>
        <div class="status-badge">{html.escape(report.status.value if hasattr(report.status, 'value') else str(report.status))}</div>
      </div>
    </div>

    <!-- Mandatory Non-Legal Disclaimer -->
    <div class="disclaimer-banner">
      <div class="disclaimer-title">&#x26A0;&#xFE0F; Non-Legal Advice Notice</div>
      {html.escape(report.disclaimer)}
    </div>

    <!-- Executive KPI Grid -->
    <div class="grid-kpis">
      <div class="kpi-card">
        <div class="kpi-label">Total Entities</div>
        <div class="kpi-value">{report.total_entities}</div>
        <div class="kpi-subtext">Screenplay + Video footage</div>
      </div>
      <div class="kpi-card" style="border-left: 3px solid #8b5cf6;">
        <div class="kpi-label">Visual-Only Spotlight</div>
        <div class="kpi-value" style="color: #c4b5fd;">{vis_count}</div>
        <div class="kpi-subtext">Unscripted on-camera exposure</div>
      </div>
      <div class="kpi-card" style="border-left: 3px solid #ef4444;">
        <div class="kpi-label">High Risk Entities</div>
        <div class="kpi-value" style="color: #f87171;">{high_risk_count}</div>
        <div class="kpi-subtext">Immediate clearance required</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Research Evidence Coverage</div>
        <div class="kpi-value">{report.research_coverage * 100:.1f}%</div>
        <div class="kpi-subtext">{report.researched_count} of {report.total_entities} verified with evidence</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Verification Coverage</div>
        <div class="kpi-value">{report.verification_coverage * 100:.1f}%</div>
        <div class="kpi-subtext">{report.verified_count} verified ({contradicted_count} contradictions)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Resolution Coverage</div>
        <div class="kpi-value">{report.resolution_coverage * 100:.1f}%</div>
        <div class="kpi-subtext">{license_req_count} licenses &bull; {remove_count} removals</div>
      </div>
    </div>

    <!-- Executive Summary -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">Executive Clearance Summary</div>
        <span class="section-count">Automated Pipeline v{report.version}</span>
      </div>
      <p style="color: #d1d5db; line-height: 1.7; font-size: 14.5px;">
        {html.escape(report.executive_summary)}
      </p>
    </div>

    <!-- PARALLEL RESEARCH INTELLIGENCE SECTION -->
    <div class="section-card" style="border-color: #2563eb;">
      <div class="section-header">
        <div class="section-title" style="color: #93c5fd;">&#x1F310; PARALLEL RESEARCH INTELLIGENCE & RIGHTS-HOLDER EVIDENCE</div>
        <span class="section-count" style="background: #1e3a8a; color: #bfdbfe;">Parallel Search API &bull; {len(research_intel_items)} Entities Analyzed</span>
      </div>
      <p style="color: #9ca3af; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
        Objective corporate rights-holder discovery, registered trademark status, and web corroboration evidence retrieved from the Parallel Search API. Preserves full auditability from camera frame detection to commercial rights holder verification.
      </p>
      {research_cards_html if research_cards_html else '<div style="color: #9ca3af; padding: 20px; text-align: center;">No research intelligence records available.</div>'}
    </div>

    <!-- FINANCIAL EXPOSURE INTELLIGENCE SECTION (PHASE 10) -->
    <div class="section-card" style="border-color: #d97706;">
      <div class="section-header">
        <div class="section-title" style="color: #fbbf24;">&#x1F4B0; FINANCIAL EXPOSURE INTELLIGENCE & STATUTORY REFERENCE FRAMEWORK</div>
        <span class="section-count" style="background: #451a03; color: #fde68a;">Phase 10 &bull; {len(exposure_items)} Entities Quantified</span>
      </div>
      <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 12.5px; color: #cbd5e1; line-height: 1.5;">
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
          <div><strong style="color: #f59e0b;">&#x1F4CA; Risk Score:</strong> How urgently the production should investigate the issue.</div>
          <div><strong style="color: #38bdf8;">&#x1F4B5; Financial Exposure:</strong> Evidence-backed operational estimate of potential cost / licensing / business exposure.</div>
          <div><strong style="color: #a78bfa;">&#x2696;&#xFE0F; Statutory Framework:</strong> Legal reference only (17 U.S.C. § 504 / 15 U.S.C. § 1117), <em>NOT</em> a prediction of court liability.</div>
        </div>
      </div>
      <p style="color: #9ca3af; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
        Financial exposure modeling based on Lanham Act (15 U.S.C. § 1117) and Copyright Act (17 U.S.C. § 504) statutory reference baselines, market licensing benchmarks, and live case law precedent search.
      </p>
      {exposure_cards_html if exposure_cards_html else '<div style="color: #9ca3af; padding: 20px; text-align: center;">No financial exposure models generated.</div>'}
    </div>

    <!-- CLEARANCE OUTREACH PACKAGES SECTION (PHASE 11) -->
    <div class="section-card" style="border-color: #059669;">
      <div class="section-header">
        <div class="section-title" style="color: #34d399;">&#x2709;&#xFE0F; CLEARANCE OUTREACH & PERMISSION PACKAGES</div>
        <span class="section-count" style="background: #064e3b; color: #a7f3d0;">Phase 11 &bull; {len(outreach_items)} Drafts Generated (Gmail Drafts)</span>
      </div>
      <p style="color: #9ca3af; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
        Automated rights clearance permission request drafts customized with candidate rights-holder contact info, scene timecode, and worldwide distribution scopes. Drafted strictly in Draft mode pending human legal approval.
      </p>
      {outreach_cards_html if outreach_cards_html else '<div style="color: #9ca3af; padding: 20px; text-align: center;">No clearance outreach drafts generated.</div>'}
    </div>

    <!-- VISUAL REMEDIATION STUDIO SECTION (PHASE 12) -->
    <div class="section-card" style="border-color: #7c3aed;">
      <div class="section-header">
        <div class="section-title" style="color: #c4b5fd;">&#x1F3A8; VISUAL REMEDIATION STUDIO & OPTICAL CLEANUPS</div>
        <span class="section-count" style="background: #3b0764; color: #e9d5ff;">Phase 12 &bull; {len(remediation_items)} Proposed Remediations</span>
      </div>
      <p style="color: #9ca3af; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
        Non-destructive optical cleanup proposals (Gaussian blur, neutral prop replacement, AI inpainting) generated from detection bounding boxes. Original master footage remains strictly unaltered.
      </p>
      {remediation_cards_html if remediation_cards_html else '<div style="color: #9ca3af; padding: 20px; text-align: center;">No visual remediation proposals generated.</div>'}
    </div>

    <!-- Visual-Only Exposure Spotlight -->
    {f"""
    <div class="section-card" style="border-color: #6d28d9;">
      <div class="section-header">
        <div class="section-title" style="color: #c4b5fd;">&#x1F50D; Visual-Only Exposure Spotlight ({len(report.visual_only_findings)})</div>
        <span class="section-count" style="background: #4c1d95; color: #ddd6fe;">Highest Surprise Liability</span>
      </div>
      <div class="spotlight-banner">
        <strong>Critical Studio Advisory:</strong> These entities were discovered in video footage (props, signage, wardrobe, incidental set decoration) but possess <em>zero trace</em> in the script. They represent unbudgeted and unscripted trademark/copyright liabilities.
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Entity</th>
              <th>Classification</th>
              <th>Risk Assessment</th>
              <th>Verification</th>
              <th>Action & Priority</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            {visual_only_rows}
          </tbody>
        </table>
      </div>
    </div>
    """ if report.visual_only_findings else ""}

    <!-- Priority Clearance Findings -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">&#x1F6A8; Priority Clearance Action Items</div>
        <span class="section-count">{len(report.priority_findings)} Items Requiring Action</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Entity</th>
              <th>Classification</th>
              <th>Risk Assessment</th>
              <th>Verification</th>
              <th>Recommended Action</th>
              <th>Location & Evidence</th>
            </tr>
          </thead>
          <tbody>
            {priority_rows if report.priority_findings else '<tr><td colspan="6" style="padding: 24px; text-align: center; color: #9ca3af;">No urgent priority clearance findings identified.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Complete Clearance Findings Matrix -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">Comprehensive Clearance Findings Matrix</div>
        <span class="section-count">{len(report.all_findings)} Total Items</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Entity</th>
              <th>Classification</th>
              <th>Risk Assessment</th>
              <th>Verification</th>
              <th>Recommended Action</th>
              <th>Location & Evidence</th>
            </tr>
          </thead>
          <tbody>
            {findings_rows if report.all_findings else '<tr><td colspan="6" style="padding: 24px; text-align: center; color: #9ca3af;">No clearance entities detected for this production.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer">
      <div>Chain of Title Intelligence System &bull; Phase 8 Reporting Engine &bull; Generation Duration: {report.generation_duration_ms:.1f}ms</div>
      <div style="font-family: monospace;">Report ID: {html.escape(report.report_id)}</div>
    </div>

  </div>
</body>
</html>
"""
    return html_content
