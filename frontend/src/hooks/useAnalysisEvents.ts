import { useState, useEffect, useCallback } from 'react';
import { ProcessingEvent, StageState, StageStatus } from '../types';
import { subscribeToAnalysisEvents } from '../services/events';

export function useAnalysisEvents(productionId?: string, jobId?: string) {
  const [events, setEvents] = useState<ProcessingEvent[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [currentProgress, setCurrentProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>('Screenplay Extraction');
  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [lastEvent, setLastEvent] = useState<ProcessingEvent | null>(null);

  const handleNewEvent = useCallback((event: ProcessingEvent) => {
    setLastEvent(event);
    setEvents((prev) => [...prev, event]);
    
    if (event.progress !== undefined) {
      setCurrentProgress(event.progress);
    }
    
    if (event.stage) {
      setCurrentStage(event.stage);
      setStages((prev) => {
        const existing = prev[event.stage!] || {
          stage: event.stage!,
          status: 'WAITING' as StageStatus,
          progress: 0,
        };

        let updatedStatus: StageStatus = existing.status;
        if (event.event_type === 'STAGE_STARTED') updatedStatus = 'RUNNING';
        if (event.event_type === 'STAGE_COMPLETED') updatedStatus = 'COMPLETED';
        if (event.event_type === 'ANALYSIS_FAILED') updatedStatus = 'FAILED';

        return {
          ...prev,
          [event.stage!]: {
            ...existing,
            status: updatedStatus,
            progress: event.progress,
            latest_event: event.message,
          },
        };
      });
    }
  }, []);

  useEffect(() => {
    if (!productionId || !jobId) {
      setIsConnected(false);
      return;
    }

    setIsConnected(true);
    const conn = subscribeToAnalysisEvents(
      productionId,
      jobId,
      (event) => handleNewEvent(event),
      (err) => {
        setIsConnected(false);
      }
    );

    return () => {
      conn.close();
      setIsConnected(false);
    };
  }, [productionId, jobId, handleNewEvent]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setCurrentProgress(0);
    setLastEvent(null);
  }, []);

  return {
    events,
    isConnected,
    currentProgress,
    currentStage,
    stages,
    lastEvent,
    clearEvents,
  };
}
