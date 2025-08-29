import requests
import json
import pydantic
from .response import GudidResponse
from .models import Device, Item

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

#Add an item object from an UDI ID
def add_item_from_udi(udi, quantity):
    if udi == None:
        return None
    udi_input = udi
    if (udi_input[0] == "\\" and udi_input[-1] == "\\"):
                    udi_input = udi_input[1:-1]
    response = call_api(udi_input,)
    if response is None:
        return None
    response_string = json.dumps(response)
    gudid_parsed = GudidResponse.model_validate_json(response_string)
    #Check if device exists, if not, create a new device with the corresponding DI, otherwise store the existing device into a variable to be used for item creation
    device_info = {
            "device_identifier": gudid_parsed.udi.di
    }
    parsed_di = gudid_parsed.udi.di
    device_instance, device_flag = Device.objects.get_or_create(device_identifier=parsed_di, defaults=device_info)

    #Create a new item for the UDI that was scanned in
    item_info = {
            "item": gudid_parsed.productCodes[0].deviceName,
            "item_no": gudid_parsed.udi.udi,
            "mfr": gudid_parsed.gudid.device.companyName,
            "mfr_cat": gudid_parsed.gudid.device.versionModelNumber,
            "descr": gudid_parsed.gudid.device.deviceDescription,
            "par_level": 1,
            "device": device_instance,
            "current_count": 1,
            "external_url": "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json?udi=" + udi,
        }
    
    item_instance, item_flag = Item.objects.get_or_create(item_no=item_info["item"], defaults=item_info)
    #If an item already existed, add to the device current count
    item_instance.increase_count(quantity)
    return item_instance

#Remove an item object from an UDI ID
def remove_item_from_udi(udi, quantity):
    if udi == None:
        return None
    udi_input = udi
    if (udi_input[0] == "\\" and udi_input[-1] == "\\"):
                    udi_input = udi_input[1:-1]
    item_instance = Item.objects.filter(item=udi_input)[0]
    item_instance.decrease_count(quantity)
    return item_instance