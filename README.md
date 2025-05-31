# PD Video Streaming Application

## 1. Overview

PD Video Streaming Application is a Python-based tool designed for capturing video and audio from various sources, processing tally information from vMix, and streaming the output via SRT to a media server like MediaMTX. It provides a graphical user interface (GUI) built with PyQt5 for managing sources, configurations, and monitoring the streaming process.

The application supports multiple Program (PGM) input sources, including:
-   **NDI Loopback:** Captures NDI audio and video sources available on the network using the `ndi-python` library, providing high-quality, low-latency input.
-   **vMix Virtual Camera:** Captures video output from vMix's "External" feature, which exposes the vMix main output as a virtual webcam (Windows DirectShow source).
-   **NDI Virtual Input (Generic OpenCV):** A placeholder for capturing NDI sources that present as standard camera devices or other OpenCV-compatible sources. This is more generic and might require specific OpenCV configurations (e.g., with FFMPEG backend) for NDI names.

Tally information from vMix is supported through:
-   **HTTP API Polling:** Fetches PGM/PVW status by polling the vMix HTTP API. It also caches and displays input names for better readability.
-   **TCP Tally (Placeholder):** UI elements exist for a TCP-based tally connection, but the underlying implementation is a placeholder.

The application streams the final output (video, and audio from NDI Loopback) to a specified SRT URL, typically for ingestion by an SRT server like MediaMTX or vMix.

## 2. Features

-   **Multiple PGM Source Options:**
    -   NDI Loopback (Video + Audio) via `ndi-python`.
    -   vMix Virtual Camera (Video-only) via OpenCV and `pygrabber`.
    -   Generic OpenCV source (Video-only, e.g., webcam, NDI name if OpenCV supports it).
-   **Dynamic NDI Source Discovery:** Automatically discovers and lists available NDI sources for NDI Loopback mode.
-   **vMix Tally Integration:**
    -   Displays Program (PGM) and Preview (PVW) tally status from vMix.
    -   Supports Tally via vMix HTTP API polling.
    -   Fetches and displays vMix input names alongside numbers for PGM/PVW.
    -   Placeholder for TCP-based Tally connection.
-   **SRT Streaming:**
    -   Streams captured video (and audio from NDI Loopback) to a specified SRT URL using FFmpeg.
    -   Manages FFmpeg process lifecycle.
-   **Configuration Management:**
    -   Saves and loads application settings (selected sources, URLs, vMix connection details, etc.) to a `config.json` file in the user's application configuration directory.
-   **GUI:**
    -   User-friendly interface built with PyQt5.
    -   Controls for selecting PGM source, NDI source, Tally mode.
    -   Input fields for SRT URL, Backend WebSocket URL.
    -   Displays PGM/PVW tally information with input names.
    -   Log display area for application status, errors, and FFmpeg output.
    -   Status bar for real-time feedback.
-   **FFmpeg Log Display:** Captures and shows `stderr` output from FFmpeg for monitoring and troubleshooting.
-   **Cross-Platform Considerations:**
    -   Uses `QStandardPaths` for configuration file location.
    -   Notes platform differences for camera access (e.g., `cv2.CAP_DSHOW` on Windows) and named pipes (POSIX `mkfifo` vs. Windows temp file fallback for FFmpeg audio).

## 3. Dependencies

The application relies on several Python libraries. Ensure these are installed in your Python environment. A `requirements.txt` file would typically list these:

-   **PyQt5:** For the graphical user interface.
-   **NumPy:** For numerical operations, especially with video frames.
-   **OpenCV (cv2):** For video capture from vMix Virtual Camera and Generic OpenCV sources.
    -   `opencv-python` or `opencv-contrib-python`.
-   **ndi-python (`ndi`):** For NDI Loopback capture. This requires the NDI SDK to be installed on the system.
-   **requests:** For making HTTP API calls to vMix (Tally and input name fetching).
-   **pygrabber:** (Windows-only) For discovering vMix Virtual Camera by name among DirectShow devices. This is optional but highly recommended for reliable vMix Virtual Camera detection on Windows. If not present, the application attempts a less reliable fallback.

**External Software:**
-   **FFmpeg:** Required for SRT streaming. It must be installed and accessible in the system's PATH.
-   **NDI SDK:** The NDI runtime/SDK must be installed on the system for NDI features to work.
-   **vMix:** (Optional, if using vMix-specific features) For providing NDI sources, virtual camera output, and Tally information.

## 4. Setup

1.  **Install Python:** Ensure Python 3.x is installed.
2.  **Install NDI SDK:** Download and install the NDI SDK (Runtime) from [NDI.tv](https://ndi.tv/sdk/).
3.  **Install FFmpeg:** Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and ensure it's added to your system's PATH environment variable.
4.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
5.  **Install Python Dependencies:**
    ```bash
    pip install PyQt5 numpy opencv-python ndi-python requests pygrabber
    ```
    (Note: `pygrabber` is primarily for Windows. Installation on other OSes might be skipped if not needed, but the code includes it.)
6.  **Clone or Download Application Files:** Place all application Python files (`pd_app.py`, `ndi_loopback_capture_thread.py`, etc.) in a single directory.
7.  **vMix Configuration (If using vMix features):**
    *   **NDI Output:** In vMix, enable NDI output for the sources you want to use (e.g., Main Mix, specific inputs).
    *   **Virtual Camera:** Activate the "External" output in vMix settings to enable the vMix Virtual Camera.
    *   **HTTP API:** Ensure the vMix Web Controller (HTTP API) is enabled in vMix Settings > Web Controller. Note the host (usually `127.0.0.1`) and port (default `8088`).
    *   **TCP Tally:** Ensure TCP Tally is enabled in vMix Settings > Tally Lights if you plan to use the (currently placeholder) TCP Tally feature.

## 5. Usage

1.  **Run the Application:**
    ```bash
    python pd_app.py
    ```
2.  **Configure Program Source:**
    *   Select the desired video source from the "Program Source" dropdown:
        *   **NDI Loopback:** The "NDI Source" dropdown will populate with discovered NDI sources. Select one. Audio will be captured from this source.
        *   **NDI Virtual Input (OpenCV):** Enter the NDI source name or camera index in the "NDI/Cam Index/Name (OpenCV)" field. This mode is video-only for SRT streaming.
        *   **vMix Virtual Camera:** The application will attempt to auto-detect the vMix Virtual Camera. This mode is video-only for SRT streaming.
3.  **Configure Tally (Optional):**
    *   Select the "Tally Mode":
        *   **HTTP Tally:** Polls vMix API. Ensure vMix Host/Port are correct (currently defaults, can be changed in config file).
        *   **TCP Tally:** Placeholder.
        *   **None:** Disables Tally.
    *   Click "Connect Tally" to start receiving Tally data. PGM/PVW labels will update with input names and numbers.
4.  **Configure Streaming & Backend:**
    *   **SRT URL:** Enter the destination SRT URL (e.g., `srt://your_media_server_ip:1234`).
    *   **Backend WS URL:** Enter the WebSocket URL for the backend (currently a placeholder feature).
5.  **Start Streaming:**
    *   Click "Start Streaming". The button will change to "Stop Streaming".
    *   Video (and audio if NDI Loopback) will be captured and streamed to the SRT URL.
    *   FFmpeg logs will appear in the "Logs" area.
    *   Application status messages will appear in the status bar and console.
6.  **Stop Streaming:**
    *   Click "Stop Streaming".

**Configuration File:**
Application settings are automatically saved to `pd_app_config.json` when closing and loaded on startup. The location is typically:
-   Linux: `~/.config/PDApp/pd_app_config.json`
-   Windows: `C:\\Users\\<YourUser>\\AppData\\Local\\PDApp\\PDApp\\pd_app_config.json`
-   macOS: `~/Library/Application Support/PDApp/pd_app_config.json`

You can manually edit this file (when the application is closed) to change settings like vMix host/port or default polling intervals if UI elements are not yet available for all options.

## 6. Troubleshooting

-   **FFmpeg Not Found:**
    -   **Error:** "FFmpeg executable not found."
    -   **Solution:** Ensure FFmpeg is installed and its location is added to your system's PATH environment variable.
-   **NDI Initialization Failed / NDI Source Not Found:**
    -   **Error:** "ndi.initialize() failed" or "Could not find specified NDI source..."
    -   **Solution:**
        -   Ensure the NDI SDK Runtime is installed correctly on your system.
        -   Verify that your NDI source (e.g., vMix NDI output) is active and on the same network.
        -   Check firewall settings to ensure NDI traffic is allowed.
-   **Cannot Open Camera (vMix Virtual Camera / OpenCV):**
    -   **Error:** "Failed to open vMix Virtual Camera..." or "Failed to open OpenCV source..."
    -   **Solution:**
        -   For vMix Virtual Camera: Ensure "External" output is activated in vMix. If `pygrabber` is not installed on Windows, detection might fail; install `pygrabber`. Ensure no other application is exclusively using the camera.
        -   For OpenCV: Verify the camera index or source string is correct. Ensure camera drivers are installed and the camera is not in use by another application.
-   **HTTP Tally Issues:**
    -   **Error:** "Connection error" or "Request timed out" for vMix API.
    -   **Solution:** Ensure vMix is running and its Web Controller (HTTP API) is enabled on the correct host and port (defaults to `http://127.0.0.1:8088`). Check firewall.
-   **Video/Audio Sync Issues in SRT Output:**
    -   This can be complex. Ensure adequate processing power. Experiment with FFmpeg parameters (latency, buffer sizes - though not currently exposed in UI). Network jitter can also affect SRT.
-   **Application Freezes:**
    -   If this occurs, check console logs for unhandled exceptions. Long timeouts in network operations or NDI discovery could temporarily make the UI less responsive, though threading aims to prevent this.

## 7. Known Issues & Limitations

-   **TCP Tally:** The TCP Tally functionality is a placeholder and not implemented.
-   **Backend WebSocket:** Connection to a backend WebSocket URL is a placeholder and not implemented.
-   **Windows Named Pipe for Audio:** The fallback for FFmpeg audio input on non-POSIX systems (Windows) uses a temporary file, which may not behave like a true pipe and could lead to issues with FFmpeg or disk space over very long sessions. A proper Windows named pipe implementation (`pywin32` or `ctypes`) would be more robust.
-   **Error Reporting:** While critical error signals have been added to threads, the `QMessageBox` popups in `MainWindow` for these signals were not fully implemented/applied due to persistent diff tool failures during development. Users currently rely on status bar messages and the log view for error details.
-   **NDI Source Name in OpenCV Mode:** The "NDI Virtual Input (OpenCV)" mode relies on OpenCV's `VideoCapture` to handle NDI source names. This requires an OpenCV build with NDI support (often via FFmpeg backend compiled with NDI). If not available, only camera indices will work.
-   **Configuration UI:** Not all configurable parameters (e.g., vMix host/port, polling intervals) have dedicated UI input fields; some must be changed in `config.json` directly.
-   **Limited Dynamic Parameter Changes:** Changing some parameters (like audio sample rate for an active SRT stream) mid-stream might not cause FFmpeg to reconfigure without a full stream restart.

## 8. Future Improvements

-   **Full TCP Tally Implementation.**
-   **Backend WebSocket Integration:** Implement actual data exchange with a backend server.
-   **Robust Windows Named Pipes:** Use `pywin32` or `ctypes` for more reliable audio piping to FFmpeg on Windows.
-   **Enhanced Error Handling:** Fully implement `QMessageBox` popups for all critical errors by resolving `pd_app.py` modification issues. Implement more specific exception handling.
-   **Advanced FFmpeg Controls:** Expose more FFmpeg parameters in the UI (e.g., bitrate, GOP size, encoding profile).
-   **UI for All Configurable Settings:** Add input fields for all parameters currently only editable in `config.json`.
-   **Stream Preview:** Implement an actual video preview within the GUI instead of the placeholder QLabel.
-   **OSC Integration:** Add OSC support for remote control or data output.
-   **Cross-platform Testing & Packaging:** Thoroughly test on Windows, macOS, and Linux. Create distributable packages.
-   **Code Refinements:** Continue to refactor complex methods and improve overall code structure (e.g., using a state pattern for mode management if complexity grows).
-   **Detailed Logging Levels:** Implement selectable logging levels (Debug, Info, Warning, Error).

---

This README provides a comprehensive guide to the PD Video Streaming Application.
