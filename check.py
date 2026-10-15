import requests
import subprocess
import json
import time
from pathlib import Path

SOURCE = "https://iptv-org.github.io/iptv/countries/cn.m3u"

TIMEOUT = 15

KEEP = []

keep_file = Path("stable_channels.txt")

if keep_file.exists():
    KEEP = [
        line.strip()
        for line in keep_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def probe_stream(url):

    try:

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-of", "json",
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )

        if not result.stdout:
            return False

        data = json.loads(result.stdout)

        streams = data.get("streams", [])

        for s in streams:

            if s.get("codec_type") == "video":
                return True

        return False

    except Exception:
        return False


print("下载源...")

text = requests.get(
    SOURCE,
    timeout=30,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
).text

lines = text.splitlines()

clean = ["#EXTM3U"]

total = 0
success = 0

for i in range(len(lines)):

    if not lines[i].startswith("#EXTINF"):
        continue

    if i + 1 >= len(lines):
        continue

    info = lines[i]
    url = lines[i + 1]

    total += 1

    print(f"[{total}] 检测: {info}")

    ok = probe_stream(url)

    if ok:

        success += 1

        clean.append(info)
        clean.append(url)

        print("✅ 通过")

    else:

        print("❌ 失效")

    time.sleep(0.5)

Path("cleaned.m3u").write_text(
    "\n".join(clean),
    encoding="utf-8"
)

print()
print(f"总检测: {total}")
print(f"有效: {success}")
