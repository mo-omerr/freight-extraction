# schemas.py
"""
Pydantic schemas for shipment extraction with validation
"""
from typing import Optional, Literal
from pydantic import BaseModel, validator, Field


class ShipmentExtraction(BaseModel):
    """Final validated shipment extraction matching output schema"""
    
    id: str
    product_line: Literal["pl_sea_import_lcl", "pl_sea_export_lcl"]
    origin_port_code: Optional[str] = None
    origin_port_name: Optional[str] = None
    destination_port_code: Optional[str] = None
    destination_port_name: Optional[str] = None
    incoterm: str = "FOB"
    cargo_weight_kg: Optional[float] = None
    cargo_cbm: Optional[float] = None
    is_dangerous: bool = False
    
    @validator('cargo_weight_kg', 'cargo_cbm')
    def round_and_validate_numeric(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError("Must be non-negative")
            return round(v, 2)
        return None
    
    @validator('origin_port_code', 'destination_port_code')
    def validate_port_code(cls, v):
        if v is not None:
            if not (len(v) == 5 and v.isupper() and v.isalpha()):
                raise ValueError(f"Invalid port code format: {v}")
        return v
    
    @validator('incoterm')
    def normalize_incoterm(cls, v):
        if not v:
            return 'FOB'
        v_upper = str(v).upper().strip()
        valid = ['FOB', 'CIF', 'CFR', 'EXW', 'DDP', 'DAP', 'FCA', 'CPT', 'CIP', 'DPU']
        if v_upper in valid:
            return v_upper
        return 'FOB'
    
    class Config:
        validate_assignment = True


class LLMExtraction(BaseModel):
    """Raw extraction from LLM before post-processing"""
    
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    incoterm: Optional[str] = None
    cargo_weight_text: Optional[str] = None
    cargo_cbm_text: Optional[str] = None
    dangerous_goods_mentioned: Optional[str] = None
    is_import_to_india: Optional[bool] = None
    is_export_from_india: Optional[bool] = None