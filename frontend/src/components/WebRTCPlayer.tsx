import React, { useEffect, useRef, useState } from 'react';
import { Maximize2, Minimize2, Play, RefreshCw, Volume2, VolumeX, Wifi, WifiOff } from 'lucide-react';

interface WebRTCPlayerProps {
  whepUrl: string;
  readerCredentials?: {
    username: string;
    password?: string;
  };
  cameraName?: string;
  autoPlay?: boolean;
}

export const WebRTCPlayer: React.FC<WebRTCPlayerProps> = ({
  whepUrl,
  readerCredentials,
  cameraName = 'Camera Stream',
  autoPlay = true,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);

  const [connectionState, setConnectionState] = useState<'idle' | 'connecting' | 'connected' | 'failed' | 'disconnected'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState<boolean>(true);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [reconnectCount, setReconnectCount] = useState<number>(0);

  const startStream = async () => {
    if (!whepUrl) {
      setErrorMessage('No streaming URL provided.');
      return;
    }

    setConnectionState('connecting');
    setErrorMessage(null);

    // Clean up previous peer connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }

    try {
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
      });
      pcRef.current = pc;

      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          videoRef.current.play().catch(() => {
            // Autoplay with audio might require user gesture, fallback to muted
            if (videoRef.current) {
              videoRef.current.muted = true;
              setIsMuted(true);
              videoRef.current.play().catch(() => {});
            }
          });
        }
      };

      pc.oniceconnectionstatechange = () => {
        if (!pc) return;
        const state = pc.iceConnectionState;
        if (state === 'connected' || state === 'completed') {
          setConnectionState('connected');
          setErrorMessage(null);
        } else if (state === 'failed' || state === 'disconnected') {
          setConnectionState('failed');
          setErrorMessage('ICE connection failed. Camera may be offline or unreachable.');
        }
      };

      pc.onconnectionstatechange = () => {
        if (!pc) return;
        if (pc.connectionState === 'connected') {
          setConnectionState('connected');
        } else if (pc.connectionState === 'failed') {
          setConnectionState('failed');
          setErrorMessage('WebRTC session terminated by server.');
        }
      };

      // 1. Create SDP Offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Wait for ICE gathering to complete or send immediately
      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve();
        } else {
          const checkState = () => {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', checkState);
              resolve();
            }
          };
          pc.addEventListener('icegatheringstatechange', checkState);
          // 2 second fallback
          setTimeout(resolve, 2000);
        }
      });

      // 2. Post SDP Offer to MediaMTX WHEP endpoint
      const headers: Record<string, string> = {
        'Content-Type': 'application/sdp',
      };
      if (readerCredentials && readerCredentials.username) {
        const token = btoa(`${readerCredentials.username}:${readerCredentials.password || ''}`);
        headers['Authorization'] = `Basic ${token}`;
      }

      const response = await fetch(whepUrl, {
        method: 'POST',
        headers,
        body: pc.localDescription?.sdp,
      });

      if (!response.ok) {
        throw new Error(`MediaMTX WHEP error (${response.status}): Stream not available yet or offline.`);
      }

      // 3. Receive SDP Answer
      const answerSdp = await response.text();
      await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: answerSdp }));
    } catch (err: any) {
      setConnectionState('failed');
      setErrorMessage(err.message || 'Failed to establish WebRTC connection');
    }
  };

  useEffect(() => {
    if (autoPlay) {
      startStream();
    }

    return () => {
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
    };
  }, [whepUrl, reconnectCount]);

  const handleReconnect = () => {
    setReconnectCount((c) => c + 1);
  };

  const toggleMute = () => {
    if (videoRef.current) {
      const nextMuted = !videoRef.current.muted;
      videoRef.current.muted = nextMuted;
      setIsMuted(nextMuted);
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full aspect-video bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl flex items-center justify-center group"
    >
      {/* Video Element */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={isMuted}
        className="w-full h-full object-contain bg-black"
      />

      {/* Top Header Overlay */}
      <div className="absolute top-0 inset-x-0 p-4 bg-gradient-to-b from-black/80 via-black/40 to-transparent flex items-center justify-between opacity-90 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center gap-2.5">
          <span className="font-semibold text-sm text-white tracking-wide">{cameraName}</span>
          <span className="text-xs text-slate-400 font-mono bg-black/50 px-2 py-0.5 rounded border border-slate-700/50">
            WebRTC (Low Latency)
          </span>
        </div>

        <div className="flex items-center gap-2">
          {connectionState === 'connected' ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          ) : connectionState === 'connecting' ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/80 text-amber-400 border border-amber-800/80">
              <RefreshCw className="w-3 h-3 animate-spin" />
              CONNECTING
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-950/80 text-rose-400 border border-rose-800/80">
              <WifiOff className="w-3 h-3" />
              OFFLINE
            </span>
          )}
        </div>
      </div>

      {/* Center Connecting / Error Overlay */}
      {connectionState === 'connecting' && (
        <div className="absolute inset-0 bg-slate-950/80 flex flex-col items-center justify-center text-center p-6 gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
          <p className="text-sm font-medium text-slate-300">Negotiating WebRTC stream...</p>
          <p className="text-xs text-slate-500 font-mono max-w-sm truncate">{whepUrl}</p>
        </div>
      )}

      {connectionState === 'failed' && (
        <div className="absolute inset-0 bg-slate-950/90 flex flex-col items-center justify-center text-center p-6 gap-3">
          <div className="p-3 rounded-full bg-rose-950/50 text-rose-400 border border-rose-800/50">
            <WifiOff className="w-6 h-6" />
          </div>
          <p className="text-base font-semibold text-slate-200">Stream Not Available</p>
          <p className="text-xs text-rose-400 max-w-md">{errorMessage}</p>
          <button
            onClick={handleReconnect}
            className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Connection
          </button>
        </div>
      )}

      {/* Bottom Controls Bar */}
      <div className="absolute bottom-0 inset-x-0 p-3 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center gap-3">
          <button
            onClick={handleReconnect}
            title="Reconnect Stream"
            className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={toggleMute}
            title={isMuted ? 'Unmute' : 'Mute'}
            className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
};
