import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Camera as CameraIcon,
  CheckCircle2,
  Compass,
  Plus,
  Radio,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { Camera, AuditLogEntry, Site } from '../types';
import { api } from '../services/api';
import { StatCard } from '../components/StatCard';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';

export const Dashboard: React.FC = () => {
  const { user, organization } = useAuth();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [recentLogs, setRecentLogs] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [camsData, sitesData] = await Promise.all([
        api.get<Camera[]>('/cameras'),
        api.get<Site[]>('/sites'),
      ]);
      setCameras(camsData || []);
      setSites(sitesData || []);

      // Logs may 403 for non-admin users — gracefully handle
      try {
        const logsData = await api.get<{ items: AuditLogEntry[] }>('/logs', { page_size: 10 });
        setRecentLogs(logsData?.items || []);
      } catch {
        setRecentLogs([]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const totalCameras = cameras.length;
  const onlineCameras = cameras.filter((c) => c.status === 'ONLINE').length;
  const offlineCameras = cameras.filter((c) => c.status === 'OFFLINE').length;
  const degradedCameras = cameras.filter((c) => c.status === 'DEGRADED' || c.status === 'UNKNOWN').length;
  const activeStreams = cameras.filter((c) => c.enabled).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {organization ? `${organization.name}` : 'Security Dashboard'}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Multi-site camera streaming overview &amp; tenant telemetry
          </p>
        </div>
        <button
          onClick={loadDashboardData}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-medium text-slate-300 hover:text-white hover:border-slate-700 transition-colors shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Onboarding State: No Sites Yet */}
      {sites.length === 0 && !isLoading && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-emerald-950/50 via-slate-900 to-slate-900 border border-emerald-800/40 shadow-xl">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-400 border border-emerald-700/50">
                Onboarding Step 1
              </span>
              <h3 className="text-base font-bold text-white mt-2">
                Set up your first monitored site
              </h3>
              <p className="text-xs text-slate-400 mt-1 max-w-xl leading-relaxed">
                Sites represent your physical locations (such as a plant, warehouse, or corporate office). Grouping your cameras by site keeps your streams organized.
              </p>
            </div>
            <Link
              to="/sites"
              className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 flex items-center gap-2 shrink-0 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create First Site
            </Link>
          </div>
        </div>
      )}

      {/* Onboarding State: Sites exist but no cameras yet */}
      {sites.length > 0 && cameras.length === 0 && !isLoading && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-950/40 via-slate-900 to-slate-900 border border-blue-800/40 shadow-xl">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-900/60 text-blue-400 border border-blue-700/50">
                Onboarding Step 2
              </span>
              <h3 className="text-base font-bold text-white mt-2">
                Connect your first RTSP camera
              </h3>
              <p className="text-xs text-slate-400 mt-1 max-w-xl leading-relaxed">
                You have {sites.length} site(s) configured. Add your IP camera RTSP stream to begin WebRTC low-latency streaming and recording.
              </p>
            </div>
            <Link
              to="/cameras"
              className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 flex items-center gap-2 shrink-0 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Your First Camera
            </Link>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard title="Total Cameras" value={totalCameras} icon={CameraIcon} color="slate" />
        <StatCard title="Online" value={onlineCameras} icon={CheckCircle2} color="emerald" />
        <StatCard title="Offline" value={offlineCameras} icon={XCircle} color="rose" />
        <StatCard title="Degraded" value={degradedCameras} icon={AlertTriangle} color="amber" />
        <StatCard title="Monitored Sites" value={sites.length} icon={Compass} color="blue" />
        <StatCard title="Active Streams" value={activeStreams} icon={Radio} color="emerald" />
      </div>

      {/* Camera Quick View */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white tracking-tight">Camera Overview</h2>
          <Link to="/cameras" className="text-xs text-emerald-400 hover:underline">
            View all cameras ({totalCameras}) &rarr;
          </Link>
        </div>

        {cameras.length === 0 ? (
          <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80">
            <CameraIcon className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400">No cameras registered yet.</p>
            <Link
              to="/cameras"
              className="mt-3 inline-block px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
            >
              Add Your First Camera
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {cameras.slice(0, 6).map((cam) => (
              <Link
                key={cam.id}
                to={`/cameras/${cam.id}`}
                className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400">
                    <CameraIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-200">{cam.name}</p>
                    <p className="text-[11px] text-slate-500 font-mono">/{cam.media_path}</p>
                  </div>
                </div>
                <StatusBadge status={cam.status} size="sm" />
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Recent Activity Audit Feed */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white tracking-tight">Recent System Activity</h2>
          <Link to="/logs" className="text-xs text-emerald-400 hover:underline">
            Full Audit Logs &rarr;
          </Link>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-800/60">
          {recentLogs.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">No recent activity logged.</div>
          ) : (
            recentLogs.map((log) => (
              <div key={log.id} className="p-4 flex items-center justify-between text-xs hover:bg-slate-800/30 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="font-mono px-2 py-0.5 rounded text-[10px] font-semibold border bg-slate-800 text-slate-300 border-slate-700">
                    {log.resource_type}
                  </span>
                  <span className="font-semibold text-slate-300">{log.action}</span>
                  <span className="text-slate-400">{log.resource_id || ''}</span>
                </div>
                <span className="text-slate-500 font-mono text-[11px] shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
