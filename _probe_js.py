import httpx, re

r = httpx.get("https://webservice.rakuten.co.jp/js/app.10022026.js", timeout=10.0)
print("JS file size:", len(r.text))

patterns = [
    r"openapi\.rakuten\.co\.jp[^\s\"']{0,100}",
    r"accessKey[^\n]{0,150}",
    r"[Rr]eferer[^\n]{0,100}",
    r"proxy[^\n]{0,150}",
]
for pat in patterns:
    hits = list(dict.fromkeys(re.findall(pat, r.text)))[:4]
    for h in hits:
        print(repr(h[:130]))
    print()
