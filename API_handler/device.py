from typing import Optional, List
from pydantic import BaseModel


class Identifier(BaseModel):
    deviceId: str
    deviceIdType: str
    deviceIdIssuingAgency: str
    containsDINumber: Optional[str]
    pkgQuantity: Optional[int]
    pkgDiscontinueDate: Optional[str]
    pkgStatus: Optional[str]
    pkgType: Optional[str]


class Identifiers(BaseModel):
    identifier: List[Identifier]


class CustomerContact(BaseModel):
    phone: str
    phoneExtension: Optional[str]
    email: str


class Contacts(BaseModel):
    customerContact: List[CustomerContact]


class Gmdn(BaseModel):
    gmdnCode: str
    gmdnPTName: str
    gmdnPTDefinition: str
    implantable: bool
    gmdnCodeStatus: str


class GmdnTerms(BaseModel):
    gmdn: List[Gmdn]


class ProductCode(BaseModel):
    productCode: str
    productCodeName: str


class ProductCodes(BaseModel):
    fdaProductCode: List[ProductCode]


class StorageHandlingLimit(BaseModel):
    unit: str
    value: str


class StorageHandling(BaseModel):
    storageHandlingType: str
    storageHandlingHigh: StorageHandlingLimit
    storageHandlingLow: StorageHandlingLimit
    storageHandlingSpecialConditionText: Optional[str]


class EnvironmentalConditions(BaseModel):
    storageHandling: List[StorageHandling]


class Sterilization(BaseModel):
    deviceSterile: bool
    sterilizationPriorToUse: bool
    methodTypes: Optional[str]


class Device(BaseModel):
    publicDeviceRecordKey: str
    publicVersionStatus: str
    deviceRecordStatus: str
    publicVersionNumber: int
    publicVersionDate: str
    devicePublishDate: str
    deviceCommDistributionEndDate: Optional[str]
    deviceCommDistributionStatus: str
    identifiers: Identifiers
    brandName: str
    versionModelNumber: str
    catalogNumber: str
    dunsNumber: str
    companyName: str
    deviceCount: int
    deviceDescription: str
    DMExempt: bool
    premarketExempt: bool
    deviceHCTP: bool
    deviceKit: bool
    deviceCombinationProduct: bool
    singleUse: bool
    lotBatch: bool
    serialNumber: bool
    manufacturingDate: bool
    expirationDate: bool
    donationIdNumber: bool
    labeledContainsNRL: bool
    labeledNoNRL: bool
    MRISafetyStatus: str
    rx: bool
    otc: bool
    contacts: Contacts
    gmdnTerms: GmdnTerms
    productCodes: ProductCodes
    deviceSizes: Optional[str]
    environmentalConditions: EnvironmentalConditions
    sterilization: Sterilization


class GudidDevice(BaseModel):
    device: Device


class ProductCodeEntry(BaseModel):
    productCode: str
    physicalState: Optional[str]
    deviceClass: str
    thirdPartyFlag: str
    definition: str
    submissionTypeID: str
    reviewPanel: str
    gmpExemptFlag: str
    technicalMethod: Optional[str]
    reviewCode: Optional[str]
    lifeSustainSupportFlag: str
    unclassifiedReason: Optional[str]
    implantFlag: str
    targetArea: Optional[str]
    regulationNumber: Optional[str]
    deviceName: str
    medicalSpecialty: Optional[str]


class GudidResponse(BaseModel):
    gudid: GudidDevice
    productCodes: List[ProductCodeEntry]