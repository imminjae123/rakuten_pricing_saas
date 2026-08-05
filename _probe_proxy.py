import httpx, json

# 楽天WSの explorer/proxy エンドポイントに実際のリクエストを送って
# どんなパラメータ・ヘッダーが必要か確認する
new_app_id     = "5ef7ed3e-071a-48c5-8032-548e5a17fa0a"
new_access_key = "pk_t5440Y2QsTaieCJPkAExYUHNOuaNw85vrP0GXekSezp"

proxy_url = "https://webservice.rakuten.co.jp/explorer/proxy"

# proxy エンドポイントへ POST (APIエクスプローラーが使うパターン)
payload = {
    "applicationId": new_app_id,
    "accessKey":     new_access_key,
    "api":           "IchibaItem/Search",
    "version":       "20260701",
    "keyword":       "Nintendo Switch",
    "hits":          "3",
    "formatVersion": "2",
}

r_post = httpx.post(proxy_url, json=payload, timeout=10.0)
print("POST proxy:", r_post.status_code)
print(r_post.text[:400])
print()

# GET でも試す
r_get = httpx.get(proxy_url, params=payload, timeout=10.0)
print("GET proxy:", r_get.status_code)
print(r_get.text[:400])
