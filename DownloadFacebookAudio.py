import os
import re
from datetime import datetime
from typing import Optional
import yt_dlp
import requests
from urllib.parse import urljoin
import csv

### Replace with path to .exe for ffmpeg.exe and ffprobe.exe  ###
FFMPEG_LOCATION = r"PUT_YOUR_PATH_HERE\ffmpeg\ffmpeg.exe"
FFPROBE_LOCATION = r"PUT_YOUR_PATH_HERE\ffmpeg\ffprobe.exe"
standard_ydl_opts = {'quiet': True,
                     'ffmpeg_location': FFMPEG_LOCATION,
                     'ffprobe_location': FFPROBE_LOCATION}


def download_facebook_video(video_url: str, base_name: Optional[str] = None,
                            output_dir: str = ".") -> Optional[str]:
    """
    Downloads the full video from a Facebook URL.

    :param video_url: URL of the Facebook video.
    :param base_name: If given, used as the filename (without extension).
    :param output_dir: Directory to save the video file.
    :return: Path to the downloaded video, or None on failure.
    """
    try:
        # build output template
        if base_name:
            outtmpl = os.path.join(output_dir, f"{base_name}.%(ext)s")
        else:
            outtmpl = os.path.join(output_dir, "%(upload_date)s_%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_LOCATION,
            'ffprobe_location': FFPROBE_LOCATION,
            'quiet': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None


def download_sermon_videos(input_csv_path: str, output_dir: str,
                           church_name: str, default_speaker: str) -> None:
    """
    Reads a CSV of Facebook video links and downloads each video using download_facebook_video.
    Filenames will be prefixed with [church_name]_[speaker_name][_title].

    :param input_csv_path: Path to CSV file with header containing 'VideoLink', optional 'Speaker', optional 'Title'
    :param output_dir: Directory where downloaded videos will be saved
    :param church_name: Prefix for each filename indicating the church
    :param default_speaker: Speaker name to use when the 'Speaker' column is empty
    :return: None
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(input_csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        # Validate CSV columns
        if 'VideoLink' not in (reader.fieldnames or []):
            raise ValueError("Input CSV must contain a 'VideoLink' column")
        rows = list(reader)
        total = len(rows)

    for idx, row in enumerate(rows, start=1):
        video_url = (row.get('VideoLink') or '').strip()
        if not video_url:
            print(f"Row {idx}/{total}: missing VideoLink, skipping")
            continue

        # Determine speaker
        speaker = (row.get('Speaker') or '').strip() or default_speaker
        speaker_clean = re.sub(r'[\\/*?:"<>|]', '', speaker).replace(' ', '_')

        # Determine optional title
        raw_title = (row.get('Title') or '').strip()
        if raw_title:
            title_clean = re.sub(r'[\\/*?:"<>|]', '', raw_title).replace(' ', '_')
            base_name = f"{church_name}_{speaker_clean}_{title_clean}"
        else:
            base_name = f"{church_name}_{speaker_clean}"

        # Download video
        try:
            out_path = download_facebook_video(
                video_url=video_url,
                base_name=base_name,
                output_dir=output_dir
            )
            if out_path:
                print(f"Row {idx}/{total}: downloaded to {out_path}")
            else:
                print(f"Row {idx}/{total}: failed to download {video_url}")
        except Exception as e:
            print(f"Row {idx}/{total}: error for {video_url} → {e}")


def download_video_thumbnail(video_url: str, save_path: str) -> bool:
    """
    Download the thumbnail image of a video given its URL.

    :param video_url: URL of the Facebook video.
    :param save_path: Full file path (including extension) where the thumbnail will be saved.
    :return: True if download succeeds, False otherwise.
    """
    try:
        with yt_dlp.YoutubeDL(standard_ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        thumb_url = info.get('thumbnail')
        if not thumb_url:
            return False

        resp = requests.get(thumb_url, stream=True, timeout=10)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(e)
        return False


def download_facebook_audio(video_url: str, base_name: Optional[str] = None,
                            include_original_name: bool = True, target_ext: str = 'm4a',
                            output_dir: str = ".",
                            fetch_thumbnail: bool = True) -> Optional[str]:
    """
    Downloads audio from a Facebook video and names the file based on upload date.
    Name format will be [base_name]_[upload_date]_[original_name].[ext]

    :param video_url: URL of the Facebook video.
    :param base_name: If not None, will be the start of the output name.
    :param include_original_name: If True, will include the original video title in the filename.
    :param target_ext: What type of audio file to download (e.g. 'm4a', 'mp3').
    :param output_dir: Directory to save the audio file.
    :param fetch_thumbnail: If True, also download the video thumbnail.
    :return: Path to the downloaded audio file or None if failed.
    """
    try:
        # Extract metadata
        with yt_dlp.YoutubeDL(standard_ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        upload_date = info.get('upload_date')  # YYYYMMDD
        raw_title = info.get('title', '')
        # Sanitize original title for filesystem
        original_name = re.sub(r'[\\/*?:"<>|]', '', raw_title).replace(' ', '_')

        # Build filename parts
        parts: list[str] = []
        if base_name:
            parts.append(base_name)
        if upload_date:
            dt = datetime.strptime(upload_date, '%Y%m%d')
            parts.append(dt.strftime('%Y-%m-%d'))
        if include_original_name and original_name:
            parts.append(original_name)
        if not parts:
            parts.append(original_name or 'facebook_audio')

        filename_base = "_".join(parts)
        filename = f"{filename_base}.{target_ext}"
        output_path = os.path.join(output_dir, filename)

        # Download audio and convert
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'quiet': False,
            'ffmpeg_location': FFMPEG_LOCATION,
            'ffprobe_location': FFPROBE_LOCATION,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': target_ext,
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # optionally fetch thumbnail
        if fetch_thumbnail:
            # choose .jpg by default
            thumb_path = os.path.join(output_dir, f"{filename_base}{'.jpg'}")
            success = download_video_thumbnail(video_url, thumb_path)
            if not success:
                print(f"Warning: failed to download thumbnail for {video_url}")

        return output_path

    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None


def download_sermon_audio(input_csv_path: str, output_dir: str, church_name: str,
                          default_speaker: Optional[str] = None,
                          include_original_name=True) -> None:
    """
    Will call download_facebook_audio to download audio from a CSV of links.
    Base name for download_facebook_audio is [church_name]_[speaker_name]_[title?].

    :param input_csv_path: Path to CSV file (with header) containing columns 'VideoLink',
                           optional 'Speaker', optional 'Title'
    :param output_dir: Directory where downloaded audio files will be saved
    :param church_name: Prefix for each filename indicating the church
    :param default_speaker: Speaker name to use when the 'Speaker' column is empty
    :param include_original_name: If True, will include the original video title in the filename.
    :return: None
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f'Opening {input_csv_path}')
    with open(input_csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if 'VideoLink' not in (reader.fieldnames or []):
            raise ValueError("Input CSV must contain a 'VideoLink' column")
        rows = list(reader)
        total = len(rows)

    for idx, row in enumerate(rows, start=1):
        video_url = (row.get('VideoLink') or '').strip()
        if not video_url:
            print(f"Row {idx}/{total}: missing VideoLink, skipping")
            continue

        # Determine speaker
        speaker = (row.get('Speaker') or '').strip() or default_speaker
        if speaker:
            speaker_clean = re.sub(r'[\\/*?:"<>|]', '', speaker).replace(' ', '_')
            speaker_clean = '_' + speaker_clean
        else:
            speaker_clean = ''

        # Determine optional title
        raw_title = (row.get('Title') or '').strip()
        if raw_title:
            title_clean = re.sub(r'[\\/*?:"<>|]', '', raw_title).replace(' ', '-')
            base_name = f"{church_name}{speaker_clean}_{title_clean}"
        else:
            base_name = f"{church_name}{speaker_clean}"

        # Download
        try:
            out_path = download_facebook_audio(
                video_url=video_url,
                base_name=base_name,
                output_dir=output_dir,
                include_original_name=include_original_name
            )
            if out_path:
                print(f"Row {idx}/{total}: downloaded to {out_path}")
            else:
                print(f"Row {idx}/{total}: failed to download {video_url}")
        except Exception as e:
            print(f"Row {idx}/{total}: error for {video_url} → {e}")


def extract_video_links(html_path: str, output_csv_path: str) -> None:
    """
    Extracts Facebook video links from a saved HTML file and writes them to a CSV,
    removing duplicates. Matches both relative and absolute URLs, with either
    numeric page IDs or named pages.

    :param html_path: Path to the HTML file containing video links.
    :param output_csv_path: Path to the output CSV file to write the links.
    :return: None
    """
    print(f'Extracting video urls from {html_path}')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match hrefs like:
    #   /123456/videos/7890
    #   /pagename/videos/7890/
    #   https://www.facebook.com/123456/videos/7890/
    #   https://www.facebook.com/pagename/videos/7890
    pattern = r'href="((?:https?://(?:www\.)?facebook\.com)?/[^"/]+/videos/\d+/?[^"]*)"'
    raw_links = re.findall(pattern, content)

    base_url = "https://www.facebook.com"
    full_links = set()
    for link in raw_links:
        # normalize trailing slash
        link = link.rstrip('/')
        if link.startswith('http'):
            full = link
        else:
            full = urljoin(base_url, link)
        full_links.add(full)

    sorted_links = sorted(full_links)
    print(f'Found {len(sorted_links)} video links.')
    # Write to CSV with empty Speaker and Title columns
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['VideoLink', 'Speaker', 'Title'])
        for link in sorted_links:
            writer.writerow([link, '', ''])


def run_standard(root_dir: str, church_name: str,
                 default_speaker: Optional[str] = None,
                 regenerate_csv: bool = False) -> None:
    """
    Execute the full Facebook video‐to‐audio pipeline for a directory of sermons.

    This helper automates two primary steps, using a folder populated with a
    saved Facebook “Videos” page HTML:

      1. **Extract video links**
         Reads `<root_dir>/_videos.html` (which you must save via your browser’s
         inspector after scrolling to load all entries) and writes a CSV of
         unique video URLs to `<root_dir>/_sermons.csv`, including empty
         `Speaker` and `Title` columns. This step is skipped if the CSV already
         exists and `regenerate_csv` is False.

      2. **Download audio**
         Reads the generated CSV and, for each row, constructs a filename of the
         form:
            `[church_name]_[speaker?]_[title?]_[YYYY-MM-DD]_[original_video_title].<ext>`
         It then invokes `download_facebook_audio` to fetch the audio and,
         optionally, the video thumbnail. Downloaded files are saved directly
         into `root_dir`.

    Files & outputs:
      - Input:  `<root_dir>/_videos.html`
      - Step 1: `<root_dir>/_sermons.csv`
      - Step 2: audio files and optional `.jpg` thumbnails in `<root_dir>`

    :param root_dir: Path to the folder containing `_videos.html` and where all
                     outputs (`_sermons.csv`, audio, thumbnails) will be saved.
    :param church_name: Identifier (no spaces) to prefix each downloaded filename.
    :param default_speaker: Use this name for any CSV rows missing a `Speaker`
                            entry; leave as None to keep blanks and fill in later.
    :param regenerate_csv: If True, always re‐extract links and overwrite the
                           existing `_sermons.csv`; otherwise skip extraction
                           if the CSV already exists.
    :return: None. Side effects write files into `root_dir`.
    """
    sermon_csv = os.path.join(root_dir, "_sermons.csv")
    video_html = os.path.join(root_dir, "_videos.html")
    if not os.path.isfile(video_html):
        print(f'Could not find {video_html}. Please fully load Facebook video page and save html')

    if os.path.isfile(sermon_csv) and not regenerate_csv:
        print(f'Sermon csv already exists at {sermon_csv}. Skipping processing of {video_html}')
    else:
        extract_video_links(video_html, sermon_csv)

    # Step 2: download audio files
    download_sermon_audio(input_csv_path=sermon_csv, output_dir=root_dir,
                          church_name=church_name, default_speaker=default_speaker)


# Example usage
if __name__ == "__main__":
    # url = r'https://www.facebook.com/100070146310727/videos/483071138058657'
    # download_facebook_audio(url, output_dir=r'M:\FacebookLiveDownloads\Shiloh')

    run_standard(r'M:\FacebookLiveDownloads\Shiloh', "ShilohPBC")
