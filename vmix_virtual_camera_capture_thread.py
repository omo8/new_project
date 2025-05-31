import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

# Attempt to import pygrabber, with a fallback for environments where it might not be available
try:
    from pygrabber.dshow_graph import FilterGraph
    PYGRABBER_AVAILABLE = True
except ImportError:
    PYGRABBER_AVAILABLE = False
    FilterGraph = None # Placeholder

class VmixVirtualCameraCaptureThread(QThread):
    new_video_frame_signal = pyqtSignal(object)  # Emits NumPy array (BGR format)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str) # For general errors
    critical_error_signal = pyqtSignal(str, str) # title, message for QMessageBox
    video_info_signal = pyqtSignal(str)  # Emits "Res: WxH, FPS: F"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.cap = None
        self.camera_name_to_find = "vmix video" # Default, can be more specific if needed e.g. "vMix Video"

    def _find_vmix_camera_index(self):
        self.status_signal.emit("Searching for vMix Virtual Camera...")
        if not PYGRABBER_AVAILABLE:
            err_msg = "pygrabber library is not installed. Cannot search for vMix Virtual Camera by name. Please install pygrabber."
            self.error_signal.emit(err_msg)
            self.critical_error_signal.emit("Dependency Missing", err_msg)
            return None

        try:
            graph = FilterGraph()
            devices = graph.get_input_devices() # List of camera names (strings)
            self.status_signal.emit(f"Available DirectShow input devices: {devices}")

            for i, device_name in enumerate(devices):
                if self.camera_name_to_find in device_name.lower():
                    self.status_signal.emit(f"Found '{self.camera_name_to_find}' at index {i} (name: {device_name})")
                    return i

            self.error_signal.emit(f"'{self.camera_name_to_find}' not found in available DirectShow devices. Ensure vMix External Output is active.")
            # This might not be critical enough for a QMessageBox every time, depends on UX.
            # For now, an error_signal is sufficient. If it's critical, a critical_error_signal can be added.
            return None
        except Exception as e:
            err_msg = f"Error using pygrabber to find cameras: {e}"
            self.error_signal.emit(err_msg)
            self.critical_error_signal.emit("Camera Discovery Error", err_msg)
            return None

    def run(self):
        self.running = True
        self.status_signal.emit("vMix Virtual Camera thread started.")

        try:
            camera_index = self._find_vmix_camera_index()

            if camera_index is None:
                # Error messages are already emitted by _find_vmix_camera_index.
                # If it returned None, it means either pygrabber is missing (critical signal sent)
                # or camera not found (error signal sent).
                return

            self.status_signal.emit(f"Attempting to open vMix Virtual Camera at index {camera_index} using CAP_DSHOW.")
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

            if not self.cap or not self.cap.isOpened():
                err_msg = f"Failed to open vMix Virtual Camera at index {camera_index}. It might be in use or drivers are missing."
                self.error_signal.emit(err_msg)
                self.critical_error_signal.emit("Camera Error", err_msg)
                return

            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps == 0:
                fps = 30
                self.status_signal.emit("Camera FPS reported as 0, assuming 30 FPS.")

            self.status_signal.emit(f"vMix Virtual Camera opened: {frame_width}x{frame_height} @ {fps:.2f} FPS (reported)")
            self.video_info_signal.emit(f"Res: {frame_width}x{frame_height}, FPS: {fps:.2f}")

            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.new_video_frame_signal.emit(frame)
                else:
                    self.error_signal.emit("Failed to read frame from vMix Virtual Camera. End of stream or error.")
                    break # Exit loop on read error

                # Minimal sleep to allow thread to be responsive to stop() if camera provides frames very fast.
                # Actual frame rate is dictated by the camera.
                QThread.msleep(1)

        except Exception as e:
            self.error_signal.emit(f"Unhandled exception in vMix Virtual Camera thread: {e}")
        finally:
            self.running = False # Ensure loop condition is false on exit
            if self.cap:
                self.cap.release()
                self.status_signal.emit("vMix Virtual Camera released.")
            self.status_signal.emit("vMix Virtual Camera thread stopped.")

    def stop(self):
        self.status_signal.emit("Attempting to stop vMix Virtual Camera thread...")
        self.running = False
        if self.isRunning():
            self.wait(5000) # Wait for thread to finish
        self.status_signal.emit("vMix Virtual Camera thread definitively stopped.")

if __name__ == '__main__':
    # Basic test for VmixVirtualCameraCaptureThread
    app = QApplication(sys.argv) # Required for Qt signals

    def handle_frame_test(frame):
        print(f"Test: Received video frame - shape: {frame.shape}")
        # cv2.imshow("vMix Test", frame) # Requires GUI context for cv2.imshow
        # cv2.waitKey(1)
        pass

    def handle_status_test(status):
        print(f"Test STATUS: {status}")

    def handle_error_test(error):
        print(f"Test ERROR: {error}")

    def handle_info_test(info):
        print(f"Test INFO: {info}")

    # Create and run the thread
    vmix_thread = VmixVirtualCameraCaptureThread()
    vmix_thread.new_video_frame_signal.connect(handle_frame_test)
    vmix_thread.status_signal.connect(handle_status_test)
    vmix_thread.error_signal.connect(handle_error_test)
    vmix_thread.video_info_signal.connect(handle_info_test)

    print("Test: Starting vMix Virtual Camera thread...")
    vmix_thread.start()

    # Let it run for a few seconds
    QTimer.singleShot(10000, lambda: vmix_thread.stop()) # Stop after 10 seconds
    QTimer.singleShot(12000, app.quit) # Quit app after stopping thread

    sys.exit(app.exec_())
    print("Test finished.")
