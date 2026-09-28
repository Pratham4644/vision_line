# Streaming Architecture & Low-Latency Pipeline

## 1. End-to-End Pipeline
```
[Camera Source: RTSP/MJPEG]
       |
       | RTSP over TCP (-stimeout 5000000)
       v
[FFmpeg Ingestion Engine]
  - Flags: -fflags nobuffer -flags low_delay
  - Transcode: -c:v copy (for H264) OR libx264 ultrafast zerolatency (for MJPEG)
       |
       | RTSP over TCP
       v
[MediaMTX v1.21.1 Core]
  - Path: dynamic registration (all_others: { source: publisher })
  - WebRTC WHEP HTTP: :8889
  - ICE UDP: :8189
       |
       | WebRTC (SRTP over UDP with STUN)
       v
[Browser WHEP WebRTC Player]
  - Handshake: POST /<path>/whep (SDP Offer -> 201 Created SDP Answer)
  - Latency: ~150ms - 400ms end-to-end
```

## 2. Low-Latency Guarantees
- **No Frame Queuing**: Buffer queues are disabled using `-fflags nobuffer`. Stale frames are dropped rather than buffered.
- **TCP Ingestion**: Unreliable wireless connections drop packets; by enforcing `-rtsp_transport tcp` between camera/edge and MediaMTX, packet fragmentation and RTP loss are prevented.
- **Direct Codec Passthrough**: Standard IP cameras streaming H.264 stream without CPU transcoding overhead (`-c:v copy`), preserving VM compute and RAM.
- **WebRTC WHEP Signaling**: Zero proprietary plugins needed. Modern browsers negotiate audio/video tracks directly using native WebRTC RTCPeerConnection.

## 3. Dynamic Stream Paths
No camera paths are hardcoded. Cameras register arbitrary path identifiers in MongoDB (e.g., `gate-camera`, `warehouse-south`, `cam-test-1`). The backend returns dynamic WHEP URLs (`https://camera1.koreacentral.cloudapp.azure.com/webrtc/<mediaMtxPath>/whep`) to frontend consumers.
