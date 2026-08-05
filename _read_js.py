import httpx, re

r = httpx.get("https://webservice.rakuten.co.jp/js/app.10022026.js", timeout=10.0)
print("Content:", r.text)
