import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
                             QComboBox, QLabel, QHBoxLayout, QStatusBar, QGroupBox, QFormLayout, QTextEdit)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import numpy as np
import cv2 # For NDICaptureThread (OpenCV based)

import json # For config
from PyQt5.QtCore import QStandardPaths # For config path

# Capture Threads
from ndi_loopback_capture_thread import NDILoopbackCaptureThread
from vmix_virtual_camera_capture_thread import VmixVirtualCameraCaptureThread
# Tally Threads
from vmix_http_tally_thread import VmixHttpTallyThread
# Placeholder for existing vMix TCP Tally Thread (if it was in a separate file)
# from vmix_tally_thread import VmixTallyThread # Assuming it might exist

# --- Placeholder for original GenericOpenCVCaptureThread ---
# (formerly NDICaptureThread, for generic OpenCV NDI/camera)
# This might be used for "NDI Virtual Input (OpenCV)".
# Or, it might be deprecated if specific handlers like NDILoopback and VmixVirtualCamera cover needs.
# For now, keeping it as a reference for how a generic OpenCV source might be handled.
class GenericOpenCVCaptureThread(QThread): # Renamed for clarity
    new_frame_signal = pyqtSignal(object)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    ndi_info_signal = pyqtSignal(str)

    def __init__(self, ndi_source_name=None, parent=None):
        super().__init__(parent)
        self.ndi_source_name = ndi_source_name
        self.running = False
        self.capture = None
        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0

    def run(self):
        self.running = True
        self.status_signal.emit("NDI Virtual Input thread started.")
        try:
            # This is a simplified OpenCV NDI capture; real NDI with OpenCV is more complex
            # and often requires specific environment variables or NDI SDK integration.
            # For this placeholder, we'll simulate finding a source if a name is given.
            if self.ndi_source_name:
                # In a real scenario, OpenCV's VideoCapture might open an NDI source
                # if the NDI SDK routes it to behave like a webcam, or via a specific backend.
                # e.g., os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "video_format;ndi_source_name"
                # For now, let's assume it can open something if a name is provided.
                # self.capture = cv2.VideoCapture(self.ndi_source_name, cv2.CAP_FFMPEG) # Example
                self.status_signal.emit(f"Attempting to connect to {self.ndi_source_name} via OpenCV (simulated).")
                # Simulate connection success for testing UI
                self.frame_width = 1920
                self.frame_height = 1080
                self.fps = 30
                self.ndi_info_signal.emit(f"Res: {self.frame_width}x{self.frame_height}, FPS: {self.fps:.2f} (Simulated OpenCV)")
                dummy_frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)

                while self.running:
                    # Simulate frame capture
                    cv2.putText(dummy_frame, "OpenCV NDI Placeholder", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                    self.new_frame_signal.emit(dummy_frame)
                    self.msleep(int(1000/self.fps) if self.fps > 0 else 33) # simulate frame rate
            else:
                self.error_signal.emit("No NDI source name provided for OpenCV capture.")

        except Exception as e:
            self.error_signal.emit(f"OpenCV NDI Error: {str(e)}")
        finally:
            if self.capture:
                self.capture.release()
            self.status_signal.emit("NDI Virtual Input thread stopped.")

    def stop(self):
        self.running = False
        self.wait()
# --- End Placeholder NDICaptureThread ---


import subprocess
import os
import tempfile
import time
import requests # For fetching vMix input names
import xml.etree.ElementTree as ET # For parsing vMix API XML
from queue import Queue, Empty, Full

# --- SRTStreamerThread with Audio Integration ---
import threading # For FFmpeg stderr reader thread

class SRTStreamerThread(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    ffmpeg_log_signal = pyqtSignal(str) # Signal for FFmpeg stderr lines

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ffmpeg_stderr_thread = None
        self.running = False
        self.ffmpeg_process = None
        self.srt_url = "srt://127.0.0.1:1234" # Example URL

        # Video parameters
        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0

        # Audio parameters (to be set before starting)
        self.audio_sample_rate = 0
        self.audio_channels = 0

        self.video_frame_queue = Queue(maxsize=60) # Approx 2 seconds of video frames at 30fps
        self.audio_frame_queue = Queue(maxsize=120) # Approx 2 seconds of audio data chunks

        self.audio_pipe_path = None
        self.audio_pipe_fd = None # File descriptor for writing to named pipe

        self._audio_writer_thread = None # Separate thread for writing audio

    def set_video_params(self, width, height, fps):
        self.frame_width = width
        self.frame_height = height
        self.fps = fps
        self.status_signal.emit(f"SRT video params set: {width}x{height} @ {fps}fps")

    def set_audio_params(self, sample_rate, channels):
        self.audio_sample_rate = sample_rate
        self.audio_channels = channels
        self.status_signal.emit(f"SRT audio params set: {sample_rate}Hz, {channels}ch")

    def _start_ffmpeg_process(self):
        if not self.frame_width or not self.frame_height or not self.fps:
            self.error_signal.emit("FFmpeg: Video parameters not set.")
            return False

        # Audio pipe creation only if audio is enabled
        self.audio_pipe_path = None # Ensure it's None if audio is disabled
        if self.audio_channels > 0 and self.audio_sample_rate > 0:
            try:
                if os.name == 'posix':
                    self.audio_pipe_path = os.path.join(tempfile.gettempdir(), f"ffmpeg_audio_pipe_{os.getpid()}")
                    if os.path.exists(self.audio_pipe_path):
                        os.unlink(self.audio_pipe_path)
                    os.mkfifo(self.audio_pipe_path)
                    self.status_signal.emit(f"Created named pipe for audio: {self.audio_pipe_path}")
                else: # Fallback for non-POSIX (Windows)
                    fd, self.audio_pipe_path = tempfile.mkstemp(suffix=".rawaudio")
                    os.close(fd)
                    self.status_signal.emit(f"Using temp file as audio input (Windows fallback): {self.audio_pipe_path}")
            except Exception as e:
                self.error_signal.emit(f"Failed to create audio pipe/file: {e}")
                # Do not return False here if video can still proceed without audio
                self.audio_pipe_path = None # Ensure pipe path is None if creation failed
                self.status_signal.emit("Warning: Audio pipe creation failed. Proceeding without audio if possible.")
                # Fallback to no audio for FFmpeg if pipe failed
                # self.audio_channels = 0 # This would modify the setting, maybe not desired.
                                        # Instead, FFmpeg command will check audio_pipe_path.
        elif self.audio_channels == 0:
            self.status_signal.emit("FFmpeg: Audio channels set to 0 by configuration. Proceeding without audio input.")
        else: # Sample rate might be 0 if channels > 0, or other invalid combo
            self.error_signal.emit(f"FFmpeg: Audio parameters invalid (Sample Rate: {self.audio_sample_rate}Hz, Channels: {self.audio_channels}ch). Cannot configure audio.")
            # Proceeding without audio if video params are fine
            self.audio_pipe_path = None # Ensure no audio pipe is used

        command = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking

            # Video Input (from stdin)
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{self.frame_width}x{self.frame_height}',
            '-r', str(self.fps),
            '-thread_queue_size', '512',
            '-i', 'pipe:0',
        ]

        # Add audio input to command ONLY if channels, sample rate, and pipe path are valid
        if self.audio_channels > 0 and self.audio_sample_rate > 0 and self.audio_pipe_path:
            command.extend([
                # Audio Input (from named pipe/file)
                '-f', 'f32le',
                '-ar', str(self.audio_sample_rate),
                '-ac', str(self.audio_channels),
                '-thread_queue_size', '512',
                '-i', self.audio_pipe_path,
            ])

        command.extend([
            # Video Codec
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            '-b:v', '2500k',
        ])

        # Add audio codec to command ONLY if audio input was successfully added
        if self.audio_channels > 0 and self.audio_sample_rate > 0 and self.audio_pipe_path:
            command.extend([
                # Audio Codec
                '-c:a', 'aac',
                '-b:a', '128k',
                '-strict', '-2',
            ])
        else:
            # No valid audio input, so tell FFmpeg to not output an audio track
            command.extend(['-an'])


        command.extend([
            # Output Format (SRT using MPEG-TS container)
            '-f', 'mpegts',
            '-muxdelay', '0.1',
            self.srt_url
        ])

        self.status_signal.emit(f"Starting FFmpeg with command: {' '.join(command)}")
        try:
            # Ensure stderr is piped
            self.ffmpeg_process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, # Usually not needed unless debugging FFmpeg stdout
                stderr=subprocess.PIPE
            )
            self.status_signal.emit("FFmpeg process started.")

            # Start stderr reader thread
            self.ffmpeg_stderr_thread = threading.Thread(target=self._read_ffmpeg_stderr, daemon=True)
            self.ffmpeg_stderr_thread.start()

            return True
        except FileNotFoundError:
            self.error_signal.emit("FFmpeg executable not found. Please ensure FFmpeg is installed and in PATH.")
            return False
        except Exception as e:
            self.error_signal.emit(f"Failed to start FFmpeg: {str(e)}")
            return False

    def _video_feed_loop(self):
        self.status_signal.emit("Video feed loop started.")
        while self.running and self.ffmpeg_process and self.ffmpeg_process.stdin:
            try:
                frame = self.video_frame_queue.get(timeout=0.1) # Timeout to allow checking self.running
                if frame is None: # Sentinel for stopping
                    break
                self.ffmpeg_process.stdin.write(frame.tobytes())
            except Empty:
                continue
            except (IOError, BrokenPipeError) as e:
                self.error_signal.emit(f"FFmpeg video stdin error: {e}")
                break
            except Exception as e:
                self.error_signal.emit(f"Video feed loop error: {e}")
                break
        self.status_signal.emit("Video feed loop finished.")

    def _audio_feed_loop(self):
        self.status_signal.emit("Audio feed loop starting...")
        if not self.audio_pipe_path:
            self.error_signal.emit("Audio pipe path not set.")
            return

        audio_pipe = None
        try:
            # Open the named pipe for writing. This might block until FFmpeg opens it for reading.
            # For regular files (Windows fallback), it opens immediately.
            self.status_signal.emit(f"Attempting to open audio pipe for writing: {self.audio_pipe_path}")
            # Use 'ab' for Windows file fallback to append, 'wb' for POSIX fifo.
            # However, FFmpeg expects a continuous stream. Reopening might be an issue.
            # Let's try 'wb' and rely on FFmpeg to keep the pipe open.
            # For POSIX fifo, it must be opened after ffmpeg starts.
            # For Windows temp file, we can open it, but ffmpeg might read it once and stop.
            # This part is tricky cross-platform.

            # Wait a brief moment for FFmpeg to potentially open the pipe
            time.sleep(0.5) # Small delay

            # On POSIX, os.open with O_WRONLY | O_NONBLOCK can be used to open without blocking,
            # then select/poll to wait for it to be ready. Simpler: blocking open in thread.
            audio_pipe = open(self.audio_pipe_path, 'wb')
            self.status_signal.emit(f"Audio pipe opened for writing: {self.audio_pipe_path}")

            while self.running:
                try:
                    audio_data, sr, ch, ts = self.audio_frame_queue.get(timeout=0.1)
                    if audio_data is None: # Sentinel
                        break
                    audio_pipe.write(audio_data.astype(np.float32).tobytes())
                    audio_pipe.flush() # Ensure data is sent
                except Empty:
                    continue
                except (IOError, BrokenPipeError) as e:
                    self.error_signal.emit(f"Audio pipe write error: {e}")
                    break # Exit loop on pipe error
                except Exception as e:
                    self.error_signal.emit(f"Audio feed loop error: {e}")
                    break
        except Exception as e:
            self.error_signal.emit(f"Failed to open or write to audio pipe {self.audio_pipe_path}: {e}")
        finally:
            if audio_pipe:
                try:
                    audio_pipe.close()
                    self.status_signal.emit(f"Closed audio pipe: {self.audio_pipe_path}")
                except Exception as e:
                    self.error_signal.emit(f"Error closing audio pipe: {e}")
            # Cleanup named pipe on POSIX
            if os.name == 'posix' and self.audio_pipe_path and os.path.exists(self.audio_pipe_path):
                try:
                    if os.path.islink(self.audio_pipe_path) or os.path.isfile(self.audio_pipe_path) or isinstance(self.audio_pipe_path, str) and os.path.exists(self.audio_pipe_path) and os.path.islink(self.audio_pipe_path) == False and os.path.isdir(self.audio_pipe_path) == False : # check if it is a fifo
                         os.unlink(self.audio_pipe_path)
                         self.status_signal.emit(f"Removed audio pipe: {self.audio_pipe_path}")
                except Exception as e:
                     self.error_signal.emit(f"Error removing audio pipe {self.audio_pipe_path}: {e}")
            elif os.name != 'posix' and self.audio_pipe_path and os.path.exists(self.audio_pipe_path): # Temp file on Windows
                 try:
                    os.unlink(self.audio_pipe_path)
                    self.status_signal.emit(f"Removed temp audio file: {self.audio_pipe_path}")
                 except Exception as e:
                    self.error_signal.emit(f"Error removing temp audio file {self.audio_pipe_path}: {e}")


        self.status_signal.emit("Audio feed loop finished.")


    def run(self):
        self.running = True

        if not self._start_ffmpeg_process():
            self.running = False
            self.error_signal.emit("Failed to initialize FFmpeg process. SRT Streamer thread stopping.")
            return

        self.status_signal.emit(f"SRT Streamer thread started for {self.srt_url}. Video: {self.frame_width}x{self.frame_height}@{self.fps}fps. Audio: {self.audio_sample_rate}Hz, {self.audio_channels}ch.")

        # Start the audio feeding thread/loop
        # Running audio feed in a separate QThread for isolation
        self._audio_writer_thread = QThread() # This is not how QThread is meant to be used for just a function.
                                            # Better to make _audio_feed_loop a method called by a QThread instance or use threading.Thread

        # For simplicity, let's use threading.Thread for the audio loop to avoid QThread complexities here
        import threading
        audio_thread = threading.Thread(target=self._audio_feed_loop, daemon=True)
        audio_thread.start()

        # Video feed loop (runs in this QThread's run method)
        self._video_feed_loop()

        # Wait for audio thread to finish if it's still running
        if audio_thread.is_alive():
            self.status_signal.emit("Waiting for audio feed thread to complete...")
            # Signal audio loop to stop by clearing queue and putting sentinel if needed
            # Or rely on self.running flag.
            audio_thread.join(timeout=2.0) # Wait for max 2 seconds

        self._cleanup_ffmpeg()
        self.status_signal.emit("SRT Streamer thread stopped.")

    def _read_ffmpeg_stderr(self):
        self.status_signal.emit("FFmpeg stderr reader thread started.")
        try:
            if self.ffmpeg_process and self.ffmpeg_process.stderr:
                for line in iter(self.ffmpeg_process.stderr.readline, b''):
                    if not self.running and not line: # Process likely stopped, and no more output
                        break
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    self.ffmpeg_log_signal.emit(decoded_line)
                # Once loop finishes, ensure stderr is closed
                if self.ffmpeg_process and self.ffmpeg_process.stderr and not self.ffmpeg_process.stderr.closed:
                    self.ffmpeg_process.stderr.close()
        except Exception as e:
            self.error_signal.emit(f"Error in FFmpeg stderr reader: {e}")
        finally:
            self.status_signal.emit("FFmpeg stderr reader thread finished.")


    def push_frame(self, frame): # Video frame
        if not self.running or self.ffmpeg_process is None:
            return
        try:
            self.video_frame_queue.put_nowait(frame)
        except Full:
            self.error_signal.emit("SRT: Video frame queue full. Dropping frame.")
            pass # Frame dropped

    def push_audio_frame(self, audio_data, sample_rate, channels, timestamp_ns):
        if not self.running: # Check running status
            return
        # Audio params should ideally be set before streaming starts and match.
        # For now, we assume they are consistent with what FFmpeg was configured with.
        if sample_rate != self.audio_sample_rate or channels != self.audio_channels:
            self.error_signal.emit(f"Audio parameter mismatch: Expected {self.audio_sample_rate}Hz/{self.audio_channels}ch, got {sample_rate}Hz/{channels}ch. Audio may be distorted.")
            # Ideally, FFmpeg should be restarted or handle this, but that's complex.
            # For now, we'll try to push it anyway, FFmpeg might handle it or fail.

        try:
            # Ensure audio_data is float32 as expected by FFmpeg's f32le
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            self.audio_frame_queue.put_nowait((audio_data, sample_rate, channels, timestamp_ns))
        except Full:
            self.error_signal.emit("SRT: Audio frame queue full. Dropping audio frame.")
            pass # Audio frame dropped
        except Exception as e:
            self.error_signal.emit(f"Error queueing audio frame: {e}")


    def _cleanup_ffmpeg(self):
        self.status_signal.emit("Cleaning up FFmpeg process...")
        if self.ffmpeg_process:
            if self.ffmpeg_process.stdin:
                try:
                    self.ffmpeg_process.stdin.close()
                except Exception as e:
                    self.error_signal.emit(f"Error closing FFmpeg stdin: {e}")

            # Terminate FFmpeg process
            try:
                self.ffmpeg_process.terminate() # Send SIGTERM
                self.ffmpeg_process.wait(timeout=5) # Wait for graceful shutdown
                self.status_signal.emit("FFmpeg process terminated.")
            except subprocess.TimeoutExpired:
                self.error_signal.emit("FFmpeg process did not terminate gracefully, killing.")
                self.ffmpeg_process.kill() # Send SIGKILL
                self.ffmpeg_process.wait()
                self.status_signal.emit("FFmpeg process killed.")
            except Exception as e:
                self.error_signal.emit(f"Error terminating FFmpeg: {e}")

            self.ffmpeg_process = None

        # Audio pipe cleanup is handled in _audio_feed_loop's finally block for POSIX
        # For Windows temp file, it's also handled there.
        if self.audio_pipe_path and os.name != 'posix' and os.path.exists(self.audio_pipe_path):
             # Ensure temp file is removed if _audio_feed_loop didn't run or complete cleanup
            try:
                os.unlink(self.audio_pipe_path)
                self.status_signal.emit(f"Cleaned up temp audio file: {self.audio_pipe_path}")
            except Exception as e:
                self.error_signal.emit(f"Error cleaning up temp audio file during _cleanup_ffmpeg: {e}")
        self.audio_pipe_path = None


    def stop(self):
        self.status_signal.emit("Stopping SRT Streamer thread...")
        self.running = False # Signal loops to stop

        # Put sentinels in queues to unblock threads
        try:
            self.video_frame_queue.put_nowait(None)
        except Full: # If queue is full, loop will eventually timeout or see self.running
            pass
        try:
            self.audio_frame_queue.put_nowait((None,0,0,0))
        except Full:
            pass

        if self.isRunning():
            self.wait(7000) # Wait for FFmpeg and loops to finish (increased timeout)

        # Ensure cleanup if thread finishes abruptly or wait times out
        self._cleanup_ffmpeg()
        self.status_signal.emit("SRT Streamer thread definitively stopped.")

# --- End SRTStreamerThread with Audio Integration ---


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Streaming App")
        self.setGeometry(100, 100, 800, 700) # Increased height for log

        # Capture Threads
        self.ndi_opencv_thread = None
        self.ndi_loopback_thread = None
        self.vmix_virtual_cam_thread = None
        self.ndi_loopback_discover_thread = None

        # Tally Threads
        self.vmix_tcp_tally_thread = None # Assuming this is the existing VmixTallyThread placeholder
        self.vmix_http_tally_thread = None

        # SRT Streamer Thread
        self.srt_streamer_thread = SRTStreamerThread()

        # Audio parameters - these will be updated by the source thread (e.g. NDI Loopback)
        # and then used to configure SRTStreamerThread before it starts FFmpeg.
        self.current_pgm_audio_sample_rate = 0
        self.current_pgm_audio_channels = 0

        # vMix Input Name Cache
        self.vmix_input_cache = {}
        self.last_input_cache_refresh_time = 0
        self.INPUT_CACHE_REFRESH_INTERVAL = 30  # seconds
        self.VMIX_HOST = '127.0.0.1'
        self.VMIX_TCP_PORT = 8099 # Default vMix TCP Tally port
        self.VMIX_HTTP_PORT = 8088

        # Default settings (some might be overridden by loaded config)
        self.DEFAULT_PGM_MODE = "NDI Loopback"
        self.DEFAULT_TALLY_MODE = "HTTP Tally"
        self.DEFAULT_SRT_URL = "srt://127.0.0.1:1234"
        self.DEFAULT_BACKEND_WS_URL = "ws://localhost:8080/ws"
        self.DEFAULT_NDI_OPENCV_SOURCE = "0" # Default for generic OpenCV source (e.g., webcam index)
        self.DEFAULT_HTTP_TALLY_POLL_MS = 250
        self.DEFAULT_CACHE_REFRESH_S = 30

        self.loaded_ndi_source_name = None # For restoring NDI source selection after discovery

        self._init_ui()
        self._connect_signals()

        self._load_config() # Load config after UI is set up

        # Initial UI state based on potentially loaded config or defaults
        self._on_pgm_source_mode_changed(self.pgm_source_combo.currentText())
        self._on_tally_mode_changed(self.tally_mode_combo.currentText())

        # Initial population of vMix input names if a tally mode is active by default or loaded
        if self.tally_mode_combo.currentText() != "None":
            self._fetch_and_cache_vmix_input_names(force_refresh=True)


    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # PGM Source Configuration Group
        pgm_source_group = QGroupBox("Program Source Configuration")
        pgm_source_layout = QFormLayout()
        self.pgm_source_combo = QComboBox()
        self.pgm_source_combo.addItems([
            "NDI Loopback",
            "NDI Virtual Input (OpenCV)",
            "vMix Virtual Camera"
        ])
        pgm_source_layout.addRow(QLabel("Program Source:"), self.pgm_source_combo)
        self.ndi_source_combo = QComboBox()
        self.ndi_source_combo.setDisabled(True)
        pgm_source_layout.addRow(QLabel("NDI Source (if applicable):"), self.ndi_source_combo)

        # Add QLineEdit for NDI Virtual Input (OpenCV) source name/index
        self.ndi_cam_index_input = QLineEdit(self.DEFAULT_NDI_OPENCV_SOURCE) # Placeholder for NDI/Cam index
        pgm_source_layout.addRow(QLabel("NDI/Cam Index/Name (OpenCV):"), self.ndi_cam_index_input)

        pgm_source_group.setLayout(pgm_source_layout)
        layout.addWidget(pgm_source_group)

        # Tally Configuration Group
        tally_group = QGroupBox("Tally Configuration")
        tally_layout = QFormLayout()
        self.tally_mode_combo = QComboBox()
        self.tally_mode_combo.addItems(["HTTP Tally", "TCP Tally", "None"]) # HTTP Tally first
        tally_layout.addRow(QLabel("Tally Mode:"), self.tally_mode_combo)
        self.tally_button = QPushButton("Connect Tally")
        self.tally_button.setCheckable(True)
        tally_layout.addWidget(self.tally_button)
        self.pgm_tally_label = QLabel("PGM: -")
        self.pvw_tally_label = QLabel("PVW: -")
        tally_layout.addRow(self.pgm_tally_label)
        tally_layout.addRow(self.pvw_tally_label)
        tally_group.setLayout(tally_layout)
        layout.addWidget(tally_group)

        # Streaming & Backend Configuration Group
        streaming_config_group = QGroupBox("Streaming & Backend Configuration")
        streaming_config_layout = QFormLayout()
        self.srt_url_input = QLineEdit(self.DEFAULT_SRT_URL)
        streaming_config_layout.addRow(QLabel("SRT URL:"), self.srt_url_input)
        self.backend_url_input = QLineEdit(self.DEFAULT_BACKEND_WS_URL)
        streaming_config_layout.addRow(QLabel("Backend WS URL:"), self.backend_url_input)
        streaming_config_group.setLayout(streaming_config_layout)
        layout.addWidget(streaming_config_group)

        # Streaming Control Group
        streaming_group = QGroupBox("Streaming Control")
        streaming_layout = QVBoxLayout()
        self.toggle_stream_button = QPushButton("Start Streaming")
        self.toggle_stream_button.setCheckable(True)
        streaming_layout.addWidget(self.toggle_stream_button)
        streaming_group.setLayout(streaming_layout)
        layout.addWidget(streaming_group)

        # Log Output
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout()
        self.log_output_area = QTextEdit() # Renamed from self.log_output for clarity
        self.log_output_area.setReadOnly(True)
        self.log_output_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap) # Optional
        log_layout.addWidget(self.log_output_area)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Video Preview and Status Bar
        self.video_preview_label = QLabel("Video preview will appear here.")
        self.video_preview_label.setAlignment(Qt.AlignCenter)
        self.video_preview_label.setMinimumSize(640, 360) # This might be too large now with log
        self.video_preview_label.setMaximumHeight(360) # Constrain preview height
        layout.addWidget(self.video_preview_label)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status_bar("Application started. Configuration loaded.")


    def _connect_signals(self):
        self.toggle_stream_button.clicked.connect(self.toggle_streaming)
        self.pgm_source_combo.currentTextChanged.connect(self._on_pgm_source_mode_changed)
        self.tally_mode_combo.currentTextChanged.connect(self._on_tally_mode_changed)
        self.tally_button.clicked.connect(self.toggle_tally_connection)

        # SRT Streamer signals
        self.srt_streamer_thread.status_signal.connect(self.update_status_bar)
        self.srt_streamer_thread.error_signal.connect(self.update_status_bar)
        self.srt_streamer_thread.ffmpeg_log_signal.connect(self._update_ffmpeg_log)


    def _update_ffmpeg_log(self, log_line):
        # Append FFmpeg log line to the dedicated log area
        # Ensure this is thread-safe; QTextEdit.append() is.
        self.log_output_area.append(f"[FFMPEG] {log_line}")
        # self.log_output_area.verticalScrollBar().setValue(self.log_output_area.verticalScrollBar().maximum()) # Auto-scroll

    def _start_ndi_discovery(self):
        if self.ndi_loopback_discover_thread and self.ndi_loopback_discover_thread.isRunning():
            self.update_status_bar("NDI discovery thread already running.")
            return

        if self.ndi_loopback_discover_thread: # Cleanup old instance if exists
            self.ndi_loopback_discover_thread.stop()
            self.ndi_loopback_discover_thread.deleteLater()

        self.ndi_loopback_discover_thread = NDILoopbackCaptureThread(ndi_source_name=None) # Discovery mode
        self.ndi_loopback_discover_thread.ndi_sources_signal.connect(self._update_ndi_source_combobox)
        self.ndi_loopback_discover_thread.status_signal.connect(self.update_status_bar)
        self.ndi_loopback_discover_thread.error_signal.connect(self.update_status_bar)
        self.ndi_loopback_discover_thread.start()
        self.update_status_bar("NDI source discovery started for Loopback mode.")

    def _stop_ndi_discovery(self):
        if self.ndi_loopback_discover_thread and self.ndi_loopback_discover_thread.isRunning():
            self.ndi_loopback_discover_thread.stop()
            self.ndi_loopback_discover_thread.deleteLater()
            self.ndi_loopback_discover_thread = None
            self.update_status_bar("NDI source discovery stopped.")
        # Clear the NDI sources combobox when discovery stops or mode changes
        self.ndi_source_combo.clear()
        self.ndi_source_combo.setDisabled(True)
        self.update_status_bar("NDI sources cleared.")


    def _on_pgm_source_mode_changed(self, mode_text): # Renamed from _on_ndi_mode_changed
        self._stop_ndi_discovery()
        self.ndi_source_combo.setDisabled(True)
        self.ndi_source_combo.clear()
        # Ensure all capture threads are stopped when PGM source mode changes to avoid conflicts
        self._stop_all_capture_threads()
        if self.toggle_stream_button.isChecked(): # If streaming was active, uncheck button
            self.toggle_stream_button.setChecked(False)
            # self.toggle_stream_button.setText("Start Streaming") # Handled by toggle_streaming itself
            if self.srt_streamer_thread.isRunning():
                self.srt_streamer_thread.stop()


        if mode_text == "NDI Loopback":
            self.ndi_source_combo.setDisabled(False)
            self._start_ndi_discovery()
            self.update_status_bar("Program Source: NDI Loopback. Discovering NDI sources...")
        elif mode_text == "NDI Virtual Input (OpenCV)":
            self.ndi_source_combo.setEditable(True)
            self.ndi_source_combo.addItem("Enter NDI Source Name for OpenCV")
            self.ndi_source_combo.setEnabled(True)
            self.update_status_bar("Program Source: NDI Virtual Input (OpenCV). Type NDI source name.")
        elif mode_text == "vMix Virtual Camera":
            self.ndi_source_combo.setDisabled(True)
            self.update_status_bar("Program Source: vMix Virtual Camera.")
        else:
            self.update_status_bar(f"Unknown Program Source mode selected: {mode_text}")

    def _on_tally_mode_changed(self, mode_text):
        self.update_status_bar(f"Tally mode changed to: {mode_text}")
        # Stop any active tally thread when mode changes
        if self.vmix_tcp_tally_thread and self.vmix_tcp_tally_thread.isRunning():
            self.vmix_tcp_tally_thread.stop()
            # self.vmix_tcp_tally_thread.deleteLater() # Defer deletion
            self.vmix_tcp_tally_thread = None
        if self.vmix_http_tally_thread and self.vmix_http_tally_thread.isRunning():
            self.vmix_http_tally_thread.stop()
            # self.vmix_http_tally_thread.deleteLater()
            self.vmix_http_tally_thread = None

        if self.tally_button.isChecked(): # If tally was connected, uncheck button
            self.tally_button.setChecked(False)
            self.tally_button.setText("Connect Tally")

        if mode_text == "None":
            self.tally_button.setEnabled(False)
            self.update_status_bar("Tally is disabled.")
        else:
            self.tally_button.setEnabled(True)
            self.update_status_bar(f"Tally mode set to {mode_text}. Click 'Connect Tally'.")


    def _update_ndi_source_combobox(self, sources_list):
        current_text = self.ndi_source_combo.currentText()

        # Block signals to prevent currentTextChanged from firing during repopulation
        self.ndi_source_combo.blockSignals(True)
        self.ndi_source_combo.clear()

        if sources_list:
            self.ndi_source_combo.addItems(sources_list)
            # Try to restore previous selection OR loaded selection
            target_ndi_source = self.loaded_ndi_source_name if self.loaded_ndi_source_name else current_text
            if target_ndi_source and target_ndi_source in sources_list:
                self.ndi_source_combo.setCurrentText(target_ndi_source)
            elif self.ndi_source_combo.count() > 0:
                self.ndi_source_combo.setCurrentIndex(0)

            if self.loaded_ndi_source_name and self.ndi_source_combo.currentText() == self.loaded_ndi_source_name:
                self.loaded_ndi_source_name = None # Clear after successful application

            self.ndi_source_combo.setEnabled(True)
            self.update_status_bar(f"NDI sources updated: {len(sources_list)} found.")
        else:
            self.ndi_source_combo.setDisabled(True)
            self.update_status_bar("No NDI sources found for Loopback mode.")

        self.ndi_source_combo.blockSignals(False)


    def toggle_streaming(self):
        if self.toggle_stream_button.isChecked():
            selected_pgm_mode = self.pgm_source_combo.currentText()

            selected_ndi_source_name = ""
            if selected_pgm_mode == "NDI Loopback":
                selected_ndi_source_name = self.ndi_source_combo.currentText()
                if not selected_ndi_source_name:
                    self.update_status_bar(f"Error: NDI source name required for {selected_pgm_mode}.")
                    self.toggle_stream_button.setChecked(False)
                    return
            elif selected_pgm_mode == "NDI Virtual Input (OpenCV)":
                selected_ndi_source_name = self.ndi_cam_index_input.text()
                if not selected_ndi_source_name:
                    self.update_status_bar(f"Error: NDI/Cam Index or Name required for {selected_pgm_mode}.")
                    self.toggle_stream_button.setChecked(False)
                    return

            self.toggle_stream_button.setText("Stop Streaming")
            self._stop_all_capture_threads()

            current_srt_audio_sample_rate = self.current_pgm_audio_sample_rate
            current_srt_audio_channels = self.current_pgm_audio_channels

            if selected_pgm_mode == "NDI Loopback":
                if current_srt_audio_channels > 0 and current_srt_audio_sample_rate > 0:
                    self.srt_streamer_thread.set_audio_params(current_srt_audio_sample_rate, current_srt_audio_channels)
                else:
                    self.update_status_bar("NDI Loopback: Audio params not yet known. SRT will start without audio.")
                    self.srt_streamer_thread.set_audio_params(0, 0)

                self.ndi_loopback_thread = NDILoopbackCaptureThread(ndi_source_name=selected_ndi_source_name)
                self.ndi_loopback_thread.new_video_frame_signal.connect(self._handle_new_video_frame)
                self.ndi_loopback_thread.new_video_frame_signal.connect(self.srt_streamer_thread.push_frame)
                self.ndi_loopback_thread.new_audio_frame_signal.connect(self.handle_new_ndi_audio_frame) # Corrected name
                self.ndi_loopback_thread.status_signal.connect(self.update_status_bar)
                self.ndi_loopback_thread.error_signal.connect(self.update_status_bar)
                self.ndi_loopback_thread.ndi_info_signal.connect(self._handle_video_info_for_srt)

                self.ndi_loopback_thread.start()
                self.update_status_bar(f"Starting NDI Loopback stream from: {selected_ndi_source_name}")

            elif selected_pgm_mode == "NDI Virtual Input (OpenCV)":
                self.srt_streamer_thread.set_audio_params(0, 0)

                self.ndi_opencv_thread = GenericOpenCVCaptureThread(ndi_source_name=selected_ndi_source_name)
                self.ndi_opencv_thread.new_frame_signal.connect(self._handle_new_video_frame)
                self.ndi_opencv_thread.new_frame_signal.connect(self.srt_streamer_thread.push_frame)
                self.ndi_opencv_thread.status_signal.connect(self.update_status_bar)
                self.ndi_opencv_thread.error_signal.connect(self.update_status_bar)
                self.ndi_opencv_thread.ndi_info_signal.connect(self._handle_video_info_for_srt)

                self.ndi_opencv_thread.start()
                self.update_status_bar(f"Starting NDI Virtual Input (OpenCV) from: {selected_ndi_source_name}")

            elif selected_pgm_mode == "vMix Virtual Camera":
                self.srt_streamer_thread.set_audio_params(0, 0)

                self.vmix_virtual_cam_thread = VmixVirtualCameraCaptureThread()
                self.vmix_virtual_cam_thread.new_video_frame_signal.connect(self._handle_new_video_frame)
                self.vmix_virtual_cam_thread.new_video_frame_signal.connect(self.srt_streamer_thread.push_frame)
                self.vmix_virtual_cam_thread.video_info_signal.connect(self._handle_video_info_for_srt)
                self.vmix_virtual_cam_thread.status_signal.connect(self.update_status_bar)
                self.vmix_virtual_cam_thread.error_signal.connect(self.update_status_bar)

                self.vmix_virtual_cam_thread.start()
                self.update_status_bar("Starting vMix Virtual Camera stream.")

            if not self.srt_streamer_thread.isRunning():
                 self.srt_streamer_thread.start()
        else: # Stop streaming
            self.toggle_stream_button.setText("Start Streaming")
            self._stop_all_capture_threads()
            if self.srt_streamer_thread.isRunning():
                self.srt_streamer_thread.stop()
            self.update_status_bar("Streaming stopped.")

    def toggle_tally_connection(self):
        tally_mode = self.tally_mode_combo.currentText()
        if self.tally_button.isChecked(): # User wants to connect
            if tally_mode == "TCP Tally":
                # Stop HTTP Tally if running
                if self.vmix_http_tally_thread and self.vmix_http_tally_thread.isRunning():
                    self.vmix_http_tally_thread.stop()
                    self.vmix_http_tally_thread = None # Allow re-creation

                # Start TCP Tally (assuming self.vmix_tally_thread is the existing TCP one)
                if not self.vmix_tcp_tally_thread or not self.vmix_tcp_tally_thread.isRunning():
                    # self.vmix_tcp_tally_thread = VmixTallyThread() # Replace with actual TCP Tally class
                    # self.vmix_tcp_tally_thread.tally_signal.connect(self._handle_tally_data)
                    # self.vmix_tcp_tally_thread.status_signal.connect(self.update_status_bar)
                    # self.vmix_tcp_tally_thread.start()
                    self.update_status_bar("TCP Tally selected - (Placeholder: Start TCP Tally Thread here)")
                    self._fetch_and_cache_vmix_input_names(force_refresh=True) # Fetch names on connect
                else:
                    self.update_status_bar("TCP Tally already running.")
                self.tally_button.setText("Disconnect Tally")


            elif tally_mode == "HTTP Tally":
                if self.vmix_tcp_tally_thread and self.vmix_tcp_tally_thread.isRunning():
                    self.vmix_tcp_tally_thread.stop()
                    self.vmix_tcp_tally_thread = None

                if not self.vmix_http_tally_thread or not self.vmix_http_tally_thread.isRunning():
                    # Use loaded/default polling interval
                    poll_interval = getattr(self, 'loaded_http_tally_poll_ms', self.DEFAULT_HTTP_TALLY_POLL_MS)
                    self.vmix_http_tally_thread = VmixHttpTallyThread(
                        host=self.VMIX_HOST,
                        port=self.VMIX_HTTP_PORT,
                        polling_interval_ms=poll_interval
                    )
                    self.vmix_http_tally_thread.tally_data_signal.connect(self._handle_tally_data)
                    self.vmix_http_tally_thread.status_signal.connect(self.update_status_bar)
                    self.vmix_http_tally_thread.error_signal.connect(self.update_status_bar)
                    self._fetch_and_cache_vmix_input_names(force_refresh=True) # Fetch names on connect
                    self.vmix_http_tally_thread.start()
                    self.tally_button.setText("Disconnect Tally")
                else:
                    self.update_status_bar("HTTP Tally already running.")

            elif tally_mode == "None":
                self.tally_button.setChecked(False) # Cannot connect if mode is None
                self.update_status_bar("Tally mode is 'None'. Cannot connect.")


        else: # User wants to disconnect
            if self.vmix_tcp_tally_thread and self.vmix_tcp_tally_thread.isRunning():
                self.vmix_tcp_tally_thread.stop()
                # self.vmix_tcp_tally_thread.deleteLater()
                self.vmix_tcp_tally_thread = None
                self.update_status_bar("TCP Tally disconnected.")
            if self.vmix_http_tally_thread and self.vmix_http_tally_thread.isRunning():
                self.vmix_http_tally_thread.stop()
                # self.vmix_http_tally_thread.deleteLater()
                self.vmix_http_tally_thread = None
                self.update_status_bar("HTTP Tally disconnected.")
            self.tally_button.setText("Connect Tally")

    def _handle_tally_data(self, tally_info): # Generic handler
        # tally_info = {'pgm_inputs': [active_input], 'pvw_inputs': [preview_input]}
        # This method should update the PGM/PVW labels in the GUI
        # For now, just log it.
        # Attempt to fetch/refresh vMix input names.
        # The method itself has a timer, so frequent calls are fine.
        self._fetch_and_cache_vmix_input_names()

        pgm_input_numbers = tally_info.get('pgm_inputs', [])
        pvw_input_numbers = tally_info.get('pvw_inputs', [])

        pgm_display_parts = []
        for num in pgm_input_numbers:
            name = self.vmix_input_cache.get(num, f"Input {num}")
            pgm_display_parts.append(f"{name} ({num})")
        pgm_str = ", ".join(pgm_display_parts) if pgm_display_parts else "-"

        pvw_display_parts = []
        for num in pvw_input_numbers:
            name = self.vmix_input_cache.get(num, f"Input {num}")
            pvw_display_parts.append(f"{name} ({num})")
        pvw_str = ", ".join(pvw_display_parts) if pvw_display_parts else "-"

        self.pgm_tally_label.setText(f"PGM: {pgm_str}")
        self.pvw_tally_label.setText(f"PVW: {pvw_str}")

        # Original status bar update can be removed or kept for verbose logging if desired
        # self.update_status_bar(f"Tally Update: PGM: {pgm_str}, PVW: {pvw_str}")

        # TODO: The logic for sending tally data to a backend (e.g. via OSC) would go here,
        # using the raw pgm_input_numbers and pvw_input_numbers.
        # Example: self.osc_sender.send_tally(pgm_input_numbers, pvw_input_numbers)

    def _fetch_and_cache_vmix_input_names(self, force_refresh=False):
        current_time = time.time()
        if not force_refresh and (current_time - self.last_input_cache_refresh_time < self.INPUT_CACHE_REFRESH_INTERVAL):
            return False # Use existing cache, no refresh needed

        api_url = f"http://{self.VMIX_HOST}:{self.VMIX_HTTP_PORT}/api"
        self.update_status_bar(f"Fetching vMix input names from {api_url}...")

        try:
            response = requests.get(api_url, timeout=1.0) # Increased timeout slightly for full API call
            response.raise_for_status()

            xml_content = response.content
            root = ET.fromstring(xml_content)

            new_cache = {}
            for input_element in root.findall('.//inputs/input'):
                try:
                    # Correctly use 'number' attribute for matching tally information from <active> and <preview> tags
                    number_str = input_element.get('number')

                    # Prefer 'shortTitle' if available and not empty, else 'title', then element text
                    title = input_element.get('shortTitle')
                    if not title or title.strip() == "":
                        title = input_element.get('title')
                    if not title or title.strip() == "":
                        title = input_element.text.strip() if input_element.text else None

                    if number_str and title: # Ensure both number and a title are present
                        number = int(number_str)
                        new_cache[number] = title
                    # else:
                        # self.update_status_bar(f"Skipping input: num='{number_str}', title='{title}'")
                except ValueError:
                    self.update_status_bar(f"Error: Could not parse input number: '{input_element.get('number')}' as integer.")
                except Exception as e_parse: # Catch other potential errors during parsing of one input
                    self.update_status_bar(f"Error parsing a vMix input element: {e_parse}")

            if not new_cache and len(list(root.findall('.//inputs/input'))) > 0 : # Only error if inputs were present but none were parsable
                 self.update_status_bar("Error: Inputs found in vMix API response, but failed to parse names/numbers for any.")
                 # Do not wipe existing cache if the new fetch failed badly, unless no inputs are reported at all
                 # If vMix reports zero inputs (e.g. fresh preset), the cache should be cleared.
                 if not list(root.findall('.//inputs/input')): # No inputs in XML
                    self.vmix_input_cache = {}
                    self.last_input_cache_refresh_time = current_time # Reflect that an update (to empty) happened
                    self.update_status_bar("vMix reports no inputs. Cache cleared.")
                 return False # Indicate refresh effectively failed or resulted in no data

            self.vmix_input_cache = new_cache # Replace cache with new data (or empty if no inputs)
            self.last_input_cache_refresh_time = current_time
            if new_cache :
                self.update_status_bar(f"vMix input names cache refreshed. Found {len(self.vmix_input_cache)} inputs.")
            elif not list(root.findall('.//inputs/input')): # No inputs in XML, cache is now empty
                 pass # Already emitted "vMix reports no inputs"
            else: # No inputs parsed, but XML did contain input elements
                self.update_status_bar("vMix input names cache updated, but no valid inputs/names were parsed.")

            return True # Refresh attempt was made

        except requests.exceptions.RequestException as e:
            self.update_status_bar(f"Error: Failed to fetch vMix input names: {e}")
        except ET.ParseError as e:
            self.update_status_bar(f"Error: Failed to parse vMix API XML for input names: {e}")
        except Exception as e: # Catch any other unexpected errors during the overall fetch process
            self.update_status_bar(f"Error: Unexpected error fetching/processing vMix input names: {e}")

        return False # Refresh failed

    def _stop_all_capture_threads(self): # Renamed from _stop_all_ndi_threads
        if self.ndi_loopback_thread and self.ndi_loopback_thread.isRunning():
            self.ndi_loopback_thread.stop()
            self.ndi_loopback_thread.deleteLater()
            self.ndi_loopback_thread = None
        if self.ndi_opencv_thread and self.ndi_opencv_thread.isRunning(): # Generic OpenCV thread
            self.ndi_opencv_thread.stop()
            self.ndi_opencv_thread.deleteLater()
            self.ndi_opencv_thread = None
        if self.vmix_virtual_cam_thread and self.vmix_virtual_cam_thread.isRunning():
            self.vmix_virtual_cam_thread.stop()
            self.vmix_virtual_cam_thread.deleteLater()
            self.vmix_virtual_cam_thread = None
        self.update_status_bar("All capture threads stopped.")


    def _handle_new_video_frame(self, frame): # Renamed from handle_new_ndi_frame
        # This method receives frames from any active video capture thread
        try:
            if isinstance(frame, np.ndarray):
                # Example: Display on self.video_preview_label (ensure it's a QPixmap)
                # This is a simplified display, real conversion is more involved.
                # frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # h, w, ch = frame_rgb.shape
                # bytes_per_line = ch * w
                # q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                # pixmap = QPixmap.fromImage(q_img)
                # self.video_preview_label.setPixmap(pixmap.scaled(self.video_preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                pass # Placeholder for actual frame display
        except Exception as e:
            self.update_status_bar(f"Error displaying frame: {e}")


    def handle_new_ndi_audio_frame(self, audio_data, sample_rate, channels, timestamp_ns):
        # This is called when the NDI loopback thread emits an audio frame.
        # Other sources like vMix Virtual Cam or generic OpenCV might not provide audio this way.
        self.update_status_bar(f"Audio Frame (NDI): {audio_data.shape[0]} samples, {sample_rate}Hz, {channels}ch, TS: {timestamp_ns}")

        # Update current audio parameters if they change or are set for the first time
        # This is primarily relevant for NDI Loopback audio.
        # self.update_status_bar(f"Audio Frame (NDI): {audio_data.shape[0]} samples, {sample_rate}Hz, {channels}ch, TS: {timestamp_ns}") # Too verbose

        source_mode = self.pgm_source_combo.currentText()

        if source_mode == "NDI Loopback": # Only process if NDI Loopback is the active PGM source
            params_changed = False
            if self.current_pgm_audio_sample_rate != sample_rate or self.current_pgm_audio_channels != channels:
                self.current_pgm_audio_sample_rate = sample_rate
                self.current_pgm_audio_channels = channels
                params_changed = True
                self.update_status_bar(f"NDI Loopback Audio Params Updated: {sample_rate}Hz, {channels}ch")

            srt_is_running = self.srt_streamer_thread.isRunning()

            if params_changed and srt_is_running:
                # If SRT is running AND its current audio config doesn't match the new NDI audio params.
                if (self.srt_streamer_thread.audio_sample_rate != sample_rate or \
                    self.srt_streamer_thread.audio_channels != channels):
                    # This typically means FFmpeg needs a restart to pick up new format.
                    self.update_status_bar("Info: NDI audio parameters changed mid-stream. SRT FFmpeg may need restart if format differs.")

            # Push audio data to SRT streamer only if SRT is running
            if srt_is_running:
                if self.srt_streamer_thread.audio_channels > 0: # If SRT was started with audio
                    self.srt_streamer_thread.push_audio_frame(audio_data, sample_rate, channels, timestamp_ns)
                elif self.current_pgm_audio_channels > 0 : # SRT started with no audio, but PGM now has audio
                     self.update_status_bar("Info: Audio detected from NDI, but SRT started without audio. Restart stream to include audio.")
            # If SRT not running, current_pgm_audio_... will be used when it starts.

    def _handle_video_info_for_srt(self, video_info_str):
        # Parses "1920x1080 @ 30.0 FPS" or "Res: 1920x1080, FPS: 30.0"
        self.update_status_bar(f"Video Info for SRT: {video_info_str}")
        try:
            w, h, fps_val = 0, 0, 0.0

            if "@" in video_info_str and "FPS" in video_info_str.upper(): # Format "1920x1080 @ 29.97 FPS"
                res_part, fps_part = video_info_str.split('@')
                w_str, h_str = res_part.strip().split('x')
                w = int(w_str)
                h = int(h_str)
                fps_val_str = fps_part.upper().replace('FPS','').strip()
                fps_val = float(fps_val_str)
            elif "Res:" in video_info_str and "FPS:" in video_info_str: # Format "Res: WxH, FPS: F"
                parts = video_info_str.split(',') #ndi_info_str was a typo here, should be video_info_str
                res_str_part = parts[0].split(':')[1].strip()
                fps_str_part = parts[1].split(':')[1].strip()
                w, h = map(int, res_str_part.split('x'))
                fps_val = float(fps_str_part)
            else:
                self.update_status_bar(f"Could not parse video info string for SRT: '{video_info_str}'")
                return

            if w <= 0 or h <= 0 or fps_val <= 0.0:
                self.update_status_bar(f"Parsed video info resulted in non-positive values: W={w}, H={h}, FPS={fps_val}. Not setting for SRT.")
                return

            self.srt_streamer_thread.set_video_params(w, h, fps_val)
            # Audio parameters are handled by handle_new_ndi_audio_frame

        except Exception as e:
            self.update_status_bar(f"Error parsing video info string '{video_info_str}' for SRT: {e}")


    def update_status_bar(self, message):
        self.status_bar.showMessage(message)
        print(f"STATUS: {message}") # Also print to console for visibility if GUI is problematic

    def closeEvent(self, event):
        self.update_status_bar("Closing application...")
        self._save_config() # Save config on close
        self._stop_all_capture_threads()
        self._stop_ndi_discovery()

        # Stop Tally Threads
        if self.vmix_tcp_tally_thread and self.vmix_tcp_tally_thread.isRunning():
            self.vmix_tcp_tally_thread.stop()
        if self.vmix_http_tally_thread and self.vmix_http_tally_thread.isRunning():
            self.vmix_http_tally_thread.stop()

        if self.srt_streamer_thread and self.srt_streamer_thread.isRunning():
            self.srt_streamer_thread.stop()
            self.srt_streamer_thread.deleteLater() # QThreads should be managed for deletion

        # Properly delete other QThread instances if they were assigned to self
        # This ensures their event loops are cleaned up if they were moved to a thread.
        # For threads that are stopped and then re-created, deleteLater is good.
        # For the discovery thread specifically:
        if self.ndi_loopback_discover_thread: self.ndi_loopback_discover_thread.deleteLater()
        if self.vmix_tcp_tally_thread: self.vmix_tcp_tally_thread.deleteLater()
        if self.vmix_http_tally_thread: self.vmix_http_tally_thread.deleteLater()
        # Capture threads (ndi_loopback_thread, ndi_opencv_thread, vmix_virtual_cam_thread)
        # are typically re-created each time, so deleteLater in _stop_all_capture_threads is fine.

        super().closeEvent(event)

    # --- Configuration Management ---
    def _get_config_path(self):
        app_name = "PDApp" # Define an application name for the config folder
        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if "/" not in config_dir : # if AppConfigLocation is empty or not well defined (e.g. on some CI)
             config_dir = os.path.join(os.path.expanduser("~"), ".config", app_name)

        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception as e:
                self.update_status_bar(f"Error creating config directory {config_dir}: {e}") # Changed to update_status_bar
                # Fallback to current directory if user's config dir is not writable/creatable
                return os.path.join(".", "pd_app_config.json")
        return os.path.join(config_dir, "pd_app_config.json")

    def _save_config(self):
        config_path = self._get_config_path()
        self.update_status_bar(f"Saving configuration to {config_path}...") # Changed to update_status_bar

        # Gather NDI Loopback source name carefully
        ndi_loopback_source = ""
        if self.pgm_source_combo.currentText() == "NDI Loopback":
            ndi_loopback_source = self.ndi_source_combo.currentText()
        elif self.loaded_ndi_source_name: # If it was loaded but NDI Loopback not active, save it back
            ndi_loopback_source = self.loaded_ndi_source_name

        config_data = {
            'pgm_source_mode': self.pgm_source_combo.currentText(),
            'ndi_loopback_source_name': ndi_loopback_source,
            'ndi_virtual_input_source': self.ndi_cam_index_input.text(),
            'tally_mode': self.tally_mode_combo.currentText(),
            'srt_url': self.srt_url_input.text(),
            'backend_ws_url': self.backend_url_input.text(),
            'vmix_host': self.VMIX_HOST, # Assuming these are fairly static for now
            'vmix_tcp_port': self.VMIX_TCP_PORT,
            'vmix_http_port': self.VMIX_HTTP_PORT,
            'http_tally_poll_interval_ms': self.vmix_http_tally_thread.polling_interval_s * 1000 if self.vmix_http_tally_thread else self.DEFAULT_HTTP_TALLY_POLL_MS,
            'input_cache_refresh_interval_s': self.INPUT_CACHE_REFRESH_INTERVAL,
        }
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.update_status_bar("Configuration saved.") # Changed to update_status_bar
        except IOError as e:
            self.update_status_bar(f"Error saving configuration: {e}") # Changed to update_status_bar
        except Exception as e: # Catch any other unexpected errors
            self.update_status_bar(f"Unexpected error saving configuration: {e}") # Changed to update_status_bar


    def _load_config(self):
        config_path = self._get_config_path()
        self.update_status_bar(f"Loading configuration from {config_path}...") # Changed to update_status_bar
        if not os.path.exists(config_path):
            self.update_status_bar("Configuration file not found. Using default settings.") # Changed to update_status_bar
            # Apply defaults to UI elements that might not have them set by constructor
            self.pgm_source_combo.setCurrentText(self.DEFAULT_PGM_MODE)
            self.tally_mode_combo.setCurrentText(self.DEFAULT_TALLY_MODE)
            self.srt_url_input.setText(self.DEFAULT_SRT_URL)
            self.backend_url_input.setText(self.DEFAULT_BACKEND_WS_URL)
            self.ndi_cam_index_input.setText(self.DEFAULT_NDI_OPENCV_SOURCE)
            # VMIX_HOST, VMIX_HTTP_PORT, INPUT_CACHE_REFRESH_INTERVAL are already set from defaults
            return

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            self.pgm_source_combo.setCurrentText(config_data.get('pgm_source_mode', self.DEFAULT_PGM_MODE))

            # Store NDI loopback source name, to be applied when combo is populated
            self.loaded_ndi_source_name = config_data.get('ndi_loopback_source_name')
            # If NDI Loopback is the loaded mode, ndi_source_combo will be populated by _start_ndi_discovery
            # and then _update_ndi_source_combobox will try to set this name.

            self.ndi_cam_index_input.setText(config_data.get('ndi_virtual_input_source', self.DEFAULT_NDI_OPENCV_SOURCE))
            self.tally_mode_combo.setCurrentText(config_data.get('tally_mode', self.DEFAULT_TALLY_MODE))
            self.srt_url_input.setText(config_data.get('srt_url', self.DEFAULT_SRT_URL))
            self.backend_url_input.setText(config_data.get('backend_ws_url', self.DEFAULT_BACKEND_WS_URL))

            # Load constants/variables if they are meant to be configurable
            self.VMIX_HOST = config_data.get('vmix_host', self.VMIX_HOST)
            self.VMIX_TCP_PORT = config_data.get('vmix_tcp_port', self.VMIX_TCP_PORT)
            self.VMIX_HTTP_PORT = config_data.get('vmix_http_port', self.VMIX_HTTP_PORT)
            self.INPUT_CACHE_REFRESH_INTERVAL = config_data.get('input_cache_refresh_interval_s', self.DEFAULT_CACHE_REFRESH_S)

            # Note: http_tally_poll_interval_ms would be used when VmixHttpTallyThread is created.
            # We can store it in a member variable to be used by toggle_tally_connection.
            self.loaded_http_tally_poll_ms = config_data.get('http_tally_poll_interval_ms', self.DEFAULT_HTTP_TALLY_POLL_MS)

            self.update_status_bar("Configuration loaded.") # Changed to update_status_bar

        except IOError as e:
            self.update_status_bar(f"Error loading configuration file: {e}") # Changed to update_status_bar
        except json.JSONDecodeError as e:
            self.update_status_bar(f"Error decoding configuration file (JSON invalid): {e}") # Changed to update_status_bar
        except Exception as e: # Catch any other unexpected errors
            self.update_status_bar(f"Unexpected error loading configuration: {e}") # Changed to update_status_bar

    # --- End Configuration Management ---


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # It's good practice to ensure NDI is initialized for the app lifetime if using ndi-python globally
    # However, NDILoopbackCaptureThread handles its own init/destroy cycles.
    # If other parts of the app used NDI directly, global init/destroy might be needed.
    # import ndi
    # if not ndi.initialize():
    #     print("Application level NDI.initialize failed. Exiting.")
    #     sys.exit(1)

    main_win = MainWindow()
    main_win.show()
    exit_code = app.exec_()

    # ndi.destroy() # Clean up NDI globally if initialized globally
    sys.exit(exit_code)
