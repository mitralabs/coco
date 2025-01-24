import httpx


def call_api(
    url, endpoint, method="GET", headers=None, data=None, files=None, timeout=100
):
    """Call the API with the given parameters.

    Args:
        url (str): The URL to call.
        endpoint (str): The endpoint to call.
        method (str, optional): The method to use. Defaults to "GET".
        headers (dict, optional): The headers to send. Defaults to None.
        data (dict, optional): The data to send. Defaults to None.
        files (dict, optional): The files to send. Defaults to None.
        timeout (int, optional): The timeout for the request. Defaults to 100.

    Returns:
        dict: The response json from the API.
    """
    full_url = f"{url}{endpoint}"
    with httpx.Client() as client:
        response = client.request(
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
