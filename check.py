import requests
import re

from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

THREADS = 32

HTTP_TIMEOUT = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SOURCES = {
    "大陆": "https://iptv-org.github.io/iptv/countries/cn.m3u",
    "香港": "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "澳门": "https://iptv-org.github.io/iptv/countries/mo.m3u",
    "台湾": "https://iptv-org.github.io/iptv/countries/tw.m3u"
}


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


def fetch_text(url):

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        if r.status_code == 200:
            return r.text

    except:
        pass

    return None


def test_hls_stream(url):

    try:

        playlist = fetch_text(url)

        if not playlist:
            return False

        if "#EXTM3U" not in playlist:
            return False

        segment = None

        lines = playlist.splitlines()

        for line in lines:

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

        r = requests.get(
            segment_url,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
            stream=True
        )

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

    except:

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

seen = set()

for region, source in SOURCES.items():

    print("加载:", region)

    try:

        text = requests.get(
            source,
            headers=HEADERS,
            timeout=30
        ).text

    except:
        continue

    lines = text.splitlines()

    for i in range(len(lines)):

        if not lines[i].startswith("#EXTINF"):
            continue

        if i + 1 >= len(lines):
            continue

        info = lines[i].strip()
        url = lines[i + 1].strip()

        name = info.split(",")[-1]

        key = normalize(name)

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

with ThreadPoolExecutor(max_workers=THREADS) as pool:

    futures = [
        pool.submit(
            detect,
            ch
        )
        for ch in channels
    ]

    for future in as_completed(futures):

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

with open(
    "cleaned.m3u",
    "w",
    encoding="utf-8"
) as f:

    f.write("\n".join(m3u))

print(
    "有效频道:",
    sum(len(v) for v in valid.values())
)
