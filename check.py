import os
import re
import sys
import threading
import time

import requests

from urllib.parse import (
    urljoin,
    urlsplit
)
from requests.adapters import HTTPAdapter
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeoutError
)

THREADS = 64

# (连接超时, 读取超时)
HTTP_TIMEOUT = (4, 6)

# 补救轮使用的更宽松超时
RESCUE_TIMEOUT = (6, 12)

PER_CHANNEL_BUDGET = 20

TIME_BUDGET = 450

# 补救轮时间预算
RESCUE_BUDGET = 240

MIN_VALID_CHANNELS = 10

# 分片有效数据最小字节数
MIN_SEGMENT_BYTES = 1000

sys.stdout.reconfigure(
    line_buffering=True
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# 候选源列表：(地区, 订阅地址)
# 同一地区可配置多个源，靠前的源在去重时优先保留
SOURCES = [
    ("大陆", "https://iptv-org.github.io/iptv/countries/cn.m3u"),
    ("大陆", "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/index.m3u"),
    ("香港", "https://iptv-org.github.io/iptv/countries/hk.m3u"),
    ("澳门", "https://iptv-org.github.io/iptv/countries/mo.m3u"),
    ("台湾", "https://iptv-org.github.io/iptv/countries/tw.m3u")
]

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


def test_hls_stream(
    url,
    depth=0,
    deadline=None,
    relaxed=False
):

    timeout = (
        RESCUE_TIMEOUT
        if relaxed
        else HTTP_TIMEOUT
    )

    if deadline is None:

        budget = (
            PER_CHANNEL_BUDGET * 2
            if relaxed
            else PER_CHANNEL_BUDGET
        )

        deadline = (
            time.monotonic()
            + budget
        )

    if depth > 2:
        return False

    if time.monotonic() > deadline:
        return False

    playlist = fetch_text(
        url,
        timeout=timeout
    )

    if playlist is None and depth == 0:

        # 网络抖动重试一次，减少误杀
        time.sleep(0.2)

        playlist = fetch_text(
            url,
            timeout=timeout
        )

    if not playlist:
        return False

    if "#EXTM3U" not in playlist:
        return False

    is_master = (
        "#EXT-X-STREAM-INF"
        in playlist
    )

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

    path = urlsplit(
        segment_url
    ).path.lower()

    if (
        is_master
        or path.endswith(".m3u8")
    ):
        return test_hls_stream(
            segment_url,
            depth + 1,
            deadline,
            relaxed
        )

    try:

        with session().get(
            segment_url,
            timeout=timeout,
            stream=True
        ) as r:

            if r.status_code != 200:
                return False

            content = b""

            for chunk in r.iter_content(
                chunk_size=188 * 20
            ):

                content += chunk

                if len(content) >= 3000:
                    break

        if b"#EXTM3U" in content[:200]:
            return test_hls_stream(
                segment_url,
                depth + 1,
                deadline,
                relaxed
            )

        is_ts = (
            content[:1] == b"G"
        )

        is_fmp4 = (
            content[4:8] == b"ftyp"
        )

        if not (is_ts or is_fmp4):
            return False

        if len(content) < MIN_SEGMENT_BYTES:
            return False

        return True

    except requests.RequestException:

        return False


def detect(channel, relaxed=False):

    region, info, url = channel

    if test_hls_stream(
        url,
        relaxed=relaxed
    ):

        return (
            region,
            info,
            url
        )

    return None


def detect_all(items, budget, relaxed):

    results = {}

    if not items:
        return results

    pool = ThreadPoolExecutor(
        max_workers=THREADS
    )

    futures = {
        pool.submit(
            detect,
            ch,
            relaxed
        ): ch
        for ch in items
    }

    finished = 0

    try:

        for future in as_completed(
            futures,
            timeout=budget
        ):

            finished += 1

            if finished % 100 == 0:
                print(
                    "已检测:",
                    finished
                )

            results[
                futures[future]
            ] = future.result()

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

    return results


channels = []

# 跨地区去重：同一频道只保留在最先出现的地区（有意为之）
seen = set()

for region, source in SOURCES:

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

first = detect_all(
    channels,
    TIME_BUDGET,
    relaxed=False
)

failed = [
    ch for ch in channels
    if not first.get(ch)
]

# 补救轮：放宽超时重测失败频道，
# 死链会快速失败，慢速有效频道被捞回
if failed:

    print(
        "补救检测:",
        len(failed)
    )

    second = detect_all(
        failed,
        RESCUE_BUDGET,
        relaxed=True
    )

    for ch, result in second.items():

        if result:
            first[ch] = result

for ch in channels:

    result = first.get(ch)

    if not result:
        continue

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

    sys.stdout.flush()

    os._exit(1)

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

sys.stdout.flush()

os._exit(0)
