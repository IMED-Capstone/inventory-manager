from typing import Optional, List
from pydantic import BaseModel, model_validator


class NullToEmptyStrModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def replace_null_strings(cls, data):
        if isinstance(data, dict):
            for k, v in data.items():
                field = cls.model_fields.get(k)
                if field and field.annotation is str and v is None:
                    data[k] = ""
        return data

class Identifier(NullToEmptyStrModel):
    deviceId: Optional[str] = ""
    deviceIdType: Optional[str] = ""
    deviceIdIssuingAgency: Optional[str] = ""
    containsDINumber: Optional[str] = ""
    pkgQuantity: Optional[int] = None
    pkgDiscontinueDate: Optional[str] = ""
    pkgStatus: Optional[str] = ""
    pkgType: Optional[str] = ""


class Identifiers(NullToEmptyStrModel):
    identifier: Optional[List[Identifier]]


class CustomerContact(NullToEmptyStrModel):
    phone: Optional[str] = ""
    phoneExtension: Optional[str] = ""
    email: Optional[str] = ""


class Contacts(NullToEmptyStrModel):
    customerContact: Optional[List[CustomerContact]]


class Gmdn(NullToEmptyStrModel):
    gmdnCode: Optional[str] = ""
    gmdnPTName: Optional[str] = ""
    gmdnPTDefinition: Optional[str] = ""
    implantable: Optional[bool] = None
    gmdnCodeStatus: Optional[str] = ""


class GmdnTerms(NullToEmptyStrModel):
    gmdn: Optional[List[Gmdn]]


class ProductCode(NullToEmptyStrModel):
    productCode: Optional[str] = ""
    productCodeName: Optional[str] = ""


class ProductCodes(NullToEmptyStrModel):
    fdaProductCode: Optional[List[ProductCode]]


class Size(NullToEmptyStrModel):
    unit: Optional[str] = ""
    value: Optional[str] = ""

class DeviceSize(NullToEmptyStrModel):
    sizeType: Optional[str] = ""
    size: Size
    sizeText: Optional[str] = ""
    sizeString: Optional[str] = ""

class DeviceSizes(NullToEmptyStrModel):
    deviceSize: Optional[List[DeviceSize]]


class StorageHandlingLimit(NullToEmptyStrModel):
    unit: Optional[str] = ""
    value: Optional[str] = ""


class StorageHandling(NullToEmptyStrModel):
    storageHandlingType: Optional[str] = ""
    storageHandlingHigh: StorageHandlingLimit
    storageHandlingLow: StorageHandlingLimit
    storageHandlingSpecialConditionText: Optional[str] = ""

class EnvironmentalConditions(NullToEmptyStrModel):
    storageHandling: Optional[List[StorageHandling]]


class Sterilization(NullToEmptyStrModel):
    deviceSterile: Optional[bool] = None
    sterilizationPriorToUse: Optional[bool] = None
    methodTypes: Optional[str] = ""


class Device(NullToEmptyStrModel):
    publicDeviceRecordKey: Optional[str] = ""
    publicVersionStatus: Optional[str] = ""
    deviceRecordStatus: Optional[str] = ""
    publicVersionNumber: Optional[int] = None
    publicVersionDate: Optional[str] = ""
    devicePublishDate: Optional[str] = ""
    deviceCommDistributionEndDate: Optional[str] = ""
    deviceCommDistributionStatus: Optional[str] = ""
    identifiers: Identifiers
    brandName: Optional[str] = ""
    versionModelNumber: Optional[str] = ""
    catalogNumber: Optional[str] = ""
    dunsNumber: Optional[str] = ""
    companyName: Optional[str] = ""
    deviceCount: Optional[int] = None
    deviceDescription: Optional[str] = ""
    DMExempt: Optional[bool] = None
    premarketExempt: Optional[bool] = None
    deviceHCTP: Optional[bool] = None
    deviceKit: Optional[bool] = None
    deviceCombinationProduct: Optional[bool] = None
    singleUse: Optional[bool] = None
    lotBatch: Optional[bool] = None
    serialNumber: Optional[bool] = None
    manufacturingDate: Optional[bool] = None
    expirationDate: Optional[bool] = None
    donationIdNumber: Optional[bool] = None
    labeledContainsNRL: Optional[bool] = None
    labeledNoNRL: Optional[bool] = None
    MRISafetyStatus: Optional[str] = ""
    rx: Optional[bool] = None
    otc: Optional[bool] = None
    contacts: Optional[Contacts]
    gmdnTerms: Optional[GmdnTerms]
    productCodes: Optional[ProductCodes]
    deviceSizes: Optional[DeviceSizes]
    environmentalConditions: Optional[EnvironmentalConditions]
    sterilization: Optional[Sterilization]


class GudidDevice(NullToEmptyStrModel):
    device: Device


class ProductCodeEntry(NullToEmptyStrModel):
    productCode: Optional[str] = ""
    physicalState: Optional[str] = ""
    deviceClass: Optional[str] = ""
    thirdPartyFlag: Optional[str] = ""
    definition: Optional[str] = ""
    submissionTypeID: Optional[str] = ""
    reviewPanel: Optional[str] = ""
    gmpExemptFlag: Optional[str] = ""
    technicalMethod: Optional[str] = ""
    reviewCode: Optional[str] = ""
    lifeSustainSupportFlag: Optional[str] = ""
    unclassifiedReason: Optional[str] = ""
    implantFlag: Optional[str] = ""
    targetArea: Optional[str] = ""
    regulationNumber: Optional[str] = ""
    deviceName: Optional[str] = ""
    medicalSpecialty: Optional[str] = ""


class GudidResponse(NullToEmptyStrModel):
    gudid: GudidDevice
    productCodes: Optional[List[ProductCodeEntry]]