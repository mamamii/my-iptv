import os
import re
import sys
import threading

import requests

from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeoutError
)

THREADS = 64

HTTP_TIMEOUT = (3, 5)

TIME_BUDGET = 450

MIN_VALID_CHANNELS = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SOURCES = {
    "大陆": "https://iptv-org.github.io/iptv/countries/cn.m3u",
    "香港": "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "澳门": "https://iptv-org.github.io/iptv/countries/mo.m3u",
    "台湾": "https://iptv-org.github.io/iptv/countries/tw.m3u"
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cleaned.m3u"
)

_thread_local = threading.local()


def session():

    s = getattr(
        _thread_local,
        "session",
        None
    )

    if s is None:

        s = requests.Session()
        s.headers.update(HEADERS)

        adapter = HTTPAdapter(
            pool_connections=8,
            pool_maxsize=8
        )

        s.mount("http://", adapter)
        s.mount("https://", adapter)

        _thread_local.session = s

    return s


def normalize(name):

    name = re.sub(r"\s+", "", name)

    for x in [
        "HD",
        "hd",
        "4K",
        "4k",
        "高清",
        "超清"
    ]:
        name = name.replace(x, "")

    return name


def fetch_text(url, timeout=HTTP_TIMEOUT):

    try:

        r = session().get(
            url,
            timeout=timeout
        )

        if r.status_code != 200:
            return None

        r.encoding = "utf-8"

        return r.text

    except requests.RequestException:

        return None


def test_hls_stream(url, depth=0):

    if depth > 2:
        return False

    playlist = fetch_text(url)

    if not playlist:
        return False

    if "#EXTM3U" not in playlist:
        return False

    segment = None

    for line in playlist.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        segment = line
        break

    if not segment:
        return False

    segment_url = urljoin(
        url,
        segment
    )

    if segment_url.lower().endswith(".m3u8"):
        return test_hls_stream(
            segment_url,
            depth + 1
        )

    try:

        with session().get(
            segment_url,
            timeout=HTTP_TIMEOUT,
            stream=True
        ) as r:

            if r.status_code != 200:
                return False

            content = next(
                r.iter_content(
                    chunk_size=188 * 20
                ),
                b""
            )

        if len(content) < 3000:
            return False

        return True

    except requests.RequestException:

        return False


def detect(channel):

    region, info, url = channel

    if test_hls_stream(url):

        return (
            region,
            info,
            url
        )

    return None


channels = []

# 跨地区去重：同一频道只保留在最先出现的地区（有意为之）
seen = set()

for region, source in SOURCES.items():

    print("加载:", region)

    text = fetch_text(
        source,
        timeout=30
    )

    if not text:
        continue

    lines = text.splitlines()

    for i in range(len(lines)):

        if not lines[i].startswith("#EXTINF"):
            continue

        if i + 1 >= len(lines):
            continue

        info = lines[i].strip()
        url = lines[i + 1].strip()

        if not url.startswith("http"):
            continue

        name = info.split(",")[-1]

        key = normalize(name)

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        channels.append(
            (
                region,
                info,
                url
            )
        )

print("待检测:", len(channels))

valid = {
    "大陆": [],
    "香港": [],
    "澳门": [],
    "台湾": []
}

pool = ThreadPoolExecutor(max_workers=THREADS)

futures = [
    pool.submit(
        detect,
        ch
    )
    for ch in channels
]

finished = 0

try:

    for future in as_completed(
        futures,
        timeout=TIME_BUDGET
    ):

        finished += 1

        if finished % 100 == 0:
            print(
                "已检测:",
                finished
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

            valid[region].append(
                (
                    info,
                    url
                )
            )

except FuturesTimeoutError:

    print(
        "达到时间预算，未完成的检测跳过"
    )

for future in futures:

    future.cancel()

pool.shutdown(wait=False)

print(
    "检测完成:",
    finished,
    "/",
    len(futures)
)

m3u = ["#EXTM3U"]

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

    valid[region].sort()

    for info, url in valid[region]:

        m3u.append(info)
        m3u.append(url)

total = sum(len(v) for v in valid.values())

if total < MIN_VALID_CHANNELS:

    print(
        "有效频道过少，疑似检测异常，放弃写入:",
        total
    )

    sys.exit(1)

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8",
    newline="\n"
) as f:

    f.write("\n".join(m3u) + "\n")

print(
    "有效频道:",
    total
)
