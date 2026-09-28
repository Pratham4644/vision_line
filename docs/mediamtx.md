# MediaMTX Configuration and Operations

## 1. Verified Working Configuration (MediaMTX v1.21.1)
The canonical MediaMTX configuration is stored in `streaming/mediamtx/mediamtx.yml`:

```yaml
logLevel: info
logDestinations: [stdout]

# RTSP Settings
rtsp: true
rtspAddress: :8554
protocols: [tcp]
rtspTransports: [tcp]

# WebRTC Settings
webrtc: true
webrtcAddress: :8889
webrtcLocalUDPAddress: :8189
webrtcLocalTCPAddress: ""
webrtcIPsFromInterfaces: false
webrtcAdditionalHosts:
  - 20.194.48.89
  - camera1.koreacentral.cloudapp.azure.com

webrtcICEServers2:
  - url: stun:stun.l.google.com:19302

# Dynamic path routing: allows any camera to publish without pre-configuration
paths:
  all_others:
    source: publisher
```

## 2. Operation and Lifecycle Commands
```bash
# Check service status
systemctl status mediamtx

# Restart MediaMTX
systemctl restart mediamtx

# View real-time logs
journalctl -u mediamtx -f -n 100
```

## 3. WebRTC Protocol (WHEP)
Browsers establish playback via WHEP (WebRTC HTTP Egress Protocol):
1. Browser generates an SDP Offer with `sendrecv` / `recvonly` video transceivers.
2. Browser issues `POST https://camera1.koreacentral.cloudapp.azure.com/<streamPath>/whep` with header `Content-Type: application/sdp`.
3. MediaMTX responds with HTTP `201 Created`, the response body containing the SDP Answer and a `Location` header for PATCH/DELETE session control.
4. ICE candidates are exchanged and the peer connection enters the `connected` state, rendering live frames into the `<video>` element.
