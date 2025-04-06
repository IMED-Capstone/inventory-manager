import requests
import json
import pydantic
from device import GudidResponse

def call_api(url, params=None, headers=None):
    """
    Makes a GET request to the specified API URL.
    
    Args:
        url (str): The API endpoint URL.
        params (dict, optional): Query parameters for the request.
        headers (dict, optional): HTTP headers for the request.
        
    Returns:
        dict: JSON response from the API if successful.
        None: If the request fails.
    """
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()
    except requests.RequestException as e:
        print(f"API call failed: {e}")
        return None

def main():
    url = "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json"
    params = {"di": "08717648200274"}
    response = call_api(url, params=params,)
    response_string = json.dumps(response)
    gudid_parsed = GudidResponse.model_validate_json(response_string)
    print(gudid_parsed.productCodes[0].deviceName)
    

if __name__ == "__main__":
    main()