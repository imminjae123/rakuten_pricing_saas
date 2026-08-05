import httpx, re

r = httpx.get("https://webservice.rakuten.co.jp/js/explorer.min.js", timeout=10.0)
print("Size:", len(r.text))

# openapi / accessKey / Referer / Authorization のまわりを全部抽出
for pat in [
    r"openapi[^\s\"']{5,80}",
    r"accessKey[^;,\n]{5,80}",
    r"[Rr]eferer[^;,\n]{5,80}",
    r"Authorization[^;,\n]{5,80}",
    r"header[^;,\n]{5,100}",
]:
    found = list(dict.fromkeys(re.findall(pat, r.text)))[:5]
    for f in found:
        print(repr(f[:120]))
    if found:
        print()
