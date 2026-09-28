import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Copy,
  Power,
  RefreshCw,
  Shield,
} from 'lucide-react';
import { CameraDetail as CameraDetailType, CameraPlayback, Site } from '../types';
import { api } from '../services/api';
import { WebRTCPlayer } from '../components/WebRTCPlayer';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';

export const CameraDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [camera, setCamera] = useState<CameraDetailType | null>(null);
  const [playback, setPlayback] = useState<CameraPlayback | null>(null);
  const [site, setSite] = useState<Site | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Connection test state
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  const loadCamera = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<CameraDetailType>(`/cameras/${id}`);
      setCamera(data);

      // Load playback info if enabled
      if (data?.enabled) {
        try {
          const pb = await api.get<CameraPlayback>(`/cameras/${id}/playback`);
          setPlayback(pb);
        } catch {
          setPlayback(null);
        }
      }

      if (data?.site_id) {
        try {
          const s = await api.get<Site>(`/sites/${data.site_id}`);
          setSite(s);
        } catch {
          // ignore site fetch error
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load camera');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCamera();
  }, [id]);

  const handleTestConnection = async () => {
    if (!id) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await api.post<{ ok: boolean; message: string }>(`/cameras/${id}/test`);
      setTestResult(res);
    } catch (err: any) {
      setTestResult({ ok: false, message: err.message || 'Connection test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleToggleEnable = async () => {
    if (!camera) return;
    try {
      const action = camera.enabled ? 'disable' : 'enable';
      await api.post(`/cameras/${camera.id}/${action}`);
      loadCamera();
    } catch (err: any) {
      alert(`Toggle failed: ${err.message}`);
    }
  };

  const handleRestart = async () => {
    if (!camera) return;
    try {
      await api.post(`/cameras/${camera.id}/restart`);
      alert('Stream ingestion restart initiated.');
      loadCamera();
    } catch (err: any) {
      alert(`Restart failed: ${err.message}`);
    }
  };

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedUrl(label);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  if (isLoading) {
    return (
      <div className="h-96 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
          <p className="text-xs font-mono text-slate-400">Loading camera telemetry...</p>
        </div>
      </div>
    );
  }

  if (error || !camera) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-rose-400 text-sm">{error || 'Camera not found'}</p>
        <Link to="/cameras" className="text-xs text-emerald-400 hover:underline">
          &larr; Back to cameras list
        </Link>
      </div>
    );
  }

  const whepUrl = playback?.whep_url || camera.whep_url || '';
  const rtspUrl = playback?.rtsp_url || camera.rtsp_playback_url || '';

  return (
    <div className="space-y-6">
      {/* Back button & Title header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/cameras')}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white tracking-tight">{camera.name}</h1>
              <StatusBadge status={camera.status} />
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Site: <span className="text-slate-300 font-semibold">{site?.name || camera.site_id.slice(0, 8)}</span> • Path: <span className="font-mono text-emerald-400">/{camera.media_path}</span>
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          {hasPermission('camera:read') && (
            <button
              onClick={handleTestConnection}
              disabled={isTesting}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-medium text-slate-300 hover:text-white transition-colors"
            >
              <Activity className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
              {isTesting ? 'Testing Link...' : 'Test Source Probe'}
            </button>
          )}

          {hasPermission('camera:update') && (
            <>
              <button
                onClick={handleRestart}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-medium text-slate-300 hover:text-white transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Restart Stream
              </button>

              <button
                onClick={handleToggleEnable}
                className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  camera.enabled
                    ? 'bg-amber-950/40 border-amber-800/80 text-amber-300 hover:bg-amber-900/60'
                    : 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300 hover:bg-emerald-900/60'
                }`}
              >
                <Power className="w-3.5 h-3.5" />
                {camera.enabled ? 'Disable Camera' : 'Enable Camera'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Connection Test Banner if executed */}
      {testResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between ${
            testResult.ok
              ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
              : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {testResult.ok ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-rose-400" />}
            <span className="font-medium">{testResult.message}</span>
          </div>
          <button onClick={() => setTestResult(null)} className="text-slate-400 hover:text-white">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid: Player + Telemetry */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: WebRTC Player */}
        <div className="lg:col-span-2 space-y-4">
          <WebRTCPlayer
            whepUrl={whepUrl}
            readerCredentials={playback?.reader_credentials}
            cameraName={camera.name}
          />

          {/* Quick Stream Endpoints Card */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Integration Endpoints (MediaMTX)
            </h3>
            <div className="space-y-2 text-xs font-mono">
              {whepUrl && (
                <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-slate-400">WebRTC WHEP:</span>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 truncate max-w-sm">{whepUrl}</span>
                    <button
                      onClick={() => handleCopy(whepUrl, 'webrtc')}
                      className="p-1 hover:text-white text-slate-500"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}

              {rtspUrl && (
                <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-slate-400">RTSP Relay:</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300 truncate max-w-sm">{rtspUrl}</span>
                    <button
                      onClick={() => handleCopy(rtspUrl, 'rtsp')}
                      className="p-1 hover:text-white text-slate-500"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
            {copiedUrl && <p className="text-[11px] text-emerald-400">Copied {copiedUrl} URL to clipboard!</p>}
          </div>
        </div>

        {/* Right Col: Telemetry & Spec */}
        <div className="space-y-6">
          <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
            <h2 className="text-sm font-bold text-white tracking-tight border-b border-slate-800 pb-3">
              Camera Configuration
            </h2>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Status:</span>
                <StatusBadge status={camera.status} size="sm" />
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Configured FPS:</span>
                <span className="font-mono text-slate-200">{camera.configured_fps || 15} fps</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Resolution:</span>
                <span className="font-mono text-slate-200">{camera.configured_resolution || 'Auto'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Protocol:</span>
                <span className="font-mono text-slate-200">{camera.source_protocol}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Ingest Mode:</span>
                <span className="text-slate-200">{camera.ingest_mode}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Credentials:</span>
                <span className="text-slate-200 font-mono">
                  {camera.has_credentials ? 'Encrypted' : 'None'}
                </span>
              </div>
            </div>
          </div>

          {playback && (
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
              <h2 className="text-sm font-bold text-white tracking-tight">Live Media State</h2>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Control:</span>
                  <span className="font-mono text-slate-200">{playback.control_state}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Media:</span>
                  <span className="font-mono text-slate-200">{playback.media_state}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Ingest:</span>
                  <span className="font-mono text-slate-200">{playback.ingest_state}</span>
                </div>
              </div>
            </div>
          )}

          <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
            <h2 className="text-sm font-bold text-white tracking-tight">Security & Ingestion</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Video is ingested over TCP with low-latency flags (<span className="font-mono text-slate-300">-fflags nobuffer</span>) directly into MediaMTX, terminating into WebRTC WHEP for browser playback without buffering.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
