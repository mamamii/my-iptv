import requests

SOURCE="https://iptv-org.github.io/iptv/countries/cn.m3u"

text=requests.get(SOURCE,timeout=30).text

lines=text.splitlines()

result=["#EXTM3U"]

for i in range(len(lines)):
    if lines[i].startswith("#EXTINF"):
        if i+1>=len(lines):
            continue

        url=lines[i+1]

        try:
            r=requests.get(
                url,
                timeout=8,
                stream=True,
                headers={
                    "User-Agent":"Mozilla/5.0"
                }
            )

            if r.status_code == 200:
                result.append(lines[i])
                result.append(url)
                print("OK:",url)

        except:
            pass

open("cleaned.m3u","w",encoding="utf-8").write(
    "\n".join(result)
)
