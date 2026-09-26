# import subprocess
# import threading
# from urllib.parse import quote


# # ============================================================
# # MediaMTX configuration
# # ============================================================

# MEDIAMTX_HOST = "127.0.0.1"
# MEDIAMTX_PORT = 8554

# MEDIAMTX_USERNAME = "PS"
# MEDIAMTX_PASSWORD = "Sasha123"


# # ============================================================
# # Stream Manager
# # ============================================================

# class StreamManager:

#     def __init__(self):

#         # camera_id -> subprocess.Popen
#         self.processes = {}

#         # Protect dictionary from multiple threads
#         self.lock = threading.Lock()

#     # ========================================================
#     # Start camera
#     # ========================================================

#     def start_camera(
#         self,
#         camera_id,
#         camera_url,
#         username=None,
#         password=None
#     ):

#         with self.lock:

#             # ------------------------------------------------
#             # Check if camera is already running
#             # ------------------------------------------------

#             existing_process = self.processes.get(camera_id)

#             if existing_process is not None:

#                 if existing_process.poll() is None:

#                     print(
#                         f"[StreamManager] "
#                         f"{camera_id} is already running"
#                     )

#                     return True

#                 # Old process already stopped
#                 del self.processes[camera_id]

#             # ------------------------------------------------
#             # Build camera source URL
#             # ------------------------------------------------

#             if username and password:

#                 encoded_username = quote(
#                     username,
#                     safe=""
#                 )

#                 encoded_password = quote(
#                     password,
#                     safe=""
#                 )

#                 source_url = (
#                     f"http://"
#                     f"{encoded_username}:"
#                     f"{encoded_password}@"
#                     f"{camera_url}"
#                 )

#             else:

#                 source_url = (
#                     f"http://{camera_url}"
#                 )

#             # ------------------------------------------------
#             # Build MediaMTX destination
#             # ------------------------------------------------

#             destination_url = (
#                 f"rtsp://"
#                 f"{MEDIAMTX_USERNAME}:"
#                 f"{MEDIAMTX_PASSWORD}@"
#                 f"{MEDIAMTX_HOST}:"
#                 f"{MEDIAMTX_PORT}/"
#                 f"{camera_id}"
#             )

#             # ------------------------------------------------
#             # FFmpeg command
#             # ------------------------------------------------

#             command = [

#                 "ffmpeg",

#                 # Don't show FFmpeg banner
#                 "-hide_banner",

#                 # Only show warnings/errors
#                 "-loglevel",
#                 "info",

#                 # ------------------------------------------------
#                 # INPUT
#                 # ------------------------------------------------

#                 "-i",
#                 source_url,

#                 # ------------------------------------------------
#                 # VIDEO PROCESSING
#                 # ------------------------------------------------

#                 "-vf",
#                 "scale=1280:720",

#                 "-r",
#                 "15",

#                 # ------------------------------------------------
#                 # AMD hardware H.264 encoder
#                 # ------------------------------------------------

#                 "-c:v",
#                 "h264_amf",

#                 "-usage",
#                 "ultralowlatency",

#                 # Constant bitrate
#                 "-rc",
#                 "cbr",

#                 "-b:v",
#                 "1M",

#                 "-maxrate",
#                 "1M",

#                 "-bufsize",
#                 "500K",

#                 # Keyframe every 15 frames
#                 "-g",
#                 "15",

#                 # No audio
#                 "-an",

#                 # ------------------------------------------------
#                 # OUTPUT
#                 # ------------------------------------------------

#                 "-f",
#                 "rtsp",

#                 "-rtsp_transport",
#                 "tcp",

#                 destination_url
#             ]

#             print()
#             print(
#                 f"[StreamManager] "
#                 f"Starting camera: {camera_id}"
#             )

#             print(
#                 f"[StreamManager] "
#                 f"Destination: "
#                 f"rtsp://...@"
#                 f"{MEDIAMTX_HOST}:"
#                 f"{MEDIAMTX_PORT}/"
#                 f"{camera_id}"
#             )

#             # ------------------------------------------------
#             # Start FFmpeg
#             # ------------------------------------------------

#             try:

#                 process = subprocess.Popen(

#                     command,

#                     stdout=subprocess.DEVNULL,

#                     stderr=subprocess.PIPE,

#                     text=True,

#                     bufsize=1
#                 )

#             except Exception as error:

#                 print(
#                     f"[StreamManager] "
#                     f"Failed to start FFmpeg: "
#                     f"{error}"
#                 )

#                 return False

#             # ------------------------------------------------
#             # Store process
#             # ------------------------------------------------

#             self.processes[camera_id] = process

#             # ------------------------------------------------
#             # Start monitor thread
#             # ------------------------------------------------

#             monitor_thread = threading.Thread(

#                 target=self._monitor_process,

#                 args=(
#                     camera_id,
#                     process
#                 ),

#                 daemon=True
#             )

#             monitor_thread.start()

#             return True

#     # ========================================================
#     # Monitor FFmpeg process
#     # ========================================================

#     def _monitor_process(
#         self,
#         camera_id,
#         process
#     ):

#         try:

#             for line in process.stderr:

#                 line = line.strip()

#                 if line:

#                     print(
#                         f"[FFmpeg:{camera_id}] "
#                         f"{line}"
#                     )

#         except Exception as error:

#             print(
#                 f"[StreamManager] "
#                 f"Monitor error for {camera_id}: "
#                 f"{error}"
#             )

#         finally:

#             return_code = process.poll()

#             print(
#                 f"[StreamManager] "
#                 f"{camera_id} stopped "
#                 f"with code {return_code}"
#             )

#             with self.lock:

#                 # Only remove this exact process.
#                 # This prevents an old FFmpeg process
#                 # from deleting a newer process entry.

#                 if self.processes.get(camera_id) == process:

#                     del self.processes[camera_id]

#     # ========================================================
#     # Stop camera
#     # ========================================================

#     def stop_camera(
#         self,
#         camera_id
#     ):

#         with self.lock:

#             process = self.processes.get(
#                 camera_id
#             )

#             if process is None:

#                 print(
#                     f"[StreamManager] "
#                     f"{camera_id} is not running"
#                 )

#                 return False

#             if process.poll() is None:

#                 print(
#                     f"[StreamManager] "
#                     f"Stopping camera: {camera_id}"
#                 )

#                 try:

#                     process.terminate()

#                 except Exception as error:

#                     print(
#                         f"[StreamManager] "
#                         f"Error stopping {camera_id}: "
#                         f"{error}"
#                     )

#                     return False

#             # Remove from manager

#             del self.processes[camera_id]

#             return True

#     # ========================================================
#     # Check if camera is running
#     # ========================================================

#     def is_running(
#         self,
#         camera_id
#     ):

#         with self.lock:

#             process = self.processes.get(
#                 camera_id
#             )

#             if process is None:

#                 return False

#             return process.poll() is None

#     # ========================================================
#     # Get all running cameras
#     # ========================================================

#     def get_running_cameras(self):

#         with self.lock:

#             running = []

#             for camera_id, process in self.processes.items():

#                 if process.poll() is None:

#                     running.append(camera_id)

#             return running

#     # ========================================================
#     # Stop all cameras
#     # ========================================================

#     def stop_all(self):

#         with self.lock:

#             camera_ids = list(
#                 self.processes.keys()
#             )

#         for camera_id in camera_ids:

#             self.stop_camera(camera_id)

#         print(
#             "[StreamManager] "
#             "All cameras stopped"
#         )


# # ============================================================
# # Global StreamManager instance
# # ============================================================

# stream_manager = StreamManager()


















import subprocess
import threading
from urllib.parse import quote, urlsplit, urlunsplit

MEDIAMTX_HOST = "127.0.0.1"
MEDIAMTX_PORT = 8554

MEDIAMTX_USERNAME = "PS"
MEDIAMTX_PASSWORD = "Sasha123"


class StreamManager:

    def __init__(self):
        self.processes = {}
        self.lock = threading.Lock()

    def _build_source_url(self, camera_url, username=None, password=None):
        """
        Build a camera source URL.

        Supports:
            rtsp://...
            http://...
            https://...
        """

        if not camera_url:
            raise ValueError("Camera URL is empty")

        # Already has a protocol
        if "://" in camera_url:
            source_url = camera_url
        else:
            # Backward compatibility for old HTTP cameras
            source_url = f"http://{camera_url}"

        # Add credentials safely if supplied
        if username and password:

            parsed = urlsplit(source_url)

            encoded_username = quote(username, safe="")
            encoded_password = quote(password, safe="")

            hostname = parsed.hostname

            if not hostname:
                raise ValueError(f"Invalid camera URL: {camera_url}")

            # IPv6 support
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"

            if parsed.port:
                host_part = f"{hostname}:{parsed.port}"
            else:
                host_part = hostname

            netloc = f"{encoded_username}:{encoded_password}@{host_part}"

            source_url = urlunsplit((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.query,
                parsed.fragment
            ))

        return source_url

    def start_camera(
        self,
        camera_id,
        camera_url,
        username=None,
        password=None
    ):

        with self.lock:

            existing_process = self.processes.get(camera_id)

            if existing_process is not None:

                if existing_process.poll() is None:
                    print(
                        f"[StreamManager] "
                        f"{camera_id} is already running"
                    )
                    return True

                del self.processes[camera_id]

            try:
                source_url = self._build_source_url(
                    camera_url,
                    username,
                    password
                )
            except Exception as error:

                print(
                    f"[StreamManager] "
                    f"Invalid source URL for {camera_id}: {error}"
                )

                return False

            destination_url = (
                f"rtsp://{MEDIAMTX_USERNAME}:"
                f"{MEDIAMTX_PASSWORD}@"
                f"{MEDIAMTX_HOST}:"
                f"{MEDIAMTX_PORT}/"
                f"{camera_id}"
            )

            print(
                f"[StreamManager] "
                f"Starting camera: {camera_id}"
            )

            print(
                f"[StreamManager] "
                f"Input protocol: "
                f"{source_url.split('://')[0]}"
            )

            print(
                f"[StreamManager] "
                f"Destination: "
                f"rtsp://...@"
                f"{MEDIAMTX_HOST}:"
                f"{MEDIAMTX_PORT}/"
                f"{camera_id}"
            )

            command = [
                "ffmpeg",

                "-hide_banner",
                "-loglevel", "info",

                # Input
                "-i",
                source_url,

                # Normalize stream
                "-vf",
                "scale=1280:720",

                "-r",
                "15",

                # Hardware H.264 encoder
                "-c:v",
                "h264_amf",

                "-usage",
                "ultralowlatency",

                "-rc",
                "cbr",

                "-b:v",
                "1M",

                "-maxrate",
                "1M",

                "-bufsize",
                "500K",

                "-g",
                "15",

                # CCTV currently video only
                "-an",

                # Publish to MediaMTX
                "-f",
                "rtsp",

                "-rtsp_transport",
                "tcp",

                destination_url
            ]

            try:

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

            except Exception as error:

                print(
                    f"[StreamManager] "
                    f"Failed to start FFmpeg: {error}"
                )

                return False

            self.processes[camera_id] = process

            monitor_thread = threading.Thread(
                target=self._monitor_process,
                args=(camera_id, process),
                daemon=True
            )

            monitor_thread.start()

            return True

    def _monitor_process(self, camera_id, process):

        try:

            for line in process.stderr:

                line = line.strip()

                if line:
                    print(
                        f"[FFmpeg:{camera_id}] "
                        f"{line}"
                    )

        except Exception as error:

            print(
                f"[StreamManager] "
                f"Monitor error for {camera_id}: "
                f"{error}"
            )

        finally:

            return_code = process.poll()

            print(
                f"[StreamManager] "
                f"{camera_id} stopped "
                f"with code {return_code}"
            )

            with self.lock:

                if self.processes.get(camera_id) == process:
                    del self.processes[camera_id]

    def stop_camera(self, camera_id):

        with self.lock:

            process = self.processes.get(camera_id)

            if process is None:

                print(
                    f"[StreamManager] "
                    f"{camera_id} is not running"
                )

                return False

            if process.poll() is None:

                print(
                    f"[StreamManager] "
                    f"Stopping camera: {camera_id}"
                )

                try:

                    process.terminate()

                except Exception as error:

                    print(
                        f"[StreamManager] "
                        f"Error stopping {camera_id}: "
                        f"{error}"
                    )

                    return False

            del self.processes[camera_id]

            return True

    def is_running(self, camera_id):

        with self.lock:

            process = self.processes.get(camera_id)

            if process is None:
                return False

            return process.poll() is None

    def get_running_cameras(self):

        with self.lock:

            running = []

            for camera_id, process in self.processes.items():

                if process.poll() is None:
                    running.append(camera_id)

            return running

    def stop_all(self):

        with self.lock:

            camera_ids = list(self.processes.keys())

        for camera_id in camera_ids:
            self.stop_camera(camera_id)

        print(
            "[StreamManager] "
            "All cameras stopped"
        )


stream_manager = StreamManager()