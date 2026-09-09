import React, { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, PageId } from './components/layout/Sidebar';
import { Overview } from './pages/Overview';
import { LiveAnalysis } from './pages/LiveAnalysis';
import { Entities } from './pages/Entities';
import { Evidence } from './pages/Evidence';
import { Risk } from './pages/Risk';
import { Verification } from './pages/Verification';
import { Research } from './pages/Research';
import { Clearance } from './pages/Clearance';
import { Timeline } from './pages/Timeline';
import { Reports } from './pages/Reports';
import { Orchestration } from './pages/Orchestration';
import { useAnalysisEvents } from './hooks/useAnalysisEvents';
import { useLiveMetrics } from './hooks/useLiveMetrics';
import { api } from './services/api';
import { Production, Entity, AvailableVideo } from './types';

// Default initial demo entities
const INITIAL_DEMO_ENTITIES: Entity[] = [
  {
    id: 'ent_01',
    production_id: 'prod_demo',
    name: 'Cadbury Dairy Milk',
    entity_type: 'BRAND',
    sources: ['VISUAL'],
    confidence: 0.98,
    scene: 1,
    timestamp: 2.5,
    context: 'Cadbury chocolate bar with signature purple packaging held by actor.',
    frame_path: 'frames/scene01_00025.jpg',
    clearance_type: 'TRADEMARK',
    risk_level: 'HIGH',
    risk_score: 88,
    rights_holder: 'CADBURY UK LIMITED',
    evidence_ids: ['evi_01'],
    verification_status: 'CONFIRMED',
    resolution_status: 'BLUR_REQUIRED',
    created_at: new Date().toISOString(),
  },
  {
    id: 'ent_02',
    production_id: 'prod_demo',
    name: 'Sony Bravia Display',
    entity_type: 'PRODUCT',
    sources: ['VISUAL'],
    confidence: 0.92,
    scene: 1,
    timestamp: 6.8,
    context: 'Television screen with visible Sony logo in background living room.',
    frame_path: 'frames/scene01_00068.jpg',
    clearance_type: 'TRADEMARK',
    risk_level: 'MEDIUM',
    risk_score: 55,
    rights_holder: 'Sony Group Corporation',
    evidence_ids: ['evi_02'],
    verification_status: 'CONFIRMED',
    resolution_status: 'LICENSE_REQUIRED',
    created_at: new Date().toISOString(),
  },
  {
    id: 'ent_03',
    production_id: 'prod_demo',
    name: 'Geometric Symphony #4',
    entity_type: 'ARTWORK',
    sources: ['VISUAL'],
    confidence: 0.89,
    scene: 1,
    timestamp: 11.4,
    context: 'Framed abstract painting in background booth.',
    frame_path: 'frames/scene01_00114.jpg',
    clearance_type: 'COPYRIGHT',
    risk_level: 'MEDIUM',
    risk_score: 48,
    rights_holder: 'Estate of Elena Vance',
    evidence_ids: ['evi_03'],
    verification_status: 'UNVERIFIED',
    resolution_status: 'LICENSE_REQUIRED',
    created_at: new Date().toISOString(),
  },
];

export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>('overview');
  const [currentProduction, setCurrentProduction] = useState<Production | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [entities, setEntities] = useState<Entity[]>(INITIAL_DEMO_ENTITIES);
  const [selectedVideo, setSelectedVideo] = useState<string>('test_video1.mp4');
  const [availableVideos, setAvailableVideos] = useState<AvailableVideo[]>([]);

  // Load available videos from workspace on mount
  useEffect(() => {
    api.getAvailableVideos()
      .then((vids) => {
        if (vids && vids.length > 0) {
          setAvailableVideos(vids);
          const rec = vids.find((v) => v.is_recommended);
          if (rec) setSelectedVideo(rec.filename);
          else setSelectedVideo(vids[0].filename);
        }
      })
      .catch(() => {});
  }, []);

  // Subscribe to real-time SSE stream when activeJobId is set
  const {
    events,
    isConnected,
    currentProgress,
    currentStage,
    stages,
    lastEvent,
    clearEvents,
  } = useAnalysisEvents(currentProduction?.id, activeJobId || undefined);

  // Compute live metrics from actual event streams and entities
  const metrics = useLiveMetrics(events, entities);

  // Video switch handler
  const handleSelectVideo = async (vidName: string) => {
    setSelectedVideo(vidName);
    if (currentProduction?.id) {
      try {
        await api.registerFootage(currentProduction.id, vidName);
        setCurrentProduction((prev) => prev ? { ...prev, footage_path: vidName } : null);
      } catch (err) {
        console.warn('Could not update footage path on backend:', err);
      }
    }
  };

  // React to incoming events to enrich or register entities in real-time
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.event_type === 'ENTITY_DETECTED' && lastEvent.entity_name) {
      setEntities((prev) => {
        const idx = prev.findIndex((e) => e.name.toLowerCase() === lastEvent.entity_name?.toLowerCase());
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            confidence: Math.max(updated[idx].confidence, lastEvent.confidence ?? updated[idx].confidence),
            timestamp: lastEvent.video_timestamp ?? updated[idx].timestamp,
            scene: lastEvent.scene_number ?? updated[idx].scene,
            frame_path: lastEvent.frame_path || updated[idx].frame_path,
          };
          return updated;
        }
        const newEntity: Entity = {
          id: lastEvent.entity_id || `ent_${Date.now()}`,
          production_id: lastEvent.production_id,
          name: lastEvent.entity_name,
          entity_type: (lastEvent.entity_type as any) || 'BRAND',
          sources: ['VISUAL'],
          confidence: lastEvent.confidence || 0.94,
          timestamp: lastEvent.video_timestamp,
          scene: lastEvent.scene_number || 1,
          frame_path: lastEvent.frame_path,
          clearance_type: 'TRADEMARK',
          risk_level: (lastEvent.risk_level as any) || 'UNKNOWN',
          risk_score: lastEvent.risk_score || 0,
          rights_holder: 'Pending Verification',
          evidence_ids: [],
          verification_status: 'UNVERIFIED',
          resolution_status: 'PENDING',
          created_at: new Date().toISOString(),
        };
        return [...prev, newEntity];
      });
    } else if (lastEvent.event_type === 'VISUAL_ONLY_DISCOVERED' && lastEvent.entity_name) {
      setEntities((prev) => {
        const idx = prev.findIndex((e) => e.name.toLowerCase() === lastEvent.entity_name?.toLowerCase());
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            classification: 'VISUAL_ONLY',
            sources: ['VISUAL'],
            risk_level: 'HIGH',
            risk_score: Math.max(updated[idx].risk_score, 85),
          };
          return updated;
        }
        return prev;
      });
    } else if (lastEvent.event_type === 'RESEARCH_COMPLETED' && lastEvent.entity_name) {
      // Parallel API completed corporate research
      setEntities((prev) => {
        return prev.map((e) => {
          if (e.id === lastEvent.entity_id || e.name.toLowerCase() === lastEvent.entity_name?.toLowerCase()) {
            const rightsHolder = lastEvent.metadata?.candidate_rights_holder || lastEvent.message?.split("'")[3] || e.rights_holder;
            return {
              ...e,
              rights_holder: rightsHolder,
            };
          }
          return e;
        });
      });
    } else if (lastEvent.event_type === 'RISK_CALCULATED' && lastEvent.entity_id) {
      setEntities((prev) => {
        return prev.map((e) => {
          if (e.id === lastEvent.entity_id || e.name.toLowerCase() === lastEvent.entity_name?.toLowerCase()) {
            return {
              ...e,
              risk_level: (lastEvent.risk_level as any) || e.risk_level,
              risk_score: lastEvent.risk_score !== undefined ? lastEvent.risk_score : e.risk_score,
            };
          }
          return e;
        });
      });
    } else if (lastEvent.event_type === 'ANALYSIS_COMPLETED' && currentProduction?.id) {
      // Final sync with backend database
      api.getEntities(currentProduction.id).then((fresh) => {
        if (fresh && fresh.length > 0) {
          setEntities(fresh);
        }
      }).catch((err) => console.warn('Could not fetch finalized entities:', err));
    }
  }, [lastEvent, currentProduction?.id]);

  // Handle sample production bootstrap with selected video
  const handleCreateSampleProduction = async (videoName?: string) => {
    const chosenVideo = videoName || selectedVideo;
    try {
      const prod = await api.createProduction({
        title: chosenVideo.includes('1') ? 'Cadbury & Consumer Brand Showcase' : 'Neon Horizon: Screenplay & Footage Pre-Clearance',
        description: 'Agentic pre-clearance benchmark comparing screenplay vs video footage',
        director: 'Alex Rivera',
        studio: 'Aethelgard Pictures',
        budget_tier: 'Studio Feature',
      });

      // Upload demo script text
      await api.uploadScriptText(
        prod.id,
        'SCENE 01 - INT. LIVING ROOM - DAY\nArjun enters the room, picks up a generic snack and sits down on the sofa.'
      );

      // Register selected video footage
      await api.registerFootage(prod.id, chosenVideo);

      const updated = await api.getProduction(prod.id);
      setCurrentProduction(updated);
      return updated;
    } catch (e) {
      console.warn('Using local demo production fallback:', e);
      const fallback: Production = {
        id: 'prod_demo_local',
        title: chosenVideo.includes('1') ? 'Cadbury & Consumer Brand Showcase' : 'Neon Horizon Pre-Clearance',
        description: 'Agentic pre-clearance benchmark comparing screenplay vs video footage',
        director: 'Alex Rivera',
        studio: 'Aethelgard Pictures',
        budget_tier: 'Studio Feature',
        status: 'READY_FOR_ANALYSIS' as any,
        footage_path: chosenVideo,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setCurrentProduction(fallback);
      return fallback;
    }
  };

  // Trigger real backend analysis job on selected video
  const handleStartAnalysis = async () => {
    // Reset any old findings and clear events to prevent model/visual confusion!
    setEntities([]);
    clearEvents();

    let prod = currentProduction;
    if (!prod) {
      prod = await handleCreateSampleProduction(selectedVideo);
    } else {
      // Ensure the selected video is registered for this production
      try {
        await api.registerFootage(prod.id, selectedVideo);
      } catch (err) {
        console.warn('Could not update footage registration:', err);
      }
    }
    const prodId = prod?.id || 'prod_demo_local';

    try {
      const job = await api.startAnalysis(prodId);
      setActiveJobId(job.job_id);
      setCurrentPage('live-analysis');
    } catch (e) {
      console.warn('Running in standalone mode with job fallback:', e);
      setActiveJobId(`job_${Date.now().toString(16)}`);
      setCurrentPage('live-analysis');
    }
  };

  // Cancel active backend analysis job
  const handleCancelAnalysis = async () => {
    if (currentProduction && activeJobId) {
      try {
        await api.cancelAnalysis(currentProduction.id, activeJobId);
      } catch (e) {
        console.error('Failed to cancel analysis job:', e);
      }
    }
  };

  return (
    <div className="app-container font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentPage={currentPage}
        onSelectPage={(page) => setCurrentPage(page)}
        visualOnlyCount={metrics.visualOnlyCount}
        highRiskCount={metrics.highRiskCount}
      />

      {/* Main Content Viewport */}
      <div className="main-content">
        <Header
          currentProduction={currentProduction}
          activeJobId={activeJobId}
          isConnected={isConnected}
          selectedVideo={selectedVideo}
          availableVideos={availableVideos}
          onSelectVideo={handleSelectVideo}
        />

        <main className="content-viewport">
          {currentPage === 'overview' && (
            <Overview
              currentProduction={currentProduction}
              metrics={metrics}
              entities={entities}
              onStartAnalysis={handleStartAnalysis}
              onCreateSampleProduction={() => handleCreateSampleProduction(selectedVideo)}
              isAnalyzing={isConnected}
              selectedVideo={selectedVideo}
              availableVideos={availableVideos}
              onSelectVideo={handleSelectVideo}
            />
          )}

          {currentPage === 'orchestration' && (
            <Orchestration currentProduction={currentProduction} />
          )}

          {currentPage === 'live-analysis' && (
            <LiveAnalysis
              currentProduction={currentProduction}
              activeJobId={activeJobId}
              isConnected={isConnected}
              events={events}
              stages={stages}
              currentStage={currentStage}
              currentProgress={currentProgress}
              metrics={metrics}
              entities={entities}
              onStartAnalysis={handleStartAnalysis}
              onCancelAnalysis={handleCancelAnalysis}
              onClearEvents={clearEvents}
              selectedVideo={selectedVideo}
              availableVideos={availableVideos}
              onSelectVideo={handleSelectVideo}
            />
          )}

          {currentPage === 'entities' && (
            <Entities
              entities={entities}
              onSelectEntity={(ent) => {
                setCurrentPage('live-analysis');
              }}
            />
          )}

          {currentPage === 'evidence' && <Evidence entities={entities} />}

          {currentPage === 'risk' && <Risk entities={entities} />}

          {currentPage === 'verification' && (
            <Verification entities={entities} productionId={currentProduction?.id} />
          )}

          {currentPage === 'research' && <Research entities={entities} />}

          {currentPage === 'clearance' && (
            <Clearance entities={entities} productionId={currentProduction?.id} />
          )}

          {currentPage === 'timeline' && <Timeline entities={entities} />}

          {currentPage === 'reports' && (
            <Reports currentProduction={currentProduction} entities={entities} />
          )}
        </main>
      </div>
    </div>
  );
};
