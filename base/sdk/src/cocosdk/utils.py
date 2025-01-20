import requests


def call_api(
    url, endpoint, method="GET", headers=None, data=None, files=None, timeout=100
):
    full_url = f"{url}{endpoint}"
    response = requests.request(
        method=method,
        url=full_url,
        headers=headers,
        data=data,
        files=files,
        timeout=timeout,
    )
    response.raise_for_status()
    json_response = response.json()
    return json_response
