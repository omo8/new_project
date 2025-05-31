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
        #### NDI Source Handling in "NDI Virtual Input (OpenCV)" Mode
        The "NDI Virtual Input (OpenCV)" mode provides a way to capture video sources using OpenCV's `cv2.VideoCapture()` function. This can include standard webcams, video files, and potentially NDI sources, depending on your OpenCV installation and system configuration.
        **Numerical Indices vs. Name Strings:**
        *   **Numerical Indices:** OpenCV can always access cameras using numerical indices (e.g., 0, 1, 2, ...). The first camera detected by the system is usually index 0, the second is 1, and so on. The order can sometimes be unpredictable, especially if you have multiple USB cameras or virtual cameras.
        *   **Camera Name Strings:** Some OpenCV backends (especially on Windows with `cv2.CAP_DSHOW` or when built with appropriate GStreamer/FFmpeg support) can open cameras using their exact name as listed by the system (e.g., "Logitech BRIO", "vMix Video").
        **Prerequisites for OpenCV to Recognize NDI Names Directly:**
        For OpenCV to open an NDI source directly by its network name (e.g., "MYCOMPUTER (OBS)"), OpenCV must be compiled with a backend that supports NDI. This typically means:
        1.  **NDI SDK Installed:** The NDI SDK and runtime libraries must be installed on the system where the application is running.
        2.  **OpenCV Built with NDI-enabled FFmpeg or GStreamer:** The FFmpeg or GStreamer libraries that OpenCV uses for video I/O must themselves be compiled with NDI support enabled. Standard pre-built OpenCV packages (e.g., from `pip install opencv-python`) often *do not* include an NDI-enabled FFmpeg/GStreamer backend by default. You might need to compile OpenCV from source with these dependencies configured or find a pre-built package that explicitly states NDI support.
        If these prerequisites are not met, trying to open an NDI source by its network name directly in OpenCV will likely fail.
        **Recommended Method: NDI Virtual Input Tool**
        The most reliable way to make an NDI source available to generic OpenCV applications (like this mode) is to use the **NDI Virtual Input** tool (part of the NDI Tools suite, available from [NDI.tv](https://ndi.tv/tools/)).
        1.  Run the NDI Virtual Input tool.
        2.  In the system tray, right-click the NDI Virtual Input icon.
        3.  Select the desired NDI network source from the list.
        4.  This NDI source will now appear to the system as a standard webcam (e.g., "NewTek NDI Video"). The exact name can vary.
        Once an NDI source is exposed as a virtual webcam via NDI Virtual Input, you can then use its assigned name (if your OpenCV backend supports names) or its numerical index in the "NDI/Cam Index/Name (OpenCV)" field of this application.
        **Finding the Correct Index or Name:**
        *   **Name:** If you're using NDI Virtual Input, the name will typically be something like "NewTek NDI Video". You can try entering this name directly. The `VmixVirtualCameraCaptureThread` in this application uses `pygrabber` (on Windows) to list camera names, which can help identify the correct name for the vMix Virtual Camera or NDI Virtual Input.
        *   **Index:** If names don't work or you're unsure, you may need to find the correct numerical index. This can sometimes be trial and error (0, 1, 2...). Some systems or third-party tools may list camera indices. The application's log (when attempting to open an OpenCV source by index) might also provide clues or error messages if an index is invalid.
        For dedicated NDI capture with richer features and more direct NDI SDK integration (including audio), the **"NDI Loopback"** mode of this application is generally recommended over the generic OpenCV mode for NDI sources.
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
        *   **NDI Virtual Input (OpenCV):** Enter the NDI source name or camera index in the "NDI/Cam Index/Name (OpenCV)" field. This mode is video-only for SRT streaming. (See section "NDI Source Handling in "NDI Virtual Input (OpenCV)" Mode" under Features for more details).
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
-   **NDI Source Name in OpenCV Mode:** The "NDI Virtual Input (OpenCV)" mode's ability to resolve NDI source names directly (e.g., "MYCOMPUTER (OBS)") depends heavily on the user's OpenCV build and its backend configurations (e.g., if it's compiled with NDI-enabled FFmpeg). An intended code refinement within the `GenericOpenCVCaptureThread` to more intelligently handle numeric-like identifiers versus string names was not implemented due to technical difficulties during development. For best practices on using NDI sources with OpenCV, refer to the "NDI Source Handling in 'NDI Virtual Input (OpenCV)' Mode" section under "Features". Using the NDI Virtual Input tool to create a standard webcam interface for NDI sources is often more reliable with generic OpenCV setups. If direct name resolution fails, using the camera's numerical index is a fallback.
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

## 한글 설명

### 1. 개요

PD 비디오 스트리밍 애플리케이션은 다양한 소스에서 비디오 및 오디오를 캡처하고, vMix의 탈리 정보를 처리하며, SRT를 통해 MediaMTX와 같은 미디어 서버로 출력을 스트리밍하도록 설계된 Python 기반 도구입니다. PyQt5로 구축된 그래픽 사용자 인터페이스(GUI)를 제공하여 소스, 구성 관리 및 스트리밍 프로세스 모니터링을 지원합니다.

이 애플리케이션은 다음을 포함한 여러 프로그램(PGM) 입력 소스를 지원합니다:
-   **NDI 루프백:** `ndi-python` 라이브러리를 사용하여 네트워크에서 사용 가능한 NDI 오디오 및 비디오 소스를 캡처하여 고품질, 저지연 입력을 제공합니다.
-   **vMix 가상 카메라:** vMix의 "External" 기능을 통해 비디오 출력을 캡처합니다. 이 기능은 vMix 메인 출력을 가상 웹캠(Windows DirectShow 소스)으로 노출합니다.
-   **NDI 가상 입력 (일반 OpenCV):** 표준 카메라 장치 또는 기타 OpenCV 호환 소스로 표시되는 NDI 소스를 캡처하기 위한 플레이스홀더입니다. 이는 더 일반적이며 NDI 이름을 사용하려면 특정 OpenCV 구성(예: FFMPEG 백엔드 사용)이 필요할 수 있습니다.

vMix의 탈리 정보는 다음을 통해 지원됩니다:
-   **HTTP API 폴링:** vMix HTTP API를 폴링하여 PGM/PVW 상태를 가져옵니다. 또한 가독성을 높이기 위해 입력 이름을 캐시하고 표시합니다.
-   **TCP 탈리 (플레이스홀더):** TCP 기반 탈리 연결을 위한 UI 요소가 있지만, 기본 구현은 플레이스홀더입니다.

애플리케이션은 최종 출력(비디오 및 NDI 루프백의 오디오)을 지정된 SRT URL로 스트리밍하며, 일반적으로 MediaMTX 또는 vMix와 같은 SRT 서버에서 수신합니다.

### 2. 주요 기능

-   **다중 PGM 소스 옵션:**
    -   `ndi-python`을 통한 NDI 루프백 (비디오 + 오디오).
    -   OpenCV 및 `pygrabber`를 통한 vMix 가상 카메라 (비디오 전용).
    -   일반 OpenCV 소스 (비디오 전용, 예: 웹캠, OpenCV가 지원하는 경우 NDI 이름).
        #### "NDI 가상 입력 (OpenCV)" 모드에서의 NDI 소스 처리
        "NDI 가상 입력 (OpenCV)" 모드는 OpenCV의 `cv2.VideoCapture()` 함수를 사용하여 비디오 소스를 캡처하는 방법을 제공합니다. 여기에는 표준 웹캠, 비디오 파일 및 OpenCV 설치 및 시스템 구성에 따라 NDI 소스가 포함될 수 있습니다.
        **숫자 인덱스 vs. 이름 문자열:**
        *   **숫자 인덱스:** OpenCV는 항상 숫자 인덱스(예: 0, 1, 2, ...)를 사용하여 카메라에 액세스할 수 있습니다. 시스템에서 감지된 첫 번째 카메라는 일반적으로 인덱스 0, 두 번째는 1 등입니다. 특히 여러 USB 카메라 또는 가상 카메라가 있는 경우 순서가 예측 불가능할 수 있습니다.
        *   **카메라 이름 문자열:** 일부 OpenCV 백엔드(특히 Windows에서 `cv2.CAP_DSHOW`를 사용하거나 적절한 GStreamer/FFmpeg 지원으로 빌드된 경우)는 시스템에 나열된 정확한 이름(예: "Logitech BRIO", "vMix Video")을 사용하여 카메라를 열 수 있습니다.
        **OpenCV가 NDI 이름을 직접 인식하기 위한 전제 조건:**
        OpenCV가 네트워크 이름(예: "MYCOMPUTER (OBS)")으로 NDI 소스를 직접 열려면 NDI를 지원하는 백엔드로 OpenCV를 컴파일해야 합니다. 이는 일반적으로 다음을 의미합니다:
        1.  **NDI SDK 설치됨:** 애플리케이션이 실행되는 시스템에 NDI SDK 및 런타임 라이브러리가 설치되어 있어야 합니다.
        2.  **NDI 지원 FFmpeg 또는 GStreamer로 빌드된 OpenCV:** OpenCV가 비디오 I/O에 사용하는 FFmpeg 또는 GStreamer 라이브러리 자체가 NDI 지원이 활성화된 상태로 컴파일되어야 합니다. 표준 사전 빌드된 OpenCV 패키지(예: `pip install opencv-python`으로 설치)에는 종종 기본적으로 NDI 지원 FFmpeg/GStreamer 백엔드가 포함되어 있지 *않습니다*. 이러한 종속성이 구성된 상태로 소스에서 OpenCV를 컴파일하거나 NDI 지원을 명시적으로 나타내는 사전 빌드된 패키지를 찾아야 할 수 있습니다.
        이러한 전제 조건이 충족되지 않으면 OpenCV에서 네트워크 이름으로 NDI 소스를 직접 열려고 하면 실패할 가능성이 높습니다.
        **권장 방법: NDI 가상 입력 도구**
        NDI 소스를 이 모드와 같은 일반 OpenCV 애플리케이션에서 사용할 수 있도록 하는 가장 안정적인 방법은 **NDI 가상 입력** 도구([NDI.tv](https://ndi.tv/tools/)에서 사용 가능한 NDI Tools 제품군의 일부)를 사용하는 것입니다.
        1.  NDI 가상 입력 도구를 실행합니다.
        2.  시스템 트레이에서 NDI 가상 입력 아이콘을 마우스 오른쪽 버튼으로 클릭합니다.
        3.  목록에서 원하는 NDI 네트워크 소스를 선택합니다.
        4.  이제 이 NDI 소스가 시스템에 표준 웹캠(예: "NewTek NDI Video")으로 나타납니다. 정확한 이름은 다를 수 있습니다.
        NDI 가상 입력을 통해 NDI 소스가 가상 웹캠으로 노출되면 이 애플리케이션의 "NDI/Cam Index/Name (OpenCV)" 필드에서 할당된 이름(OpenCV 백엔드가 이름을 지원하는 경우) 또는 숫자 인덱스를 사용할 수 있습니다.
        **올바른 인덱스 또는 이름 찾기:**
        *   **이름:** NDI 가상 입력을 사용하는 경우 이름은 일반적으로 "NewTek NDI Video"와 같습니다. 이 이름을 직접 입력해 볼 수 있습니다. 이 애플리케이션의 `VmixVirtualCameraCaptureThread`는 Windows에서 `pygrabber`를 사용하여 카메라 이름을 나열하므로 vMix 가상 카메라 또는 NDI 가상 입력의 올바른 이름을 식별하는 데 도움이 될 수 있습니다.
        *   **인덱스:** 이름이 작동하지 않거나 확실하지 않은 경우 올바른 숫자 인덱스를 찾아야 할 수 있습니다. 이는 때때로 시행착오(0, 1, 2...)를 거쳐야 할 수 있습니다. 일부 시스템 또는 타사 도구는 카메라 인덱스를 나열할 수 있습니다. 인덱스로 OpenCV 소스를 열려고 할 때 애플리케이션 로그에 단서나 오류 메시지가 표시될 수도 있습니다.
        더 풍부한 기능과 직접적인 NDI SDK 통합(오디오 포함)을 갖춘 전용 NDI 캡처의 경우, 이 애플리케이션의 **"NDI 루프백"** 모드가 일반적으로 NDI 소스에 대한 일반 OpenCV 모드보다 권장됩니다.
-   **동적 NDI 소스 검색:** NDI 루프백 모드에 대해 사용 가능한 NDI 소스를 자동으로 검색하고 목록화합니다.
-   **vMix 탈리 연동:**
    -   vMix의 프로그램(PGM) 및 프리뷰(PVW) 탈리 상태를 표시합니다.
    -   vMix HTTP API 폴링을 통한 탈리를 지원합니다.
    -   PGM/PVW에 대한 입력 번호와 함께 vMix 입력 이름을 가져와 표시합니다.
    -   TCP 기반 탈리 연결을 위한 플레이스홀더.
-   **SRT 스트리밍:**
    -   캡처된 비디오 (및 NDI 루프백의 오디오)를 FFmpeg을 사용하여 지정된 SRT URL로 스트리밍합니다.
    -   FFmpeg 프로세스 라이프사이클을 관리합니다.
-   **설정 관리:**
    -   선택한 소스, URL, vMix 연결 세부 정보 등 애플리케이션 설정을 사용자의 애플리케이션 구성 디렉터리에 `config.json` 파일로 저장하고 불러옵니다.
-   **GUI:**
    -   PyQt5로 구축된 사용자 친화적인 인터페이스.
    -   PGM 소스, NDI 소스, 탈리 모드 선택 컨트롤.
    -   SRT URL, 백엔드 WebSocket URL 입력 필드.
    -   입력 이름과 함께 PGM/PVW 탈리 정보를 표시합니다.
    -   애플리케이션 상태, 오류 및 FFmpeg 출력을 위한 로그 표시 영역.
    -   실시간 피드백을 위한 상태 표시줄.
-   **FFmpeg 로그 표시:** FFmpeg의 `stderr` 출력을 캡처하여 모니터링 및 문제 해결을 위해 표시합니다.
-   **크로스 플랫폼 고려 사항:**
    -   설정 파일 위치에 `QStandardPaths`를 사용합니다.
    -   카메라 액세스(예: Windows의 `cv2.CAP_DSHOW`) 및 명명된 파이프(FFmpeg 오디오용 POSIX `mkfifo` 대 Windows 임시 파일 대체)에 대한 플랫폼 차이점을 기록합니다.

### 3. 의존성

이 애플리케이션은 여러 Python 라이브러리에 의존합니다. Python 환경에 이러한 라이브러리가 설치되어 있는지 확인하십시오. 일반적으로 `requirements.txt` 파일에 이러한 항목이 나열됩니다:

-   **PyQt5:** 그래픽 사용자 인터페이스용.
-   **NumPy:** 특히 비디오 프레임 관련 수치 연산용.
-   **OpenCV (cv2):** vMix 가상 카메라 및 일반 OpenCV 소스에서 비디오 캡처용.
    -   `opencv-python` 또는 `opencv-contrib-python`.
-   **ndi-python (`ndi`):** NDI 루프백 캡처용. 시스템에 NDI SDK가 설치되어 있어야 합니다.
-   **requests:** vMix에 HTTP API 호출(탈리 및 입력 이름 가져오기)용.
-   **pygrabber:** (Windows 전용) Windows의 DirectShow 장치 중에서 이름으로 vMix 가상 카메라를 검색합니다. 이는 선택 사항이지만 Windows에서 안정적인 vMix 가상 카메라 감지를 위해 강력히 권장됩니다. 없는 경우 애플리케이션은 덜 안정적인 대체 방법을 시도합니다.

**외부 소프트웨어:**
-   **FFmpeg:** SRT 스트리밍에 필요합니다. 시스템의 PATH에 설치되고 액세스할 수 있어야 합니다.
-   **NDI SDK:** NDI 기능을 사용하려면 시스템에 NDI 런타임/SDK가 설치되어 있어야 합니다.
-   **vMix:** (vMix 특정 기능 사용 시 선택 사항) NDI 소스, 가상 카메라 출력 및 탈리 정보 제공용.

### 4. 설치

1.  **Python 설치:** Python 3.x가 설치되어 있는지 확인합니다.
2.  **NDI SDK 설치:** [NDI.tv](https://ndi.tv/sdk/)에서 NDI SDK(런타임)를 다운로드하여 설치합니다.
3.  **FFmpeg 설치:** [ffmpeg.org](https://ffmpeg.org/download.html)에서 FFmpeg을 다운로드하고 시스템의 PATH 환경 변수에 추가되었는지 확인합니다.
4.  **가상 환경 생성 (권장):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows의 경우: venv\Scripts\activate
    ```
5.  **Python 의존성 설치:**
    ```bash
    pip install PyQt5 numpy opencv-python ndi-python requests pygrabber
    ```
    (참고: `pygrabber`는 주로 Windows용입니다. 다른 OS에서는 필요하지 않은 경우 설치를 건너뛸 수 있지만 코드는 이를 포함합니다.)
6.  **애플리케이션 파일 복제 또는 다운로드:** 모든 애플리케이션 Python 파일(`pd_app.py`, `ndi_loopback_capture_thread.py` 등)을 단일 디렉터리에 배치합니다.
7.  **vMix 구성 (vMix 기능 사용 시):**
    *   **NDI 출력:** vMix에서 사용하려는 소스(예: 메인 믹스, 특정 입력)에 대해 NDI 출력을 활성화합니다.
    *   **가상 카메라:** vMix 설정에서 "External" 출력을 활성화하여 vMix 가상 카메라를 활성화합니다.
    *   **HTTP API:** vMix 설정 > Web Controller에서 vMix 웹 컨트롤러(HTTP API)가 활성화되어 있는지 확인합니다. 호스트(일반적으로 `127.0.0.1`)와 포트(기본값 `8088`)를 확인합니다.
    *   **TCP 탈리:** (현재 플레이스홀더인) TCP 탈리 기능을 사용하려는 경우 vMix 설정 > Tally Lights에서 TCP 탈리가 활성화되어 있는지 확인합니다.

### 5. 사용법

1.  **애플리케이션 실행:**
    ```bash
    python pd_app.py
    ```
2.  **프로그램 소스 구성:**
    *   "Program Source" 드롭다운에서 원하는 비디오 소스를 선택합니다:
        *   **NDI Loopback:** "NDI Source" 드롭다운이 검색된 NDI 소스로 채워집니다. 하나를 선택합니다. 이 소스에서 오디오가 캡처됩니다.
        *   **NDI Virtual Input (OpenCV):** "NDI/Cam Index/Name (OpenCV)" 필드에 NDI 소스 이름 또는 카메라 인덱스를 입력합니다. 이 모드는 SRT 스트리밍 시 비디오 전용입니다. (자세한 내용은 특징 섹션의 "NDI 가상 입력 (OpenCV)" 모드에서의 NDI 소스 처리" 참조).
        *   **vMix Virtual Camera:** 애플리케이션이 vMix 가상 카메라를 자동 감지하려고 시도합니다. 이 모드는 SRT 스트리밍 시 비디오 전용입니다.
3.  **탈리 구성 (선택 사항):**
    *   "Tally Mode"를 선택합니다:
        *   **HTTP Tally:** vMix API를 폴링합니다. vMix 호스트/포트가 올바른지 확인합니다 (현재 기본값이며, 설정 파일에서 변경 가능).
        *   **TCP Tally:** 플레이스홀더.
        *   **None:** 탈리를 비활성화합니다.
    *   "Connect Tally"를 클릭하여 탈리 데이터 수신을 시작합니다. PGM/PVW 레이블이 입력 이름과 번호로 업데이트됩니다.
4.  **스트리밍 및 백엔드 구성:**
    *   **SRT URL:** 대상 SRT URL을 입력합니다 (예: `srt://your_media_server_ip:1234`).
    *   **Backend WS URL:** 백엔드의 WebSocket URL을 입력합니다 (현재 플레이스홀더 기능).
5.  **스트리밍 시작:**
    *   "Start Streaming"을 클릭합니다. 버튼이 "Stop Streaming"으로 변경됩니다.
    *   비디오 (및 NDI 루프백의 경우 오디오)가 캡처되어 SRT URL로 스트리밍됩니다.
    *   FFmpeg 로그가 "Logs" 영역에 나타납니다.
    *   애플리케이션 상태 메시지가 상태 표시줄과 콘솔에 나타납니다.
6.  **스트리밍 중지:**
    *   "Stop Streaming"을 클릭합니다.

**설정 파일:**
애플리케이션 설정은 종료 시 `pd_app_config.json`에 자동으로 저장되고 시작 시 불러옵니다. 일반적인 위치는 다음과 같습니다:
-   Linux: `~/.config/PDApp/pd_app_config.json`
-   Windows: `C:\\Users\\<사용자이름>\\AppData\\Local\\PDApp\\PDApp\\pd_app_config.json`
-   macOS: `~/Library/Application Support/PDApp/pd_app_config.json`

모든 옵션에 대한 UI 요소가 아직 제공되지 않는 경우, 애플리케이션이 닫혀 있을 때 이 파일을 수동으로 편집하여 vMix 호스트/포트 또는 기본 폴링 간격과 같은 설정을 변경할 수 있습니다.

### 6. 문제 해결

-   **FFmpeg를 찾을 수 없음:**
    -   **오류:** "FFmpeg executable not found."
    -   **해결책:** FFmpeg이 설치되어 있고 해당 위치가 시스템의 PATH 환경 변수에 추가되었는지 확인합니다.
-   **NDI 초기화 실패 / NDI 소스를 찾을 수 없음:**
    -   **오류:** "ndi.initialize() failed" 또는 "Could not find specified NDI source..."
    -   **해결책:**
        -   시스템에 NDI SDK 런타임이 올바르게 설치되었는지 확인합니다.
        -   NDI 소스(예: vMix NDI 출력)가 활성 상태이고 동일한 네트워크에 있는지 확인합니다.
        -   방화벽 설정을 확인하여 NDI 트래픽이 허용되는지 확인합니다.
-   **카메라를 열 수 없음 (vMix 가상 카메라 / OpenCV):**
    -   **오류:** "Failed to open vMix Virtual Camera..." 또는 "Failed to open OpenCV source..."
    -   **해결책:**
        -   vMix 가상 카메라의 경우: vMix에서 "External" 출력이 활성화되어 있는지 확인합니다. Windows에 `pygrabber`가 설치되어 있지 않으면 감지가 실패할 수 있습니다. `pygrabber`를 설치하십시오. 다른 애플리케이션이 카메라를 독점적으로 사용하고 있지 않은지 확인합니다.
        -   OpenCV의 경우: 카메라 인덱스 또는 소스 문자열이 올바른지 확인합니다. 카메라 드라이버가 설치되어 있고 다른 애플리케이션에서 카메라를 사용하고 있지 않은지 확인합니다.
-   **HTTP 탈리 문제:**
    -   **오류:** vMix API에 대한 "Connection error" 또는 "Request timed out".
    -   **해결책:** vMix가 실행 중이고 해당 웹 컨트롤러(HTTP API)가 올바른 호스트 및 포트(기본값 `http://127.0.0.1:8088`)에서 활성화되어 있는지 확인합니다. 방화벽을 확인합니다.
-   **SRT 출력의 비디오/오디오 동기화 문제:**
    -   이는 복잡할 수 있습니다. 충분한 처리 능력을 확보하십시오. FFmpeg 매개변수(지연 시간, 버퍼 크기 - 현재 UI에 노출되지 않음)를 실험해 보십시오. 네트워크 지터도 SRT에 영향을 줄 수 있습니다.
-   **애플리케이션 멈춤:**
    -   이런 현상이 발생하면 콘솔 로그에서 처리되지 않은 예외가 있는지 확인하십시오. 네트워크 작업 또는 NDI 검색의 긴 시간 초과는 스레딩으로 이를 방지하려고 하지만 일시적으로 UI 응답성을 저하시킬 수 있습니다.

### 7. 알려진 문제점 및 제한 사항

-   **TCP 탈리:** TCP 탈리 기능은 플레이스홀더이며 구현되지 않았습니다.
-   **백엔드 WebSocket:** 백엔드 WebSocket URL 연결은 플레이스홀더이며 구현되지 않았습니다.
-   **Windows 명명된 파이프 오디오:** 비 POSIX 시스템(Windows)에서 FFmpeg 오디오 입력에 대한 대체 방법으로 임시 파일을 사용하며, 이는 실제 파이프처럼 작동하지 않을 수 있고 매우 긴 세션 동안 FFmpeg 또는 디스크 공간 문제를 일으킬 수 있습니다. 적절한 Windows 명명된 파이프 구현(`pywin32` 또는 `ctypes` 사용)이 더 안정적일 것입니다.
-   **오류 보고:** 스레드에 중요 오류 신호가 추가되었지만, `MainWindow`에서 이러한 신호에 대한 `QMessageBox` 팝업은 개발 중 지속적인 diff 도구 실패로 인해 완전히 구현/적용되지 못했습니다. 사용자는 현재 상태 표시줄 메시지와 로그 보기에 의존하여 오류 세부 정보를 확인해야 합니다.
-   **OpenCV 모드의 NDI 소스 이름:** "NDI 가상 입력 (OpenCV)" 모드에서 NDI 소스 이름(예: "MYCOMPUTER (OBS)")을 직접 확인하는 기능은 사용자의 OpenCV 빌드 및 백엔드 구성(예: NDI 지원 FFmpeg로 컴파일되었는지 여부)에 크게 의존합니다. `GenericOpenCVCaptureThread` 내에서 숫자 형식 식별자와 문자열 이름을 보다 지능적으로 처리하기 위한 코드 개선이 계획되었으나 개발 중 기술적 어려움으로 인해 구현되지 못했습니다. OpenCV와 함께 NDI 소스를 사용하는 최선의 방법에 대해서는 "특징" 섹션 아래의 "NDI 가상 입력 (OpenCV)" 모드에서의 NDI 소스 처리" 부분을 참조하십시오. NDI 가상 입력 도구를 사용하여 NDI 소스에 대한 표준 웹캠 인터페이스를 만드는 것이 일반적인 OpenCV 설정에서 더 안정적일 수 있습니다. 직접적인 이름 확인이 실패할 경우 카메라의 숫자 인덱스를 사용하는 것이 대안입니다.
-   **설정 UI:** 일부 구성 가능한 매개변수(예: vMix 호스트/포트, 폴링 간격)에는 전용 UI 입력 필드가 없으므로 `config.json`에서 직접 변경해야 합니다.
-   **제한된 동적 매개변수 변경:** 활성 SRT 스트림에 대한 오디오 샘플 속도와 같은 일부 매개변수를 스트림 중간에 변경해도 전체 스트림을 다시 시작하지 않으면 FFmpeg이 재구성되지 않을 수 있습니다.

### 8. 향후 개선 사항

-   **TCP 탈리 전체 구현.**
-   **백엔드 WebSocket 연동:** 백엔드 서버와의 실제 데이터 교환을 구현합니다.
-   **안정적인 Windows 명명된 파이프:** Windows에서 FFmpeg으로 더 안정적인 오디오 파이핑을 위해 `pywin32` 또는 `ctypes`를 사용합니다.
-   **향상된 오류 처리:** `pd_app.py` 수정 문제를 해결하여 모든 중요 오류에 대해 `QMessageBox` 팝업을 완전히 구현합니다. 보다 구체적인 예외 처리를 구현합니다.
-   **고급 FFmpeg 제어:** UI에 더 많은 FFmpeg 매개변수(예: 비트 전송률, GOP 크기, 인코딩 프로필)를 노출합니다.
-   **모든 구성 가능 설정에 대한 UI:** 현재 `config.json`에서만 편집 가능한 모든 매개변수에 대한 입력 필드를 추가합니다.
-   **스트림 미리보기:** 플레이스홀더 QLabel 대신 GUI 내에 실제 비디오 미리보기를 구현합니다.
-   **OSC 연동:** 원격 제어 또는 데이터 출력을 위한 OSC 지원을 추가합니다.
-   **크로스 플랫폼 테스트 및 패키징:** Windows, macOS 및 Linux에서 철저히 테스트합니다. 배포 가능한 패키지를 만듭니다.
-   **코드 개선:** 복잡한 메서드를 계속 리팩토링하고 전체 코드 구조를 개선합니다(예: 복잡성이 증가할 경우 모드 관리를 위한 상태 패턴 사용).
-   **상세 로깅 수준:** 선택 가능한 로깅 수준(디버그, 정보, 경고, 오류)을 구현합니다.

---

이 README는 PD 비디오 스트리밍 애플리케이션에 대한 포괄적인 가이드를 제공합니다.
[end of README.md]
