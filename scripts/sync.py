import os
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
import boto3
from dateutil import parser
import xml.etree.ElementTree as ET

CHANNEL_URL = "https://www.youtube.com/@Parkergetajob/videos"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

DOWNLOADED_FILE = Path("downloaded.txt")
RSS_FILE = Path("rss.xml")

# Load downloaded IDs
downloaded = set(DOWNLOADED_FILE.read_text().splitlines())

# Run yt-dlp
cmd = [
    "yt-dlp",
    "--extract-audio",
    "--audio-format", "mp3",
    "--output", str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
    "--print", "%(id)s|%(title)s|%(upload_date)s",
    CHANNEL_URL
]

result = subprocess.run(cmd, capture_output=True, text=True)
lines = result.stdout.strip().splitlines()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
)

tree = ET.parse(RSS_FILE)
channel = tree.getroot().find("channel")

now = time.time()
new_ids = []

for line in lines:
    vid, title, upload_date = line.split("|")

    if vid in downloaded:
        continue

    mp3 = DOWNLOAD_DIR / f"{vid}.mp3"
    if not mp3.exists():
        continue

    # Upload to R2
    s3.upload_file(
        str(mp3),
        os.environ["R2_BUCKET"],
        mp3.name,
        ExtraArgs={"ContentType": "audio/mpeg"}
    )

    url = f"{os.environ['R2_PUBLIC_BASE_URL']}/{mp3.name}"

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "enclosure", {
        "url": url,
        "type": "audio/mpeg"
    })

    pub_date = parser.parse(upload_date).replace(tzinfo=timezone.utc)
    ET.SubElement(item, "pubDate").text = pub_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    downloaded.add(vid)
    new_ids.append(vid)

# Save RSS
tree.write(RSS_FILE, encoding="utf-8", xml_declaration=True)

# Save downloaded.txt
DOWNLOADED_FILE.write_text("\n".join(sorted(downloaded)))

# Delete local files older than 5 days
for f in DOWNLOAD_DIR.glob("*.mp3"):
    if now - f.stat().st_mtime > 5 * 86400:
        f.unlink()
