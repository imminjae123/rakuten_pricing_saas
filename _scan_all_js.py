import httpx, re

# explorer ページの全 script src を取得して全 JS ファイルをスキャン
page = httpx.get("https://webservice.rakuten.co.jp/explorer/api/IchibaItem/Search", timeout=10.0)

# script src を全部抽出
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', page.text)
print("Found scripts:")
for s in scripts:
    print(" ", s)

print()

# 各 JS ファイルをダウンロードして openapi / accessKey / fetch / ajax を探す
for src in scripts:
    if src.startswith("/"):
        src = "https://webservice.rakuten.co.jp" + src
    if not src.startswith("http"):
        continue
    try:
        r = httpx.get(src, timeout=10.0)
        content = r.text

        hits = []
        for pat in [
            r"openapi\.rakuten[^\s\"'<]{5,100}",
            r"accessKey[^;,\n\"']{5,80}",
            r"(?:fetch|axios|ajax)\([^)]{5,150}",
        ]:
            found = re.findall(pat, content)
            hits.extend(found[:3])

        if hits:
            print(f"=== {src} ===")
            for h in hits:
                print(" ", repr(h[:120]))
            print()
    except Exception as e:
        print(f"  skip {src}: {e}")
