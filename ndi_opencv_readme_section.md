### NDI Source Handling in "NDI Virtual Input (OpenCV)" Mode

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
