import httpx, re

pages = [
    "https://webservice.rakuten.co.jp/documentation/ichiba-item-search",
    "https://webservice.rakuten.co.jp/documentation",
    "https://webservice.rakuten.co.jp/guide",
    "https://webservice.rakuten.co.jp/",
]
for url in pages:
    r = httpx.get(url, timeout=10.0)
    print(f"--- {url} ({r.status_code}) ---")
    # access_token / bearer / authorization まわりの記述を抜き出す
    hits = re.findall(r"(?:access_token|bearer|authorization|oauth|client_credentials)[^\n<]{0,120}", r.text, re.IGNORECASE)
    for h in list(dict.fromkeys(hits))[:8]:
        print(" ", repr(h.strip()[:120]))
    # また JavaScript 変数やサンプルコードの URL パターンを抜き出す
    urls = re.findall(r"https://[a-zA-Z0-9./_-]{10,80}", r.text)
    api_urls = [u for u in urls if "rakuten" in u and ("api" in u or "token" in u or "oauth" in u)]
    for u in list(dict.fromkeys(api_urls))[:6]:
        print("  URL:", u)
    print()
