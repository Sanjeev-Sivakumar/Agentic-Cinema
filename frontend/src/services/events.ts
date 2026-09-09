import { ProcessingEvent } from '../types';

export interface SSEConnection {
  close: () => void;
}

export function subscribeToAnalysisEvents(
  productionId: string,
  jobId: string,
  onEvent: (event: ProcessingEvent) => void,
  onError?: (err: any) => void
): SSEConnection {
  const url = `/productions/${productionId}/analysis/${jobId}/events`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    try {
      const data: ProcessingEvent = JSON.parse(e.data);
      onEvent(data);
    } catch (err) {
      console.error('[SSE] Failed to parse event payload:', err);
    }
  };

  // Listen to custom typed SSE events
  const knownEvents = [
    'ANALYSIS_STARTED',
    'STAGE_STARTED',
    'STAGE_COMPLETED',
    'FRAME_EXTRACTED',
    'SCENE_DETECTED',
    'OCR_COMPLETED',
    'OBJECT_DETECTED',
    'FRAME_SELECTED_FOR_VISION',
    'VISION_ANALYSIS_STARTED',
    'VISION_ANALYSIS_COMPLETED',
    'ENTITY_DETECTED',
    'ENTITY_ADDED',
    'ENTITY_DEDUPLICATED',
    'VISUAL_ONLY_DISCOVERED',
    'RESEARCH_STARTED',
    'RESEARCH_COMPLETED',
    'RISK_ASSESSMENT_STARTED',
    'RISK_SIGNAL_CALCULATED',
    'RISK_CALCULATED',
    'RISK_ASSESSMENT_COMPLETED',
    'RISK_ASSESSMENT_FAILED',
    'VERIFICATION_STARTED',
    'VERIFICATION_CHECK_COMPLETED',
    'VERIFICATION_CONTRADICTION_FOUND',
    'VERIFICATION_COMPLETED',
    'VERIFICATION_FAILED',
    'RESOLUTION_STARTED',
    'RESOLUTION_ACTION_RECOMMENDED',
    'RESOLUTION_ESCALATED',
    'RESOLUTION_COMPLETED',
    'RESOLUTION_FAILED',
    'REPORT_GENERATION_STARTED',
    'REPORT_SECTION_GENERATED',
    'REPORT_GENERATION_COMPLETED',
    'REPORT_GENERATION_FAILED',
    'REPORT_GENERATED',
    'ORCHESTRATION_STARTED',
    'AGENT_STARTED',
    'AGENT_COMPLETED',
    'AGENT_FAILED',
    'TOOL_STARTED',
    'TOOL_COMPLETED',
    'ORCHESTRATION_COMPLETED',
    'ORCHESTRATION_FAILED',
    'ANALYSIS_COMPLETED',
    'ANALYSIS_FAILED',
    'ANALYSIS_CANCELLED',
  ];

  knownEvents.forEach((eventType) => {
    eventSource.addEventListener(eventType, (e: any) => {
      try {
        const data: ProcessingEvent = JSON.parse(e.data);
        onEvent(data);
      } catch (err) {
        console.error(`[SSE] Error parsing ${eventType}:`, err);
      }
    });
  });

  eventSource.onerror = (err) => {
    console.warn('[SSE] EventSource connection error or disconnect:', err);
    if (onError) onError(err);
  };

  return {
    close: () => {
      eventSource.close();
    },
  };
}
