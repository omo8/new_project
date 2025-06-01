import time
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

# Placeholder for the actual NDI library
# In a real environment, you would import it as:
# import NDIlib as ndi
class ndi:
    class Source:
        def __init__(self, name=""):
            self.ndi_name = name

    @staticmethod
    def initialize():
        print("NDI: Initialized")
        return True

    @staticmethod
    def destroy():
        print("NDI: Destroyed")
        pass

    @staticmethod
    def find_create_v2(p_create_settings=None):
        print("NDI: Finder created")
        return "pNDI_find_dummy" # Dummy pointer

    @staticmethod
    def find_destroy(p_find):
        print(f"NDI: Finder {p_find} destroyed")
        pass

    _sources_found_flag = False # Class attribute to simulate state
    _simulated_sources = [Source("Source 1 (Simulated)"), Source("Source 2 (Simulated)")]

    @staticmethod
    def find_wait_for_sources(p_find, timeout_ms):
        print(f"NDI: Waiting for sources on {p_find} for {timeout_ms}ms")
        # Simulate finding sources after a short delay, only once
        if not ndi._sources_found_flag:
            time.sleep(min(timeout_ms / 1000.0, 0.5)) # Simulate some delay, but not too long
            ndi._sources_found_flag = True # Set flag so next call it returns True quickly
            return True # Indicate sources might be available

        # If already "found", subsequent calls might return immediately or after short poll
        time.sleep(min(timeout_ms / 1000.0, 0.1))
        return True


    @staticmethod
    def find_get_current_sources(p_find):
        print(f"NDI: Getting current sources from {p_find}")
        if ndi._sources_found_flag: # Only return sources if "found"
            return ndi._simulated_sources
        return []

    class RecvCreateV3:
        def __init__(self):
            self.color_format = None
            self.bandwidth = None
            self.allow_video_fields = False
            self.source_to_connect_to = None

    RECV_COLOR_FORMAT_BGRX_BGRA = "RECV_COLOR_FORMAT_BGRX_BGRA"
    RECV_COLOR_FORMAT_UYVY_BGRA = "RECV_COLOR_FORMAT_UYVY_BGRA"
    RECV_BANDWIDTH_HIGHEST = "RECV_BANDWIDTH_HIGHEST"

    @staticmethod
    def recv_create_v3(p_create_settings=None):
        print(f"NDI: Receiver created with settings: color_format={p_create_settings.color_format}")
        return "pNDI_recv_dummy"

    @staticmethod
    def recv_connect(p_recv, p_source):
        print(f"NDI: Receiver {p_recv} connecting to source {p_source.ndi_name}")
        pass

    @staticmethod
    def recv_destroy(p_recv):
        print(f"NDI: Receiver {p_recv} destroyed")
        pass

    FRAME_TYPE_NONE = 0
    FRAME_TYPE_VIDEO = 1
    FRAME_TYPE_AUDIO = 2
    FRAME_TYPE_METADATA = 3
    FRAME_TYPE_ERROR = 4

    _capture_frame_count = 0

    class VideoFrameV2:
        def __init__(self):
            self.data = None
            self.frame_rate_N = 30000
            self.frame_rate_D = 1001
            self.xres = 1920
            self.yres = 1080
            self.picture_aspect_ratio = 16/9.0
            self.line_stride_in_bytes = 1920 * 4

    class AudioFrameV2:
        def __init__(self):
            self.data = None
            self.sample_rate = 48000
            self.no_channels = 2
            self.timestamp = 0

    @staticmethod
    def recv_capture_v2(p_recv, timeout_ms):
        # print(f"NDI: Capturing frame on {p_recv} with timeout {timeout_ms}ms")
        time.sleep(1.0/30.0 * 0.9) # Simulate ~30fps with slight variation

        ndi._capture_frame_count +=1

        if ndi._capture_frame_count % 100 < 70 :
            frame_type = ndi.FRAME_TYPE_VIDEO
            video_frame = ndi.VideoFrameV2()
            sim_frame = np.random.randint(0, 256, size=(video_frame.yres, video_frame.xres, 4), dtype=np.uint8)
            video_frame.data = sim_frame
            return frame_type, video_frame, None, None
        elif ndi._capture_frame_count % 100 < 95:
            frame_type = ndi.FRAME_TYPE_AUDIO
            audio_frame = ndi.AudioFrameV2()
            num_samples = audio_frame.sample_rate // 30
            audio_frame.data = np.random.randn(num_samples * audio_frame.no_channels).astype(np.float32)
            audio_frame.timestamp = int(time.time() * 1_000_000_000) # Nanoseconds
            return frame_type, None, audio_frame, None
        else:
            frame_type = ndi.FRAME_TYPE_NONE
            return frame_type, None, None, None

    @staticmethod
    def recv_free_video_v2(p_recv, p_frame):
        pass

    @staticmethod
    def recv_free_audio_v2(p_recv, p_frame):
        pass

    @staticmethod
    def recv_free_metadata(p_recv, p_frame):
        pass


class NDILoopbackCaptureThread(QThread):
    new_video_frame_signal = pyqtSignal(object)  # Emits NumPy array (BGR)
    new_audio_frame_signal = pyqtSignal(object, int, int, int)  # data, sample_rate, channels, timestamp (nanoseconds)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    ndi_sources_signal = pyqtSignal(list)
    ndi_info_signal = pyqtSignal(str) # "WidthxHeight @ FPS"

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
        self._lock_source_name = False # To prevent race conditions when source_name is set

    def set_source_name(self, source_name):
        self.status_signal.emit(f"NDI source name set to: {source_name}")
        if self.ndi_source_name != source_name:
            self._lock_source_name = True
            self.ndi_source_name = source_name
            self.ndi_source_to_connect = None # Reset connection target
            self._lock_source_name = False
            # If already running and in discovery, the loop should pick up the new name.
            # If connected, a more complex reconnect logic would be needed. For now, assume it's set before connection.
            if self.isRunning() and self.pNDI_recv: # If already connected
                self.status_signal.emit("Source changed while connected. Triggering reconnect by stopping current capture.")
                self.running = False # This will stop the current run, it will be restarted by controller if needed


    def run(self):
        self.running = True
        self.status_signal.emit("NDI Loopback thread started.")

        if not ndi.initialize():
            self.error_signal.emit("Failed to initialize NDI.")
            self.running = False
            return

        try:
            self.pNDI_find = ndi.find_create_v2()
            if not self.pNDI_find:
                self.error_signal.emit("Failed to create NDI finder.")
                self.running = False
                # Cleanup done in finally
                return

            # Source Discovery Loop
            # This loop continues as long as thread is running and no specific source is connected.
            # Or if a specific source_name is given but not yet found.
            while self.running and not self.ndi_source_to_connect:
                if self._lock_source_name: # Wait if source name is being changed
                    time.sleep(0.05)
                    continue

                self.status_signal.emit("Discovering NDI sources...")
                # Reset the simulated sources found flag for each discovery attempt cycle if no source is selected
                if not self.ndi_source_name:
                    ndi._sources_found_flag = False

                if ndi.find_wait_for_sources(self.pNDI_find, 1000): # Wait 1 sec
                    sources = ndi.find_get_current_sources(self.pNDI_find)
                    if sources:
                        source_names = [s.ndi_name for s in sources]
                        self.ndi_sources_signal.emit(source_names)
                        self.status_signal.emit(f"Found NDI sources: {source_names}")

                        if self.ndi_source_name:
                            found_source = next((s for s in sources if s.ndi_name == self.ndi_source_name), None)
                            if found_source:
                                self.ndi_source_to_connect = found_source
                                self.status_signal.emit(f"Target NDI source '{self.ndi_source_name}' found.")
                                # Break discovery loop once specific source is found
                                break
                            else:
                                self.status_signal.emit(f"Specified NDI source '{self.ndi_source_name}' not found. Will retry.")
                        else:
                            self.status_signal.emit("No NDI source specified. Emitting available sources. Waiting for selection.")
                    else:
                        self.ndi_sources_signal.emit([]) # Emit empty list
                        self.status_signal.emit("No NDI sources found currently.")
                else: # find_wait_for_sources timed out without (new) sources
                    self.ndi_sources_signal.emit([]) # Emit empty list
                    self.status_signal.emit("Timeout waiting for NDI sources.")

                if not self.running: break # Check if stop() was called
                time.sleep(2) # Wait before retrying discovery

            if not self.running:
                self.status_signal.emit("NDI thread stopped during source discovery.")
                return # Cleanup in finally

            if not self.ndi_source_to_connect:
                self.error_signal.emit(f"Could not connect to NDI source: {self.ndi_source_name if self.ndi_source_name else 'Not specified'}. Stopping thread.")
                self.running = False
                return # Cleanup in finally

            # Create NDI Receiver
            recv_create_attrs = ndi.RecvCreateV3()
            recv_create_attrs.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
            recv_create_attrs.bandwidth = ndi.RECV_BANDWIDTH_HIGHEST
            recv_create_attrs.allow_video_fields = False

            self.pNDI_recv = ndi.recv_create_v3(recv_create_attrs)
            if not self.pNDI_recv:
                self.error_signal.emit("Failed to create NDI receiver.")
                self.running = False
                return # Cleanup in finally

            ndi.recv_connect(self.pNDI_recv, self.ndi_source_to_connect)
            self.status_signal.emit(f"NDI receiver connected to '{self.ndi_source_to_connect.ndi_name}'.")

            # Capture Loop
            while self.running:
                frame_type, video_frame, audio_frame, metadata_frame = ndi.recv_capture_v2(self.pNDI_recv, 1000)

                if frame_type == ndi.FRAME_TYPE_VIDEO:
                    if video_frame.data is not None:
                        frame_bgr = np.copy(video_frame.data[:, :, :3])
                        self.new_video_frame_signal.emit(frame_bgr)

                        new_width, new_height = video_frame.xres, video_frame.yres
                        new_fps = round(video_frame.frame_rate_N / video_frame.frame_rate_D, 2) if video_frame.frame_rate_D > 0 else 0

                        if (self.frame_width != new_width or
                            self.frame_height != new_height or
                            self.fps != new_fps):
                            self.frame_width, self.frame_height, self.fps = new_width, new_height, new_fps
                            self.ndi_info_signal.emit(f"{self.frame_width}x{self.frame_height} @ {self.fps} FPS")
                    ndi.recv_free_video_v2(self.pNDI_recv, video_frame)

                elif frame_type == ndi.FRAME_TYPE_AUDIO:
                    if audio_frame.data is not None:
                        audio_data_copy = np.copy(audio_frame.data)
                        self.new_audio_frame_signal.emit(
                            audio_data_copy,
                            audio_frame.sample_rate,
                            audio_frame.no_channels,
                            audio_frame.timestamp
                        )
                    ndi.recv_free_audio_v2(self.pNDI_recv, audio_frame)

                elif frame_type == ndi.FRAME_TYPE_METADATA:
                    ndi.recv_free_metadata(self.pNDI_recv, metadata_frame)

                elif frame_type == ndi.FRAME_TYPE_ERROR:
                    self.error_signal.emit("Error frame received from NDI. Connection might be lost.")
                    # Consider if this should stop the loop or try to re-establish
                    # For now, it continues, but this is a sign of trouble.

                # No new frame is FRAME_TYPE_NONE, normal timeout, do nothing.
                if not self.running: break

            self.status_signal.emit("NDI capture loop ended.")

        except Exception as e:
            self.error_signal.emit(f"NDI thread runtime error: {e}")
            import traceback
            print(traceback.format_exc()) # For more detailed debugging if errors occur
        finally:
            self.status_signal.emit("Cleaning up NDI resources...")
            if self.pNDI_recv:
                ndi.recv_destroy(self.pNDI_recv)
                self.pNDI_recv = None
            if self.pNDI_find:
                ndi.find_destroy(self.pNDI_find)
                self.pNDI_find = None
            ndi.destroy()
            ndi._sources_found_flag = False # Reset for next full start
            ndi._capture_frame_count = 0 # Reset for dummy data generation
            self.running = False
            self.status_signal.emit("NDI Loopback thread finished.")

    def stop(self):
        self.status_signal.emit("Stopping NDI Loopback thread...")
        self.running = False
        if self.isFinished(): # If run() already exited
            return
        self.wait(3000) # Wait for thread to finish, with a timeout
        if self.isRunning():
            self.error_signal.emit("NDI thread did not stop gracefully.")
            # self.terminate() # Avoid terminate if possible, can lead to issues

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QComboBox
    import sys

    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NDI Loopback Test")
            self.ndi_thread = NDILoopbackCaptureThread()

            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            layout = QVBoxLayout(self.central_widget)

            self.status_label = QLabel("Status: Idle")
            layout.addWidget(self.status_label)

            self.info_label = QLabel("Info: -")
            layout.addWidget(self.info_label)

            self.sources_combo = QComboBox()
            layout.addWidget(self.sources_combo)

            self.start_button = QPushButton("Start NDI Loopback")
            self.start_button.clicked.connect(self.start_ndi)
            layout.addWidget(self.start_button)

            self.stop_button = QPushButton("Stop NDI Loopback")
            self.stop_button.clicked.connect(self.stop_ndi)
            layout.addWidget(self.stop_button)

            self.ndi_thread.status_signal.connect(lambda msg: self.status_label.setText(f"Thread Status: {msg}"))
            self.ndi_thread.error_signal.connect(lambda msg: print(f"ERROR: {msg}"))
            self.ndi_thread.ndi_sources_signal.connect(self.update_sources_combo)
            self.ndi_thread.new_video_frame_signal.connect(self.handle_video)
            self.ndi_thread.new_audio_frame_signal.connect(self.handle_audio)
            self.ndi_thread.ndi_info_signal.connect(lambda info: self.info_label.setText(f"NDI Info: {info}"))

        def update_sources_combo(self, sources):
            print(f"APP: NDI Sources: {sources}")
            current_selection = self.sources_combo.currentText()
            self.sources_combo.clear()
            self.sources_combo.addItems(sources)
            if current_selection in sources:
                self.sources_combo.setCurrentText(current_selection)
            elif sources:
                 # Optionally auto-select first discovered source if nothing was selected
                 # self.sources_combo.setCurrentIndex(0)
                 # self.ndi_thread.set_source_name(self.sources_combo.currentText())
                 pass


        def start_ndi(self):
            if not self.ndi_thread.isRunning():
                selected_source = self.sources_combo.currentText()
                if not selected_source and ndi._simulated_sources: # For testing, auto pick if combo is empty but sources exist
                    print("No source selected in UI, but simulated sources exist. Auto-selecting first for test.")
                    self.ndi_thread.set_source_name(ndi._simulated_sources[0].ndi_name)
                elif selected_source:
                     self.ndi_thread.set_source_name(selected_source)
                else:
                    print("No NDI source selected in UI and no simulated sources to auto-pick. Thread will discover.")
                    self.ndi_thread.set_source_name(None) # Explicitly set to None to trigger discovery mode

                self.ndi_thread.start()
                self.status_label.setText("Status: Started")
            else:
                self.status_label.setText("Status: Already running")

        def stop_ndi(self):
            if self.ndi_thread.isRunning():
                self.ndi_thread.stop()
                # self.ndi_thread.wait() # wait() is called in stop()
                self.status_label.setText("Status: Stopped")
            else:
                self.status_label.setText("Status: Already stopped")

        def handle_video(self, frame):
            # In a real app, display this frame. For test, just log.
            if self.ndi_thread._capture_frame_count % 30 == 0: # Log every 30th frame
                 print(f"APP: New video frame - shape: {frame.shape}, dtype: {frame.dtype}")

        def handle_audio(self, data, sample_rate, channels, timestamp):
            if self.ndi_thread._capture_frame_count % 30 == 0: # Log every 30th audio frame bundle
                print(f"APP: New audio frame - samples: {len(data)//channels if channels else 0}, rate: {sample_rate}, ch: {channels}, ts: {timestamp}")

        def closeEvent(self, event):
            self.stop_ndi()
            super().closeEvent(event)

    app = QApplication(sys.argv)
    window = TestWindow()
    window.setGeometry(100, 100, 400, 200)
    window.show()
    sys.exit(app.exec_())
