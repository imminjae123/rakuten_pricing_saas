import httpx, time

new_app_id     = "5ef7ed3e-071a-48c5-8032-548e5a17fa0a"
new_access_key = "pk_t5440Y2QsTaieCJPkAExYUHNOuaNw85vrP0GXekSezp"
NEW_URL        = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

params = {
    "applicationId": new_app_id,
    "accessKey":     new_access_key,
    "keyword":       "Nintendo Switch",
    "hits":          3,
    "formatVersion": 2,
}

referers = [
    "https://app.rakuten.co.jp",
    "https://app.rakuten.co.jp/",
    "https://webservice.rakuten.co.jp",
    "https://webservice.rakuten.co.jp/",
    "http://localhost/",
    "http://localhost",
]

for ref in referers:
    time.sleep(1)
    r = httpx.get(NEW_URL, params=params, headers={"Referer": ref}, timeout=10.0)
    print(f"Referer={ref!r:45s} -> {r.status_code} | {r.text[:60]}")
