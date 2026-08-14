import datetime
import json

import requests

from .models import Device, Item
from .response import GudidResponse
from .services import normalize_udi

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
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()
    except requests.RequestException as e:
        return None

def get_or_create_item_from_udi(udi):
    """Resolve a UDI to one physical item without changing inventory state."""
    if udi is None:
        return None

    udi_input = normalize_udi(udi)
    existing_item = Item.objects.filter(item_no=udi_input).first()
    if existing_item is not None:
        return existing_item

    response = call_api(udi_input,)
    if response is None:
        return None
    response_string = json.dumps(response)
    gudid_parsed = GudidResponse.model_validate_json(response_string)
    #Check if device exists, if not, create a new device with the corresponding DI, otherwise store the existing device into a variable to be used for item creation
    device_info = {
            "manufacturer": gudid_parsed.gudid.device.companyName,
            "device_name": gudid_parsed.gudid.device.brandName,
            "device_identifier": gudid_parsed.udi.di
    }
    parsed_di = gudid_parsed.udi.di
    device_instance, device_flag = Device.objects.get_or_create(device_identifier=parsed_di, defaults=device_info)

    #Create a new item for the UDI that was scanned in
    #TODO: add customer contact info
    expiration_date = None
    if gudid_parsed.udi.expirationDate:
        expiration_date = datetime.datetime.strptime(
            gudid_parsed.udi.expirationDate, "%Y-%m-%d"
        ).date()
    product_name = (
        gudid_parsed.productCodes[0].deviceName
        if gudid_parsed.productCodes
        else gudid_parsed.gudid.device.brandName
    )
    item_info = {
            "item": product_name,
            "item_no": gudid_parsed.udi.udi,
            "mfr": gudid_parsed.gudid.device.companyName,
            "mfr_cat": gudid_parsed.gudid.device.versionModelNumber,
            "descr": gudid_parsed.gudid.device.deviceDescription,
            "device": device_instance,
            "is_available": False,
            "exp_date": expiration_date,
            "external_url": "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json?udi=" + gudid_parsed.udi.udi,
        }
    
    item_instance, item_flag = Item.objects.get_or_create(
        item_no=item_info["item_no"], defaults=item_info
    )
    return item_instance
