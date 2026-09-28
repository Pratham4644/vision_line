#!/usr/bin/env python3



"""



Low-Latency Camera Ingest Worker



Pipeline:



    Camera RTSP



        |



        | RTSP/TCP



        v



      FFmpeg



        |



        | H.264 stream copy



        | RTSP/TCP



        v



     MediaMTX



One ingest.py process = one camera = one FFmpeg process.



Responsibilities:



    - Connect to one RTSP camera



    - Keep latency/buffering as low as practical



    - Copy H.264 without re-encoding



    - Publish to MediaMTX



    - Reconnect automatically after failure



    - Never expose credentials in logs



    - Drain FFmpeg stderr continuously



    - Shut down cleanly



"""



from __future__ import annotations



import logging
import hashlib
import errno



import os



import signal



import subprocess



import sys



import threading



import time



from pathlib import Path



from typing import Optional

try:
    import fcntl
except ImportError:
    fcntl = None

if os.name == "nt":
    import msvcrt



from urllib.parse import quote, unquote, urlsplit, urlunsplit



# ============================================================================



# OPTIONAL .ENV LOADING



# ============================================================================



# agent.py normally provides the environment.



# Loading .env here also makes ingest.py independently testable.



try:



    from dotenv import load_dotenv



    ENV_FILE = Path(__file__).resolve().parent / ".env"



    if ENV_FILE.exists():



        load_dotenv(ENV_FILE, override=False)



except ImportError:



    # python-dotenv is optional for ingest.py when agent.py already



    # provides the environment.



    pass



# ============================================================================



# LOGGING



# ============================================================================



LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()



logging.basicConfig(



    level=LOG_LEVEL,



    format="%(asctime)s | %(levelname)s | ingest | %(message)s",



)



logger = logging.getLogger("camera-ingest")



# ============================================================================



# CONFIGURATION



# ============================================================================



FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg").strip()



CAMERA_ID = os.getenv("EDGE_CAMERA_ID", "").strip()



SOURCE_URL = os.getenv("EDGE_SOURCE_URL", "").strip()



MEDIA_PATH = os.getenv("EDGE_MEDIA_PATH", "").strip()



MEDIAMTX_HOST = os.getenv(



    "MEDIAMTX_HOST",



    "127.0.0.1",



).strip()



MEDIAMTX_RTSP_PORT = int(



    os.getenv("MEDIAMTX_RTSP_PORT", "8554")



)



PUBLISH_USERNAME = os.getenv(



    "MEDIAMTX_PUBLISH_USERNAME",



    "edge-publisher",



).strip()



PUBLISH_PASSWORD = os.getenv(



    "MEDIAMTX_PUBLISH_PASSWORD",



    "",



)



RECONNECT_INITIAL_DELAY = float(



    os.getenv("RECONNECT_INITIAL_DELAY", "1")



)



RECONNECT_MAX_DELAY = float(



    os.getenv("RECONNECT_MAX_DELAY", "30")



)



# How long FFmpeg must stay alive before we consider the connection stable.



# This prevents a rapidly failing camera from being restarted at 1-second



# intervals forever.



STABLE_CONNECTION_SECONDS = float(



    os.getenv("STABLE_CONNECTION_SECONDS", "10")



)

EDGE_DIR = Path(__file__).resolve().parent
CAMERA_KEY = hashlib.sha256(CAMERA_ID.encode("utf-8")).hexdigest()[:16] if CAMERA_ID else "unknown"
CAMERA_LOCK_PATH = EDGE_DIR / f".ingest-{CAMERA_KEY}.lock"
FFMPEG_PID_PATH = EDGE_DIR / f".ffmpeg-{CAMERA_KEY}.pid"


class CameraIngestLock:
    """Prevents two ingest workers for the same camera from running concurrently."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+")
        try:
            self.handle.seek(0)
            if os.name == "nt":
                self.handle.write("0")
                self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError) as exc:
            self.handle.close()
            self.handle = None
            if getattr(exc, "errno", None) in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                return False
            raise

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self.handle.close()
            self.handle = None


def _read_pid_file() -> Optional[int]:
    try:
        return int(FFMPEG_PID_PATH.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def _is_ffmpeg_pid(pid: int) -> bool:
    """Best-effort identity check before killing a stale PID."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=3, check=False,
            )
            return "ffmpeg.exe" in result.stdout.lower()
        except OSError:
            return False
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    try:
        return "ffmpeg" in proc_cmdline.read_text(errors="ignore").lower()
    except OSError:
        return False


def cleanup_stale_ffmpeg() -> None:
    """Remove an FFmpeg left behind by an abruptly terminated ingest worker."""
    pid = _read_pid_file()
    if pid is None:
        return
    if _is_ffmpeg_pid(pid):
        logger.warning("Found stale FFmpeg process | camera=%s | pid=%s", CAMERA_ID, pid)
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    try:
        FFMPEG_PID_PATH.unlink()
    except FileNotFoundError:
        pass


def write_ffmpeg_pid(pid: int) -> None:
    FFMPEG_PID_PATH.write_text(str(pid), encoding="utf-8")


def clear_ffmpeg_pid(pid: int) -> None:
    try:
        if _read_pid_file() == pid:
            FFMPEG_PID_PATH.unlink()
    except FileNotFoundError:
        pass




# ============================================================================



# NORMALIZE MEDIA PATH



# ============================================================================



# API may return:



#



#     cam_123



#



# or:



#



#     /cam_123



#



# Internally we always use:



#



#     /cam_123



if MEDIA_PATH and not MEDIA_PATH.startswith("/"):



    MEDIA_PATH = "/" + MEDIA_PATH



# ============================================================================



# SHUTDOWN STATE



# ============================================================================



STOP_EVENT = threading.Event()



PROCESS_LOCK = threading.Lock()



CURRENT_PROCESS: Optional[subprocess.Popen] = None



# ============================================================================



# SECURITY HELPERS



# ============================================================================



def redact_url(url: str) -> str:



    """



    Remove credentials from a URL before logging it.



    """



    try:



        parsed = urlsplit(url)



        if parsed.username is None:



            return url



        hostname = parsed.hostname or ""



        if parsed.port:



            hostname = f"{hostname}:{parsed.port}"



        return urlunsplit(



            (



                parsed.scheme,



                f"{quote(parsed.username)}:***@{hostname}",



                parsed.path,



                parsed.query,



                parsed.fragment,



            )



        )



    except Exception:



        return "\<redacted-url>"



def normalize_rtsp_source_url(url: str) -> str:



    """



    Normalize RTSP source credentials.



    Handles both:



        password containing special characters



    and:



        already URL-encoded passwords



    This prevents double encoding such as:



        %40 -> %2540



    """



    try:



        parsed = urlsplit(url)



        if parsed.username is None:



            return url



        username = parsed.username or ""

        password = parsed.password or ""



        # Normalize legacy URL encoding before encoding credentials once.

        for _ in range(3):

            decoded_username = unquote(username)

            decoded_password = unquote(password)

            if decoded_username == username and decoded_password == password:

                break

            username = decoded_username

            password = decoded_password



        hostname = parsed.hostname or ""



        if parsed.port:



            hostname = f"{hostname}:{parsed.port}"



        encoded_username = quote(username, safe="")



        encoded_password = quote(password, safe="")



        return urlunsplit(



            (



                parsed.scheme,



                f"{encoded_username}:{encoded_password}@{hostname}",



                parsed.path,



                parsed.query,



                parsed.fragment,



            )



        )



    except Exception as exc:



        raise ValueError(



            "Invalid RTSP source URL"



        ) from exc



# ============================================================================



# MEDIAMTX URL



# ============================================================================



def build_publish_url() -> str:



    """



    Build the RTSP publish URL.



    Credentials are URL encoded so special characters in passwords



    cannot corrupt the URL.



    """



    username = quote(



        PUBLISH_USERNAME,



        safe="",



    )



    password = quote(



        PUBLISH_PASSWORD,



        safe="",



    )



    return (



        f"rtsp://{username}:{password}"



        f"@{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}"



        f"{MEDIA_PATH}"



    )



# ============================================================================



# FFMPEG COMMAND



# ============================================================================



def build_ffmpeg_command(



    source_url: str,



    publish_url: str,



) -> list[str]:



    """



    Build the production low-latency FFmpeg command.



    Pipeline:



        RTSP camera



             |



             | TCP



             v



        FFmpeg



             |



             | H.264 re-encode



             | 1280x720



             | 30 FPS



             | \~1.5 Mbps



             v



        MediaMTX



             |



             | WebRTC / RTSP



             v



        Customers



    We intentionally re-encode the camera stream because the original



    camera stream can be \~15 Mbps, which is unnecessarily expensive



    over the customer's WAN connection.



    The encoder settings are based on the previously working



    MediaMTX pipeline.



    """



    return [



        FFMPEG_BIN,



        # ================================================================



        # GENERAL



        # ================================================================



        "-hide_banner",



        "-loglevel", "warning",



        "-nostdin",



        # ================================================================



        # INPUT



        # ================================================================



        # Camera -> Edge PC



        "-rtsp_transport", "tcp",



        # Keep input buffering low.



        "-fflags", "+genpts",



        "-use_wallclock_as_timestamps", "1",



        # Reasonable startup probing.



        "-analyzeduration", "500000",



        "-probesize", "500000",



        "-i", source_url,



        # ================================================================



        # STREAM SELECTION



        # ================================================================



        "-map", "0:v:0",



        # ================================================================



        # VIDEO ENCODING



        # ================================================================



        # IMPORTANT:



        # Do NOT use "-c:v copy".



        #



        # The camera can produce \~15 Mbps H.264.



        # We encode it to a controlled \~1.5 Mbps stream for WAN delivery.



        "-c:v", "libx264",



        # Very low CPU usage / low latency.



        "-preset", "ultrafast",



        "-tune", "zerolatency",



        "-pix_fmt", "yuv420p",



        # Keep a stable 30 FPS output.



        "-r", "30",



        # One keyframe every second.



        "-g", "30",



        "-keyint_min", "30",



        "-sc_threshold", "0",



        # ================================================================



        # BITRATE CONTROL



        # ================================================================



        "-b:v", "1500k",



        "-maxrate", "1500k",



        "-bufsize", "3000k",



        # ================================================================



        # AUDIO



        # ================================================================



        "-an",



        # ================================================================



        # OUTPUT



        # ================================================================



        # FFmpeg -> MediaMTX



        "-f", "rtsp",



        "-rtsp_transport", "tcp",



        # Avoid unnecessary muxer buffering.



        "-muxdelay", "0",



        "-flush_packets", "1",



        # Dynamic MediaMTX path.



        publish_url,



    ]



# ============================================================================



# STDERR READER



# ============================================================================



def drain_stderr(



    process: subprocess.Popen,



) -> None:



    """



    Continuously drain FFmpeg stderr.



    Without this, stderr can eventually fill its pipe and block FFmpeg.



    """



    if process.stderr is None:



        return



    try:



        for raw_line in iter(



            process.stderr.readline,



            b"",



        ):



            if STOP_EVENT.is_set():



                break



            line = raw_line.decode(



                "utf-8",



                errors="replace",



            ).strip()



            if not line:



                continue



            logger.warning(



                "FFmpeg[%s] %s",



                CAMERA_ID,



                line,



            )



    except Exception as exc:



        logger.debug(



            "FFmpeg stderr reader stopped: %s",



            exc,



        )



    finally:



        try:



            process.stderr.close()



        except Exception:



            pass



# ============================================================================



# PROCESS TERMINATION



# ============================================================================



def terminate_process(



    process: subprocess.Popen,



) -> None:



    """



    Gracefully terminate FFmpeg.



    If FFmpeg refuses to terminate, force kill it.



    """



    if process.poll() is not None:



        return



    logger.info(



        "Stopping FFmpeg | camera=%s | pid=%s",



        CAMERA_ID,



        process.pid,



    )



    try:



        process.terminate()



    except Exception as exc:



        logger.debug(



            "FFmpeg terminate failed: %s",



            exc,



        )



    try:



        process.wait(timeout=5)
        clear_ffmpeg_pid(process.pid)
        return



    except subprocess.TimeoutExpired:



        pass



    logger.warning(



        "FFmpeg did not terminate within 5 seconds; killing it"



    )



    try:



        process.kill()



        process.wait(timeout=3)



    except Exception as exc:



        logger.error(



            "Failed to kill FFmpeg: %s",



            exc,



        )



# ============================================================================



# START FFMPEG



# ============================================================================



def start_ffmpeg() -> subprocess.Popen:



    """



    Start one FFmpeg process.



    """



    publish_url = build_publish_url()



    # Normalize camera RTSP credentials before passing URL to FFmpeg.



    source_url = normalize_rtsp_source_url(



        SOURCE_URL



    )



    command = build_ffmpeg_command(



        source_url,



        publish_url,



    )



    logger.info(



        "Starting FFmpeg | camera=%s",



        CAMERA_ID,



    )



    logger.info(



        "Source=%s",



        redact_url(source_url),



    )



    logger.info(



        "Destination=rtsp://%s:%s%s",



        MEDIAMTX_HOST,



        MEDIAMTX_RTSP_PORT,



        MEDIA_PATH,



    )



    process_kwargs = {



        "stdin": subprocess.DEVNULL,



        "stdout": subprocess.DEVNULL,



        "stderr": subprocess.PIPE,



    }



    # Prevent a console window from appearing on Windows.



    if os.name == "nt":



        process_kwargs["creationflags"] = (



            subprocess.CREATE_NO_WINDOW



        )



    process = subprocess.Popen(



        command,



        **process_kwargs,



    )

    write_ffmpeg_pid(process.pid)



    with PROCESS_LOCK:



        global CURRENT_PROCESS



        CURRENT_PROCESS = process



    # Drain stderr immediately.



    stderr_thread = threading.Thread(



        target=drain_stderr,



        args=(process,),



        name=f"ffmpeg-stderr-{CAMERA_ID}",



        daemon=True,



    )



    stderr_thread.start()



    logger.info(



        "FFmpeg started | camera=%s | pid=%s",



        CAMERA_ID,



        process.pid,



    )



    return process



# ============================================================================



# WORKER LOOP



# ============================================================================



def run_worker() -> None:



    """



    Keep FFmpeg alive.



    Failed connections use exponential backoff.



    Once a connection remains alive for STABLE_CONNECTION_SECONDS,



    the retry delay is reset.



    """



    delay = RECONNECT_INITIAL_DELAY



    while not STOP_EVENT.is_set():



        process: Optional[subprocess.Popen] = None



        started_at = time.monotonic()



        try:



            process = start_ffmpeg()



            return_code = process.wait()



            runtime = time.monotonic() - started_at



            if STOP_EVENT.is_set():



                break



            logger.warning(



                "FFmpeg exited | camera=%s | "



                "return_code=%s | runtime=%.1fs",



                CAMERA_ID,



                return_code,



                runtime,



            )



            # Only reset the retry delay after a genuinely stable



            # connection. This prevents crash loops.



            if runtime >= STABLE_CONNECTION_SECONDS:



                delay = RECONNECT_INITIAL_DELAY



            else:



                delay = min(



                    delay * 2,



                    RECONNECT_MAX_DELAY,



                )



        except FileNotFoundError:



            logger.error(



                "FFmpeg executable not found: %s",



                FFMPEG_BIN,



            )



            break



        except Exception:



            logger.exception(



                "Unexpected ingest error | camera=%s",



                CAMERA_ID,



            )



            delay = min(



                delay * 2,



                RECONNECT_MAX_DELAY,



            )



        finally:



            if process is not None:



                terminate_process(process)



            with PROCESS_LOCK:



                CURRENT_PROCESS = None



        if STOP_EVENT.is_set():



            break



        logger.info(



            "Reconnect scheduled | camera=%s | delay=%.1fs",



            CAMERA_ID,



            delay,



        )



        STOP_EVENT.wait(delay)



    logger.info(



        "Worker loop stopped | camera=%s",



        CAMERA_ID,



    )



# ============================================================================



# SIGNAL HANDLING



# ============================================================================



def request_shutdown(



    signum: int,



    _frame,



) -> None:



    """



    Handle SIGINT/SIGTERM.



    """



    logger.info(



        "Shutdown signal received | signal=%s | camera=%s",



        signum,



        CAMERA_ID,



    )



    STOP_EVENT.set()



    with PROCESS_LOCK:



        process = CURRENT_PROCESS



    if process is not None:



        terminate_process(process)



def validate_config() -> None:

    required = {

        "EDGE_SOURCE_URL": SOURCE_URL,

        "EDGE_MEDIA_PATH": MEDIA_PATH,

        "MEDIAMTX_HOST": MEDIAMTX_HOST,

        "MEDIAMTX_PUBLISH_PASSWORD": PUBLISH_PASSWORD,

    }



    missing = [name for name, value in required.items() if not value]



    if missing:

        raise RuntimeError(

            "Missing required configuration: " + ", ".join(missing)

        )





# ============================================================================



# MAIN



# ============================================================================



def main() -> int:



    try:



        validate_config()



    except Exception as exc:



        logger.error(



            "Configuration error: %s",



            exc,



        )



        return 2



    signal.signal(



        signal.SIGINT,



        request_shutdown,



    )



    signal.signal(



        signal.SIGTERM,



        request_shutdown,



    )



    logger.info(



        "========================================"



    )



    logger.info(



        "Camera ingest starting"



    )



    logger.info(



        "Camera ID: %s",



        CAMERA_ID,



    )



    logger.info(



        "Source: %s",



        redact_url(SOURCE_URL),



    )



    logger.info(



        "MediaMTX: %s:%s%s",



        MEDIAMTX_HOST,



        MEDIAMTX_RTSP_PORT,



        MEDIA_PATH,



    )



    logger.info(



        "========================================"



    )



    ingest_lock = CameraIngestLock(CAMERA_LOCK_PATH)
    if not ingest_lock.acquire():
        logger.error("Another ingest worker is already running for camera=%s", CAMERA_ID)
        return 1

    try:
        cleanup_stale_ffmpeg()
        run_worker()

    except KeyboardInterrupt:



        STOP_EVENT.set()



    finally:



        with PROCESS_LOCK:



            process = CURRENT_PROCESS



        if process is not None:



            terminate_process(process)



        logger.info(



            "Camera ingest stopped | camera=%s",



            CAMERA_ID,



        )

        ingest_lock.release()



    return 0



if __name__ == "__main__":



    sys.exit(main())
