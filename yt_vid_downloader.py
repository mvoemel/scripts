"""
YouTube Video Downloader (using yt-dlp)

This script allows you to download YouTube videos (or other supported sites by yt-dlp)
with flexible parameters such as resolution, output format, and download location.

⚡ Requirements:
    pip install yt-dlp

📌 Usage examples:
    # Download a video in 4K (2160p) MP4 format
    python downloader.py "https://youtube.com/watch?v=XXXX" -r 2160 -m mp4

    # Download a video in 1080p MKV format to a custom folder
    python downloader.py "https://youtube.com/watch?v=XXXX" -r 1080 -m mkv -o my_videos

    # Download at best available quality without forcing resolution
    python downloader.py "https://youtube.com/watch?v=XXXX"

Note:
    Make sure you only download videos you own or have permission to download.
    Respect YouTube's Terms of Service.
"""

import argparse
import yt_dlp

def download_video(url, resolution, output_path, merge_format):
    # Build format string for yt-dlp
    if resolution:
        format_str = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]"
    else:
        format_str = "bestvideo+bestaudio/best"

    ydl_opts = {
        'format': format_str,
        'merge_output_format': merge_format,
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download YouTube videos with resolution, format, and output options."
    )

    parser.add_argument("url", help="The YouTube video URL.")
    parser.add_argument(
        "-r", "--resolution", type=int, default=None,
        help="Maximum video height (e.g., 2160 for 4K, 1080, 720)."
    )
    parser.add_argument(
        "-o", "--output", default="downloads",
        help="Output folder (default: downloads)."
    )
    parser.add_argument(
        "-m", "--merge", default="mp4",
        choices=["mp4", "mkv", "webm"],
        help="Merge output format (default: mp4)."
    )

    args = parser.parse_args()

    download_video(args.url, args.resolution, args.output, args.merge)
