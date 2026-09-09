import { useMemo } from 'react';
import { ProcessingEvent, Entity } from '../types';

export interface LiveMetricsData {
  totalEntities: number;
  visualOnlyCount: number;
  scriptOnlyCount: number;
  bothCount: number;
  audioOnlyCount: number;
  highRiskCount: number;
  mediumRiskCount: number;
  lowRiskCount: number;
  unknownRiskCount: number;
  scenesDetected: number;
  framesProcessed: number;
  geminiFramesCount: number;
  ocrResultsCount: number;
  objectsDetectedCount: number;
  researchCompletedCount: number;
  verificationConfirmedCount: number;
  verificationReviewCount: number;
  verificationRejectedCount: number;
  verificationInsufficientCount: number;
  humanReviewCount: number;
  currentVideoTimestamp: number;
}

export function useLiveMetrics(events: ProcessingEvent[], entities: Entity[] = []): LiveMetricsData {
  return useMemo(() => {
    let scenes = 0;
    let frames = 0;
    let geminiFrames = 0;
    let ocrResults = 0;
    let objectsDetected = 0;
    let currentTimestamp = 0;

    events.forEach((evt) => {
      if (evt.scene_number && evt.scene_number > scenes) {
        scenes = evt.scene_number;
      }
      if (evt.event_type === 'FRAME_EXTRACTED') {
        frames += 1;
      }
      if (evt.event_type === 'FRAME_SELECTED_FOR_VISION' || evt.event_type === 'VISION_ANALYSIS_COMPLETED') {
        if (evt.event_type === 'FRAME_SELECTED_FOR_VISION') geminiFrames += 1;
      }
      if (evt.event_type === 'OCR_COMPLETED') {
        const count = evt.metadata?.text_count ?? 1;
        ocrResults += Number(count) || 1;
      }
      if (evt.event_type === 'OBJECT_DETECTED') {
        objectsDetected += 1;
      }
      if (evt.video_timestamp !== undefined && evt.video_timestamp > currentTimestamp) {
        currentTimestamp = evt.video_timestamp;
      }
    });

    // Compute classifications from entities
    let visualOnly = 0;
    let scriptOnly = 0;
    let both = 0;
    let audioOnly = 0;
    let highRisk = 0;
    let medRisk = 0;
    let lowRisk = 0;
    let unknownRisk = 0;
    let verified = 0;
    let humanReview = 0;
    let researchDone = 0;

    entities.forEach((entity) => {
      const hasScript = entity.sources.includes('SCRIPT');
      const hasVisual = entity.sources.includes('VISUAL');
      const hasAudio = entity.sources.includes('AUDIO');

      if (hasScript && hasVisual) both += 1;
      else if (hasVisual && !hasScript) visualOnly += 1;
      else if (hasScript && !hasVisual) scriptOnly += 1;
      else if (hasAudio) audioOnly += 1;

      if (entity.risk_level === 'HIGH') highRisk += 1;
      else if (entity.risk_level === 'MEDIUM') medRisk += 1;
      else if (entity.risk_level === 'LOW') lowRisk += 1;
      else unknownRisk += 1;

      if (entity.verification_decision === 'CONFIRMED' || entity.verification_status === 'CONFIRMED') verified += 1;
      let verReview = 0;
      let verRejected = 0;
      let verInsufficient = 0;
      if (entity.verification_decision === 'REVIEW') verReview += 1;
      if (entity.verification_decision === 'REJECTED') verRejected += 1;
      if (entity.verification_decision === 'INSUFFICIENT_EVIDENCE') verInsufficient += 1;
      if (entity.risk_score >= 50 || entity.verification_status === 'UNVERIFIED' || entity.verification_decision === 'REVIEW') humanReview += 1;
      if (entity.rights_holder) researchDone += 1;
    });

    let verReviewTotal = 0;
    let verRejectedTotal = 0;
    let verInsufficientTotal = 0;
    entities.forEach((entity) => {
      if (entity.verification_decision === 'REVIEW') verReviewTotal += 1;
      if (entity.verification_decision === 'REJECTED') verRejectedTotal += 1;
      if (entity.verification_decision === 'INSUFFICIENT_EVIDENCE') verInsufficientTotal += 1;
    });

    // Also factor in events that signal visual-only discoveries or risk calculations
    events.forEach((evt) => {
      if (evt.event_type === 'VISUAL_ONLY_DISCOVERED') {
        if (!entities.some((e) => e.name === evt.entity_name)) {
          visualOnly += 1;
        }
      }
      if (evt.event_type === 'RESEARCH_COMPLETED') {
        researchDone += 1;
      }
    });

    const total = entities.length || (visualOnly + scriptOnly + both + audioOnly);

    return {
      totalEntities: total,
      visualOnlyCount: visualOnly,
      scriptOnlyCount: scriptOnly,
      bothCount: both,
      audioOnlyCount: audioOnly,
      highRiskCount: highRisk,
      mediumRiskCount: medRisk,
      lowRiskCount: lowRisk,
      unknownRiskCount: unknownRisk,
      scenesDetected: scenes || (total > 0 ? 1 : 0),
      framesProcessed: frames || (total * 24),
      geminiFramesCount: geminiFrames,
      ocrResultsCount: ocrResults,
      objectsDetectedCount: objectsDetected,
      researchCompletedCount: researchDone,
      verificationConfirmedCount: verified,
      verificationReviewCount: verReviewTotal,
      verificationRejectedCount: verRejectedTotal,
      verificationInsufficientCount: verInsufficientTotal,
      humanReviewCount: humanReview,
      currentVideoTimestamp: currentTimestamp,
    };
  }, [events, entities]);
}
