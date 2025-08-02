import requests
import json
import pydantic
from .response import GudidResponse
from .models import Item

def call_api(udi=None, headers=None):
    """
    Makes a GET request to the specified API URL.
    
    Args:
        udi: string id for device lookup.
        headers (dict, optional): HTTP headers for the request.
        
    Returns:
        dict: JSON response from the API if successful.
        None: If the request fails.
    """
    url = "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json"
    params = {"udi": udi}
    if udi == None:
        return None
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()
    except requests.RequestException as e:
        return None

#Create an item object from an UDI ID
def create_item_from_id(udi):
    if udi == None:
        return None
    response = call_api(udi,)
    response_string = json.dumps(response)
    gudid_parsed = GudidResponse.model_validate_json(response_string)
    #TODO: check if item exists before adding it
    item_info = {
            "item": gudid_parsed.productCodes[0].deviceName,
            "item_no": gudid_parsed.gudid.device.identifiers.identifier[0].deviceId,
            "mfr": gudid_parsed.gudid.device.companyName,
            "mfr_cat": gudid_parsed.gudid.device.versionModelNumber,
            "descr": gudid_parsed.gudid.device.deviceDescription,
            "par_level": 1,
            "external_url": "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json?udi=" + udi,
        }
    
    item_instance, flag = Item.objects.get_or_create(item_no=item_info["item"], defaults=item_info)