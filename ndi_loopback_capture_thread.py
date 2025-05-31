import ndi
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import cv2 # For potential UYVY to BGR conversion, if needed.

class NDILoopbackCaptureThread(QThread):
    new_video_frame_signal = pyqtSignal(object)  # Emits NumPy array (BGR format)
    new_audio_frame_signal = pyqtSignal(object, int, int, int)  # Emits audio data, sample rate, num channels, timestamp
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    ndi_sources_signal = pyqtSignal(list)  # Emits list of NDI source names
    ndi_info_signal = pyqtSignal(str)  # Emits resolution and FPS info

    def __init__(self, ndi_source_name=None, parent=None):
        super().__init__(parent)
        self.ndi_source_name = ndi_source_name
        self.running = False
        self.pNDI_find = None
        self.pNDI_recv = None
        self.ndi_source_to_connect = None

        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0

    def set_source_name(self, source_name):
        self.ndi_source_name = source_name
        # If thread is running, ideally it should reconnect.
        # For now, this might require a stop and start of the thread.
        if self.isRunning() and source_name:
            self.status_signal.emit(f"NDI source changed to: {source_name}. Restarting capture.")
            # This is a simplified approach. A more robust solution would re-initialize
            # the receiver within the run loop or signal the run loop to do so.
            self.stop()
            self.start_capture() # Custom method to re-init and start
        elif source_name:
             self.status_signal.emit(f"NDI source set to: {source_name}")


    def start_capture(self): # Helper to allow restarting with new source
        if not self.isRunning():
            self.running = True
            self.start()

    def run(self):
        self.running = True
        self.status_signal.emit("NDI Loopback thread started.")

        if not ndi.initialize():
            self.error_signal.emit("Failed to initialize NDI.")
            self.running = False
            return

        self.pNDI_find = ndi.find_create_v2()
        if self.pNDI_find is None:
            self.error_signal.emit("Failed to create NDI find instance.")
            ndi.destroy()
            self.running = False
            return

        # If ndi_source_name is None, this thread is purely for discovery.
        if self.ndi_source_name is None:
            self.status_signal.emit("NDI Discovery Service Started.")
            while self.running:
                if ndi.find_wait_for_sources(self.pNDI_find, 2000): # Wait for 2 seconds
                    current_sources = ndi.find_get_current_sources(self.pNDI_find)
                    source_names = [source.ndi_name for source in current_sources]
                    self.ndi_sources_signal.emit(source_names)
                    # self.status_signal.emit(f"Discovered NDI sources: {source_names}") # Can be noisy
                else:
                    # self.status_signal.emit("No new NDI sources found in the last interval.")
                    # Emit empty list if no sources are found after waiting, to clear ComboBox if necessary
                    # Or emit previously known sources if that's preferred. Emitting current state is good.
                    current_sources = ndi.find_get_current_sources(self.pNDI_find) # Get current list even on timeout
                    source_names = [source.ndi_name for source in current_sources]
                    self.ndi_sources_signal.emit(source_names)

                # Loop for continuous discovery, check running flag periodically
                for _ in range(5): # Check running flag every ~200ms for responsiveness
                    if not self.running:
                        break
                    QThread.msleep(200)
            self.status_signal.emit("NDI Discovery Service Stopped.")
            self._cleanup_ndi()
            return # Exit run method for discovery-only threads

        # Proceed with connection and capture if ndi_source_name is provided.
        self.status_signal.emit(f"Attempting to connect to specified NDI source: {self.ndi_source_name}")

        sources = []
        found_specific_source = False
        # Try to find the specific source for a few seconds
        for attempt in range(5): # Max ~5 seconds to find the specific source
            if not ndi.find_wait_for_sources(self.pNDI_find, 1000):
                self.status_signal.emit(f"Attempt {attempt+1}: Specified source '{self.ndi_source_name}' not found yet. Retrying...")
                continue

            current_sources = ndi.find_get_current_sources(self.pNDI_find)
            source_names = [source.ndi_name for source in current_sources]
            # Also emit all sources found during targeted search, useful for GUI update
            self.ndi_sources_signal.emit(source_names)

            for source_obj in current_sources:
                if source_obj.ndi_name == self.ndi_source_name:
                    self.ndi_source_to_connect = source_obj
                    self.status_signal.emit(f"Found specified NDI source: {self.ndi_source_name}")
                    found_specific_source = True
                    break
            if found_specific_source:
                break
            else:
                QThread.msleep(200) # Wait a bit before retrying find_get_current_sources

        if not found_specific_source:
            self.error_signal.emit(f"Could not find specified NDI source '{self.ndi_source_name}' after several attempts.")
            self._cleanup_ndi()
            return

        # At this point, self.ndi_source_to_connect should be set.
        if not self.ndi_source_to_connect:
             self.error_signal.emit(f"Internal error: NDI source object for '{self.ndi_source_name}' not set before connection attempt.")
             self._cleanup_ndi()
             return

        self.status_signal.emit(f"Connecting to NDI receiver for: {self.ndi_source_to_connect.ndi_name}...")
        recv_create_attrs = ndi.RecvCreateV3()
        recv_create_attrs.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
        # Alternatives:
        # recv_create_attrs.color_format = ndi.RECV_COLOR_FORMAT_UYVY_BGRA # Requires conversion
        recv_create_attrs.bandwidth = ndi.RECV_BANDWIDTH_HIGHEST
        recv_create_attrs.allow_video_fields = False

        self.pNDI_recv = ndi.recv_create_v3(recv_create_attrs)
        if self.pNDI_recv is None:
            self.error_signal.emit("Failed to create NDI receiver.")
            self._cleanup_ndi()
            return

        ndi.recv_connect(self.pNDI_recv, self.ndi_source_to_connect)
        self.status_signal.emit(f"Connected to {self.ndi_source_to_connect.ndi_name}.")

        # Metadata for FPS calculation
        last_video_timestamp = 0
        frame_count = 0
        fps_calc_interval = 1 # seconds
        fps_timer = QTimer() # Using QTimer for periodic FPS calculation might be complex in a thread
                            # Simpler approach: calculate based on frame timestamps or count over time.


        prev_width, prev_height, prev_fps = 0,0,0

        while self.running:
            video_frame, audio_frame, metadata_frame = None, None, None
            try:
                frame_type, data, timestamp = ndi.recv_capture_v3(self.pNDI_recv, timeout_ms=1000)

                if frame_type == ndi.FRAME_TYPE_VIDEO:
                    video_frame = data # data is already an NDIlib.video_frame_v2_t
                    # self.status_signal.emit("Video frame received")
                    if video_frame.data is None or video_frame.data.size == 0:
                        self.error_signal.emit("Received empty video frame data.")
                        ndi.recv_free_video_v2(self.pNDI_recv, video_frame)
                        continue

                    # Frame properties
                    self.frame_width = video_frame.xres
                    self.frame_height = video_frame.yres
                    # self.fps = video_frame.frame_rate_N / video_frame.frame_rate_D # This can be fractional

                    # Calculate FPS more dynamically
                    current_time = QTimer() # This is not how QTimer works.
                                        # For FPS, usually count frames over an interval or use timestamps.
                    # Using frame timestamps for FPS (approximate)
                    if last_video_timestamp > 0 and video_frame.timestamp > last_video_timestamp:
                        time_diff_ns = video_frame.timestamp - last_video_timestamp # Timestamp is in 100ns units
                        time_diff_s = time_diff_ns / 10_000_000.0 # Convert to seconds
                        if time_diff_s > 0:
                            self.fps = 1.0 / time_diff_s
                    last_video_timestamp = video_frame.timestamp


                    if self.frame_width != prev_width or self.frame_height != prev_height or abs(self.fps - prev_fps) > 1:
                        info_str = f"Res: {self.frame_width}x{self.frame_height}, FPS: {self.fps:.2f}"
                        self.ndi_info_signal.emit(info_str)
                        prev_width, prev_height, prev_fps = self.frame_width, self.frame_height, self.fps


                    # Process video data
                    # Assuming RECV_COLOR_FORMAT_BGRX_BGRA, data is BGRA. We need BGR.
                    # Make a copy because the buffer is owned by NDI.
                    frame_data_bgr = np.copy(video_frame.data[:, :, :3])
                    self.new_video_frame_signal.emit(frame_data_bgr)
                    ndi.recv_free_video_v2(self.pNDI_recv, video_frame)

                elif frame_type == ndi.FRAME_TYPE_AUDIO:
                    audio_frame = data # data is an NDIlib.audio_frame_v2_t
                    # self.status_signal.emit("Audio frame received")
                    # Audio data is interleaved. NDI hands it as float32, planar typically.
                    # Let's confirm format with `ndi-python` docs or examples.
                    # The `audio_frame.data` is a NumPy array.
                    # timestamp is in 100s of nanoseconds
                    self.new_audio_frame_signal.emit(np.copy(audio_frame.data),
                                                     audio_frame.sample_rate,
                                                     audio_frame.no_channels,
                                                     audio_frame.timestamp)
                    ndi.recv_free_audio_v2(self.pNDI_recv, audio_frame)

                elif frame_type == ndi.FRAME_TYPE_METADATA:
                    # self.status_signal.emit("Metadata frame received")
                    ndi.recv_free_metadata(self.pNDI_recv, data) # data is NDIlib.metadata_frame_t

                elif frame_type == ndi.FRAME_TYPE_ERROR:
                    self.error_signal.emit("Error received from NDI stream. Restarting connection might be needed.")
                    # Potentially try to reconnect or signal critical error
                    QThread.msleep(100) # Wait a bit before trying to capture again

                elif frame_type == ndi.FRAME_TYPE_NONE:
                    # self.status_signal.emit("No new NDI frame received in timeout.")
                    pass # Timeout, normal

                else:
                    # self.status_signal.emit(f"Unhandled NDI frame type: {frame_type}")
                    pass


            except Exception as e:
                self.error_signal.emit(f"Error during NDI capture: {str(e)}")
                # Depending on the error, may need to break or attempt re-initialization
                QThread.msleep(1000) # Wait a bit before trying again

        self.status_signal.emit("NDI Loopback thread stopping.")
        self._cleanup_ndi()

    def _cleanup_ndi(self):
        self.status_signal.emit("Cleaning up NDI resources.")
        if self.pNDI_recv:
            ndi.recv_destroy(self.pNDI_recv)
            self.pNDI_recv = None
        if self.pNDI_find:
            ndi.find_destroy(self.pNDI_find)
            self.pNDI_find = None
        ndi.destroy()
        self.status_signal.emit("NDI resources cleaned up.")

    def stop(self):
        self.status_signal.emit("Attempting to stop NDI Loopback thread...")
        self.running = False
        if self.isRunning():
            self.wait(5000) # Wait for thread to finish
        self.status_signal.emit("NDI Loopback thread stopped.")

if __name__ == '__main__':
    # This is a basic test, not a full GUI application
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv) # Required for QThread signals if not in a full app

    print("Starting NDI Loopback Test")

    # Create a dummy handler for signals for testing
    def handle_video(frame):
        print(f"Video frame received: shape={frame.shape}, dtype={frame.dtype}")

    def handle_audio(data, rate, channels, ts):
        print(f"Audio frame received: shape={data.shape}, rate={rate}, channels={channels}, ts={ts}")

    def handle_status(status):
        print(f"STATUS: {status}")

    def handle_error(error):
        print(f"ERROR: {error}")

    def handle_sources(sources):
        print(f"NDI Sources: {sources}")
        if sources and not capture_thread.ndi_source_name:
            # Automatically select the first source for this test if none is specified
            print(f"Test: Automatically selecting source: {sources[0]}")
            capture_thread.set_source_name(sources[0])
            # The thread needs to be started after the source is set, or handle it internally.
            # For this test, if it's already discovering, it should pick it up or be restarted.
            # The current run() loop logic expects ndi_source_name to be set before connection.

    def handle_ndi_info(info):
        print(f"NDI Info: {info}")

    # Test without specifying a source initially
    # capture_thread = NDILoopbackCaptureThread()

    # Test by specifying a source name (replace with a real NDI source name on your network)
    # Example: capture_thread = NDILoopbackCaptureThread(ndi_source_name="Your NDI Source Name")

    # For testing, let's assume we want to discover then select.
    capture_thread = NDILoopbackCaptureThread()


    capture_thread.new_video_frame_signal.connect(handle_video)
    capture_thread.new_audio_frame_signal.connect(handle_audio)
    capture_thread.status_signal.connect(handle_status)
    capture_thread.error_signal.connect(handle_error)
    capture_thread.ndi_sources_signal.connect(handle_sources)
    capture_thread.ndi_info_signal.connect(handle_ndi_info)

    print("Starting NDI capture thread for discovery...")
    capture_thread.start_capture() # Start (which calls self.start())

    # Keep the test running for a bit, then stop
    # In a real app, this would be managed by the application lifecycle.
    # QTimer.singleShot(20000, capture_thread.stop) # Stop after 20 seconds
    # QTimer.singleShot(22000, app.quit)

    # For this test, we need to let the app run until sources are found and one is selected.
    # If no source is specified at start, the handle_sources will try to set one.
    # Then the thread's internal logic should try to connect.

    # Let's simulate a delay then setting the source if not auto-selected by handle_sources
    def delayed_source_set():
        if not capture_thread.ndi_source_name and capture_thread.isRunning():
            # This is a fallback if handle_sources didn't set one (e.g. no sources initially)
            # Or if you want to manually override.
            # For the test, we rely on handle_sources.
            pass


    # QTimer.singleShot(5000, delayed_source_set) # Example of delayed manual set

    print("Test setup complete. Monitoring NDI signals. Press Ctrl+C to exit.")
    sys.exit(app.exec_()) # Start Qt event loop for signal handling

    # capture_thread.stop() # Ensure it stops if loop exits early
    print("NDI Loopback Test Finished")
