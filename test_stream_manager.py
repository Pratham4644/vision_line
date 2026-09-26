# import time

# from stream_manager import stream_manager


# stream_manager.start_camera(
#     camera_id="cam1",
#     camera_url="192.168.1.9:8080/video",
#     username="hello",
#     password="Pratham@123"
# )

# print()
# print("========================================")
# print("cam1 is running")
# print("========================================")
# print()
# print("Open:")
# print("http://127.0.0.1:8889/cam1/")
# print()
# print("Press CTRL+C to stop")
# print("========================================")

# try:

#     while True:

#         time.sleep(2)

#         print(
#             "Running cameras:",
#             stream_manager.get_running_cameras()
#         )

# except KeyboardInterrupt:

#     print()
#     print("Stopping cam1...")

#     stream_manager.stop_camera("cam1")

#     print("cam1 stopped.")