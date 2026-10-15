import requests
import subprocess
import json
import re

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

# ==========================================
# 配置
# ==========================================

THREADS = 32

HTTP_TIMEOUT = 3

FFPROBE_TIMEOUT = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SOURCES = {
    "大陆": "https://iptv-org.github.io/iptv/countries/cn.m3u",
    "香港": "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "澳门": "https://iptv-org.github.io/iptv/countries/mo.m3u",
    "台湾": "https://iptv-org.github.io/iptv/countries/tw.m3u"
}

# ==========================================
# 工具
# ==========================================

def normalize_name(name):

    name = re.sub(r"\s+", "", name)

    for word in [
        "HD",
        "hd",
        "高清",
        "超清",
        "4K",
        "4k"
    ]:
        name = name.replace(word, "")

    return name.strip()


def fast_http_check(url):

    try:

        r = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            stream=True,
            headers=HEADERS,
            allow_redirects=True
        )

        if r.status_code != 200:
            return False

        return True

    except:
        return False


def ffprobe_check(url):

    try:

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT
        )

        if not result.stdout:
            return False

        data = json.loads(result.stdout)

        streams = data.get(
            "streams",
            []
        )

        for stream in streams:

            if (
                stream.get("codec_type")
                == "video"
            ):
                return True

        return False

    except:
        return False


def detect_channel(channel):

    region, info, url = channel

    if not fast_http_check(url):
        return None

    if not ffprobe_check(url):
        return None

    return (
        region,
        info,
        url
    )

# ==========================================
# 收集频道
# ==========================================

channels = []

seen = set()

for region, source in SOURCES.items():

    print(f"\n下载 {region}")

    try:

        text = requests.get(
            source,
            timeout=30,
            headers=HEADERS
        ).text

    except Exception as e:

        print(e)

        continue

    lines = text.splitlines()

    i = 0

    while i < len(lines):

        line = lines[i]

        if (
            line.startswith("#EXTINF")
            and i + 1 < len(lines)
        ):

            info = line.strip()
            url = lines[i + 1].strip()

            name = info.split(",")[-1]

            key = normalize_name(name)

            if key not in seen:

                seen.add(key)

                channels.append(
                    (
                        region,
                        info,
                        url
                    )
                )

        i += 1

print(
    "\n总频道数:",
    len(channels)
)

# ==========================================
# 并发检测
# ==========================================

valid = {
    "大陆": [],
    "香港": [],
    "澳门": [],
    "台湾": []
}

checked = 0

with ThreadPoolExecutor(
    max_workers=THREADS
) as executor:

    futures = [
        executor.submit(
            detect_channel,
            ch
        )
        for ch in channels
    ]

    for future in as_completed(
        futures
    ):

        checked += 1

        if checked % 20 == 0:
            print(
                f"进度 {checked}/{len(channels)}"
            )

        result = future.result()

        if result:

            region, info, url = result

            if 'group-title="' in info:

                info = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{region}"',
                    info
                )

            else:

                info = info.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 group-title="{region}"'
                )

            valid[
                region
            ].append(
                (
                    info,
                    url
                )
            )

# ==========================================
# 排序
# ==========================================

for region in valid:

    valid[region].sort(
        key=lambda x: x[0]
    )

# ==========================================
# 输出M3U
# ==========================================

m3u = [
    "#EXTM3U"
]

for region in [
    "大陆",
    "香港",
    "澳门",
    "台湾"
]:

    m3u.append("")
    m3u.append(
        f"# ===== {region} ====="
    )

    for info, url in valid[region]:

        m3u.append(info)
        m3u.append(url)

with open(
    "cleaned.m3u",
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "\n".join(m3u)
    )

total_valid = sum(
    len(v)
    for v in valid.values()
)

print("\n完成")
print("有效频道:", total_valid)

for region in valid:

    print(
        region,
        len(valid[region])
    )
