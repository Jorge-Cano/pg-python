import json
import sys
import requests
from requests.exceptions import HTTPError, Timeout, RequestException

def fetch_data_from_api(url: str, params: dict = None, headers: dict = None) -> dict:
    """
    Fetches JSON data from a third-party REST API with robust error handling.
    
    :param url: The API endpoint URL.
    :param params: Optional dictionary of query parameters.
    :param headers: Optional dictionary of request headers (e.g., API keys, Authorization).
    :return: The parsed JSON response as a dictionary, or None if the request failed.
    """
    # Set a reasonable timeout (connect, read) in seconds
    timeout_seconds = 10

    try:
        # Route status messages to stderr so they don't break the jq pipe
        print(f"Fetching data from: {url}...", file=sys.stderr)
        response = requests.get(url, params=params, headers=headers, timeout=timeout_seconds)
        
        # Raise an exception for HTTP error codes (4xx and 5xx)
        response.raise_for_status()
        
        # Parse and return the JSON response
        data = response.json()
        return data

    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} (Status code: {response.status_code})", file=sys.stderr)
    except Timeout:
        print(f"The request timed out after {timeout_seconds} seconds.", file=sys.stderr)
    except RequestException as err:
        print(f"An error occurred during the request: {err}", file=sys.stderr)
    except ValueError:
        print("Failed to parse response as JSON.", file=sys.stderr)
        
    return None

if __name__ == "__main__":
    # Example using JSONPlaceholder (a free fake online REST API for testing)
    API_URL = "https://jsonplaceholder.typicode.com/posts/1"
    
    # Optional: Add headers if your third-party service requires authentication
    # HEADERS = {"Authorization": "Bearer YOUR_API_KEY_HERE"}
    
    result = fetch_data_from_api(API_URL)
    
    if result:
        # json.dumps ensures strict JSON output so | jq can parse it cleanly
        print(json.dumps(result, indent=4))