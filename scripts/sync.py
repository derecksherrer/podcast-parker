import os
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
import boto3
import xml.etree.ElementTree as ET

CHANNEL_URL = "https://www.youtube.com/@Parkergetajob/videos"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

ARCHIVE_FILE = Path("downloaded.txt")
RSS_FILE = Path("rss.xml")

# Run yt-dlp (only NEW videos)
cmd = [
    "yt-dlp",
    "--extract-audio",
    "--audio-format", "mp3",
    "--download-archive", str(ARCHIVE_FILE),
    "--output", str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
    "--print", "%(id)s|%(title)s|%(upload_date)s",
    CHANNEL_URL
]

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    raise RuntimeError(result.stderr)

lines = result.stdout.strip().splitlines()

if not lines:
    print("No new videos.")
    exit(0)

# Load RSS
tree = ET.parse(RSS_FILE)
channel = tree.getroot().find("channel")

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
)

now = time.time()

for line in lines:
    vid, title, upload_date = line.split("|")
    mp3 = DOWNLOAD_DIR / f"{vid}.mp3"

    if not mp3.exists():
        continue

    # Upload MP3
