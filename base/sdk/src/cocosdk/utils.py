import logging
import requests
import json

logger = logging.getLogger(__name__)


def call_api(
    url, endpoint, method="GET", headers=None, data=None, files=None, timeout=100
):
    # Modular function to call API endpoints with logging, error handling, and timeout
    full_url = f"{url}{endpoint}"

    try:
        logger.info(f"Calling {method} endpoint: {full_url}")
        response = requests.request(
            method, full_url, headers=headers, data=data, files=files, timeout=timeout
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        try:
            json_response = response.json()
            print(f"Response from {full_url}: {json_response}")  # Print the response
            return json_response
        except json.JSONDecodeError:
            logger.error(
                f"Invalid JSON response from {full_url}: Response Content: {response.text}"
            )
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling {full_url}: {e}")
        if hasattr(e, "response") and e.response:
            try:
                logger.error(f"Response: {e.response.text}")
            except Exception as e_in:
                logger.error(f"Could not print error message {e_in}")
        return None
