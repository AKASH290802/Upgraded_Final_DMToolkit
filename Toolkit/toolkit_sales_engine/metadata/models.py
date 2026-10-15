"""
Pydantic models for the Metadata Registry.
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    PICKLIST = "picklist"
    REFERENCE = "reference"
    CURRENCY = "currency"
    PERCENT = "percent"
    UNKNOWN = "unknown"


SF_TYPE_MAP: dict[str, DataType] = {
    "string":        DataType.STRING,
    "textarea":      DataType.STRING,
    "id":            DataType.STRING,
    "int":           DataType.INTEGER,
    "integer":       DataType.INTEGER,
    "double":        DataType.FLOAT,
    "currency":      DataType.CURRENCY,
    "percent":       DataType.PERCENT,
    "boolean":       DataType.BOOLEAN,
    "date":          DataType.DATE,
    "datetime":      DataType.DATETIME,
    "email":         DataType.EMAIL,
    "phone":         DataType.PHONE,
    "url":           DataType.URL,
    "picklist":      DataType.PICKLIST,
    "multipicklist": DataType.PICKLIST,
    "reference":     DataType.REFERENCE,
}


class FieldMeta(BaseModel):
    object_name: str = Field(..., description="API name of the Salesforce object")
    field_name: str = Field(..., description="API name of the field")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(default="")
    data_type: DataType = Field(...)
    required: bool = Field(default=False)
    max_length: Optional[int] = Field(default=None)
    picklist_values: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    example_values: list[str] = Field(default_factory=list)
    embedding_id: Optional[str] = Field(default=None)
    reference_to: list[str] = Field(default_factory=list,
        description="API name(s) of the object(s) a REFERENCE field points to")

    model_config = {"use_enum_values": True}


class ObjectMeta(BaseModel):
    object_name: str
    label: str
    fields: list[FieldMeta]
