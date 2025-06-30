**Facebook Video & Audio Download Tool**

This repository contains Python scripts to extract Facebook video links from a saved HTML file, download the full videos or audio tracks (with optional thumbnails), and name files based on church name, speaker, and title. Below is the typical workflow and usage instructions.

---

## Prerequisites

- **Python 3.x** installed
- **yt-dlp** (for downloading media) and **requests** (for thumbnails)
  ```bash
  pip install yt-dlp requests
  ```
- **FFmpeg** and **ffprobe** executables available locally
  - Edit the `FFMPEG_LOCATION` and `FFPROBE_LOCATION` constants in the script to point to your installations.

---

## Workflow Steps

1. **Fetch the Facebook videos page HTML**

   - Open your browser and navigate to the Facebook page’s **Videos** tab (e.g. [https://www.facebook.com/YourPage/videos](https://www.facebook.com/YourPage/videos)).
   - Scroll all the way to the bottom so that all video entries load.
   - Press **F12** (or right-click → Inspect) to open Developer Tools.
   - In the **Elements** panel, find the `<body>` (or top-level) element, right-click it, and choose **Copy → Copy outerHTML**.
   - Paste that content into a file named `_videos.html` in the folder where you want to download your media.

2. **Prepare your folder**

   - Create (or use) a directory where both the `_videos.html` and your script live.
   - Ensure the script has write permission to that folder (for downloads and CSV).

3. **Run the standard pipeline**

   - In a Python REPL or script, import and invoke:

   ```python
   from your_module import run_standard

   # Example: replace with your folder path and church name
   run_standard(r"C:\Path\To\YourFolder", church_name="YourChurch", default_speaker=None)
   ```

   - **Notes:**
     - `default_speaker=None` will skip using a single default speaker. This is useful if your CSV’s `Speaker` column varies widely and you want to set it manually later.
     - If you do have a single default speaker for all entries, pass their name as the third argument instead of `None`.

4. **What happens internally**

   1. `extract_video_links` reads `_videos.html`, locates all `href` attributes matching Facebook video URLs (both relative and absolute), deduplicates, and writes them to `_sermons.csv` with empty `Speaker` and `Title` columns.
   2. `download_sermon_audio` reads `_sermons.csv` and for each row:
      - Builds a `base_name` using `[church_name]_[speaker]_[title?]`.
      - Calls `download_facebook_audio` to download the audio (and optional thumbnail) named accordingly.
   3. You can also run `download_sermon_videos` in place of audio to fetch full video files.

---

## Customization & Tips

- **Including Thumbnails**: By default, thumbnails are saved alongside audio (with `.jpg` extension). You can disable this by setting `fetch_thumbnail=False` when calling `download_facebook_audio` directly.
- **File Naming**: The script sanitizes names by replacing spaces with underscores and removing illegal filesystem characters.
- **Error Handling**: Any missing links or download errors will be printed to the console but won’t stop the batch.

---

Feel free to open an issue or extend the scripts for your specific use cases!

