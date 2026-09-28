import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Filter,
  RefreshCw,
  Search,
  Shield,
} from 'lucide-react';
import { AuditLogEntry } from '../types';
import { api } from '../services/api';

interface LogsResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export const Logs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(25);
  const [resourceType, setResourceType] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Log Detail Modal
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);

  const loadLogs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<LogsResponse>('/logs', {
        page,
        page_size: pageSize,
        resource_type: resourceType || undefined,
        action: actionFilter || undefined,
      });
      setLogs(data?.items || []);
      setTotal(data?.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [page, resourceType, actionFilter]);

  const totalPages = Math.ceil(total / pageSize) || 1;

  const getActionBadgeColor = (action: string) => {
    const a = action.toLowerCase();
    if (a.includes('create') || a.includes('login')) return 'bg-emerald-950/60 text-emerald-400 border-emerald-800';
    if (a.includes('update') || a.includes('edit') || a.includes('restart')) return 'bg-amber-950/60 text-amber-400 border-amber-800';
    if (a.includes('delete') || a.includes('disable')) return 'bg-rose-950/60 text-rose-400 border-rose-800';
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Audit &amp; Security Logs</h1>
          <p className="text-sm text-slate-400 mt-1">
            Immutable audit record of all administrative, configuration, and security operations
          </p>
        </div>
        <button
          onClick={loadLogs}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-medium text-slate-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh Logs
        </button>
      </div>

      {/* Filters Bar */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Filters:</span>
          </div>

          <select
            value={resourceType}
            onChange={(e) => {
              setResourceType(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Resource Types</option>
            <option value="camera">Camera</option>
            <option value="site">Site</option>
            <option value="user">User</option>
            <option value="organization">Organization</option>
            <option value="auth">Auth</option>
            <option value="stream">Stream</option>
          </select>

          <input
            type="text"
            placeholder="Filter by action (e.g. create, update)..."
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="text-xs text-slate-500 font-mono">
          Showing {logs.length} of {total} events
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Logs Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
              <tr>
                <th className="p-4">Timestamp</th>
                <th className="p-4">Resource</th>
                <th className="p-4">Action</th>
                <th className="p-4">Target Resource ID</th>
                <th className="p-4">Actor</th>
                <th className="p-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-slate-500">
                    {isLoading ? 'Loading logs...' : 'No audit records found matching your filters.'}
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="p-4 font-mono text-slate-400 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="p-4 font-mono uppercase text-slate-300">
                      <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">
                        {log.resource_type}
                      </span>
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[10px] border ${getActionBadgeColor(
                          log.action,
                        )}`}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-slate-400 max-w-[150px] truncate">
                      {log.resource_id || '—'}
                    </td>
                    <td className="p-4 font-mono text-slate-400 max-w-[150px] truncate">
                      {log.user_id ? log.user_id.slice(0, 12) + '...' : 'System'}
                    </td>
                    <td className="p-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="text-emerald-400 hover:underline font-mono text-xs"
                      >
                        View &rarr;
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-slate-950/60 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 text-slate-300"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 text-slate-300"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Log Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" />
                Audit Record Details
              </h2>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-slate-400 hover:text-white"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px]">
                <div>
                  <span className="text-slate-500">Record ID:</span>
                  <p className="text-slate-200 truncate">{selectedLog.id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Timestamp:</span>
                  <p className="text-slate-200 truncate">{new Date(selectedLog.timestamp).toISOString()}</p>
                </div>
                <div>
                  <span className="text-slate-500">Resource:</span>
                  <p className="text-slate-200">{selectedLog.resource_type}</p>
                </div>
                <div>
                  <span className="text-slate-500">Action:</span>
                  <p className="text-slate-200">{selectedLog.action}</p>
                </div>
                <div>
                  <span className="text-slate-500">Resource ID:</span>
                  <p className="text-slate-200 truncate">{selectedLog.resource_id || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Request ID:</span>
                  <p className="text-slate-200 truncate">{selectedLog.request_id || 'N/A'}</p>
                </div>
              </div>

              <div>
                <p className="text-slate-400 uppercase font-semibold text-[10px] mb-1">Details JSON Payload</p>
                <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto max-h-60">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              </div>
            </div>

            <div className="pt-3 flex justify-end border-t border-slate-800">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
