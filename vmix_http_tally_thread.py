import time
import requests
import xml.etree.ElementTree as ET
from PyQt5.QtCore import QThread, pyqtSignal

class VmixHttpTallyThread(QThread):
    tally_data_signal = pyqtSignal(dict)  # Emits {'pgm_inputs': [active_input_num], 'pvw_inputs': [preview_input_num]}
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str) # For general, often transient, errors
    critical_error_signal = pyqtSignal(str, str) # For more severe, persistent, or setup errors (title, message)

    def __init__(self, host='127.0.0.1', port=8088, polling_interval_ms=250, parent=None):
        super().__init__(parent)
        self.running = False
        self.host = host
        self.port = port
        self.polling_interval_s = polling_interval_ms / 1000.0
        self.api_url = f"http://{self.host}:{self.port}/api"
        self.request_timeout_s = max(0.1, self.polling_interval_s * 0.8) # Timeout should be less than interval

    def run(self):
        self.running = True
        self.status_signal.emit(f"vMix HTTP Tally thread started for {self.api_url}, polling every {self.polling_interval_s*1000:.0f}ms.")

        while self.running:
            start_time = time.time()

            try:
                response = requests.get(self.api_url, timeout=self.request_timeout_s)
                response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)

                xml_content = response.content
                root = ET.fromstring(xml_content)

                active_text = root.findtext('active')
                preview_text = root.findtext('preview')

                active_input = None
                preview_input = None

                if active_text is not None and active_text.isdigit() and int(active_text) > 0: # vMix input 0 is not a real input
                    active_input = int(active_text)

                if preview_text is not None and preview_text.isdigit() and int(preview_text) > 0: # vMix input 0 is not a real input
                    preview_input = int(preview_text)

                # self.status_signal.emit(f"HTTP Tally: PGM={active_input}, PVW={preview_input}") # Can be noisy
                tally_data = {
                    'pgm_inputs': [active_input] if active_input is not None else [],
                    'pvw_inputs': [preview_input] if preview_input is not None else []
                }
                self.tally_data_signal.emit(tally_data)

            except requests.exceptions.Timeout:
                self.error_signal.emit(f"HTTP Tally: Request timed out against {self.api_url}")
            except requests.exceptions.ConnectionError:
                self.error_signal.emit(f"HTTP Tally: Connection error for {self.api_url}. Is vMix running and Web API enabled?")
                # Sleep longer if connection error to avoid flooding logs/network
                if self.running: QThread.msleep(int(self.polling_interval_s * 1000 * 2))
            except requests.exceptions.HTTPError as e:
                self.error_signal.emit(f"HTTP Tally: HTTP error {e.response.status_code} from {self.api_url}")
            except ET.ParseError as e:
                self.error_signal.emit(f"HTTP Tally: Failed to parse XML response from vMix. Error: {e}")
            except ValueError as e:
                self.error_signal.emit(f"HTTP Tally: Error converting PGM/PVW input to number. XML content might be unexpected. Error: {e}")
            except Exception as e:
                self.error_signal.emit(f"HTTP Tally: An unexpected error occurred: {e}")

            elapsed_time = time.time() - start_time
            sleep_duration = self.polling_interval_s - elapsed_time
            if sleep_duration > 0 and self.running:
                QThread.msleep(int(sleep_duration * 1000))
            elif self.running: # If loop took longer than interval, sleep minimally to yield
                QThread.msleep(10)

        self.status_signal.emit("vMix HTTP Tally thread stopped.")

    def stop(self):
        self.status_signal.emit("Attempting to stop vMix HTTP Tally thread...")
        self.running = False
        if self.isRunning():
            self.wait(int(self.polling_interval_s * 1000 * 2) + 100) # Wait a bit longer than polling interval
        self.status_signal.emit("vMix HTTP Tally thread definitively stopped.")

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QTimer # Added QTimer for the test
    import sys

    app = QApplication(sys.argv)

    def handle_tally(data):
        print(f"Tally Data: PGM={data['pgm_inputs']}, PVW={data['pvw_inputs']}")

    def handle_status(status):
        print(f"Status: {status}")

    def handle_error(error):
        print(f"Error: {error}")

    # Create and start the thread
    # Make sure vMix is running with Web API enabled on default port 8088
    # Or change host/port accordingly.
    http_tally_thread = VmixHttpTallyThread(polling_interval_ms=500)
    http_tally_thread.tally_data_signal.connect(handle_tally)
    http_tally_thread.status_signal.connect(handle_status)
    http_tally_thread.error_signal.connect(handle_error)

    http_tally_thread.start()

    # Let it run for some time then stop
    QTimer.singleShot(10000, http_tally_thread.stop) # Stop after 10 seconds
    QTimer.singleShot(11000, app.quit) # Quit app

    sys.exit(app.exec_())
