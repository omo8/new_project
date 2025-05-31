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
    error_signal = pyqtSignal(str)
    video_info_signal = pyqtSignal(str)  # Emits "Res: WxH, FPS: F"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.cap = None
        self.camera_name_to_find = "vmix video" # Default, can be more specific if needed e.g. "vMix Video"

    def _find_vmix_camera_index(self):
        self.status_signal.emit("Searching for vMix Virtual Camera...")
        if not PYGRABBER_AVAILABLE:
            self.error_signal.emit("pygrabber library is not available. Cannot search for vMix Virtual Camera by name.")
            # Fallback: Try common camera indices like 0, 1, 2 if pygrabber is not there.
            # This is a very rough fallback and might not find vMix.
            # For robust operation, pygrabber should be installed.
            # Here, we could try a few indices and check their names if OpenCV provides them (often not)
            # Or simply return a common index and hope for the best, or None.
            self.status_signal.emit("Attempting fallback to common camera indices (0 or 1) due to missing pygrabber.")
            # Let's try to open index 0 and 1 and see if they work, but we can't verify the name.
            # This part is highly unreliable without pygrabber.
            # For now, let's assume if pygrabber is not there, we can't reliably find it.
            # A more robust fallback would be to allow user to specify index or iterate common indices.
            # Returning None is safer if we can't find it by name.
            self.error_signal.emit("Consider installing pygrabber for reliable vMix camera detection.")
            # As a simple simulation of pygrabber not finding it:
            # return None
            # Or, to allow testing of the rest of the pipeline, assume index 0 or 1 if vMix is likely the only DSHOW cam
            # For this exercise, let's try to return a common index to allow flow, but with error.
            # This is a placeholder for when pygrabber is not installed.
            # It should ideally be handled by the user or a configuration setting.
            # Let's return 0 for testing purposes if pygrabber is not found.
            # self.error_signal.emit("Simulating vMix camera at index 0 (pygrabber unavailable).")
            # return 0
            # A better simulation for "not found if pygrabber is missing":
            return None


        try:
            graph = FilterGraph()
            devices = graph.get_input_devices() # List of camera names (strings)
            self.status_signal.emit(f"Available DirectShow input devices: {devices}")

            for i, device_name in enumerate(devices):
                if self.camera_name_to_find in device_name.lower():
                    self.status_signal.emit(f"Found '{self.camera_name_to_find}' at index {i} (name: {device_name})")
                    return i

            self.error_signal.emit(f"'{self.camera_name_to_find}' not found in available DirectShow devices.")
            return None
        except Exception as e:
            self.error_signal.emit(f"Error using pygrabber to find cameras: {e}")
            return None

    def run(self):
        self.running = True
        self.status_signal.emit("vMix Virtual Camera thread started.")

        camera_index = self._find_vmix_camera_index()

        if camera_index is None:
            self.error_signal.emit("vMix Virtual Camera index not found. Stopping thread.")
            self.running = False
            return

        self.status_signal.emit(f"Attempting to open vMix Virtual Camera at index {camera_index} using CAP_DSHOW.")
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            self.error_signal.emit(f"Failed to open vMix Virtual Camera at index {camera_index}.")
            self.running = False
            return

        # Try to set a common resolution, vMix virtual cam might have a fixed one
        # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        # self.cap.set(cv2.CAP_PROP_FPS, 30)


        frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: # FPS might not be reported correctly by all DSHOW cameras
            fps = 30 # Assume 30 FPS if not reported or if 0
            self.status_signal.emit("Camera FPS reported as 0, assuming 30 FPS.")

        self.status_signal.emit(f"vMix Virtual Camera opened: {frame_width}x{frame_height} @ {fps:.2f} FPS (reported)")
        self.video_info_signal.emit(f"Res: {frame_width}x{frame_height}, FPS: {fps:.2f}")

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.new_video_frame_signal.emit(frame)
            else:
                self.error_signal.emit("Failed to read frame from vMix Virtual Camera. End of stream or error.")
                self.running = False # Stop if we can't read frames
                break

            # Control frame rate if necessary, though VideoCapture should handle it.
            # For DSHOW, it typically respects the camera's output rate.
            # self.msleep(int(1000 / fps) if fps > 0 else 33)

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
