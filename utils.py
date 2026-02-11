# utils.py
"""
Utility functions for numeric processing and DG detection
"""
import re
from typing import Optional


class NumericProcessor:
    """Process weight and CBM fields"""
    
    @staticmethod
    def extract_number(text: str) -> Optional[float]:
        """Extract number, handling commas and various formats"""
        if not text:
            return None
        
        # Remove extra spaces
        text = text.strip()
        
        # Pattern to match numbers with optional commas and decimals
        pattern = r'([\d,]+\.?\d*)'
        match = re.search(pattern, text)
        if match:
            number_str = match.group(1).replace(',', '')
            try:
                return float(number_str)
            except:
                return None
        return None
    
    @staticmethod
    def extract_unit(text: str) -> str:
        """Detect unit: kg, lbs, tonnes, MT, RT"""
        if not text:
            return 'kg'
        
        text_lower = text.lower()
        
        # Check for different unit patterns
        if 'lb' in text_lower or 'pound' in text_lower:
            return 'lbs'
        elif 'ton' in text_lower or 'mt' in text_lower or 'rt' in text_lower:
            return 'tonnes'
        
        return 'kg'
    
    @staticmethod
    def convert_to_kg(value: float, unit: str) -> float:
        """Convert to kg based on unit"""
        conversions = {
            'kg': 1.0,
            'kgs': 1.0,
            'lbs': 0.453592,
            'pounds': 0.453592,
            'tonnes': 1000.0,
            'ton': 1000.0,
            'mt': 1000.0,
            'rt': 1000.0,  # Revenue Ton
        }
        return value * conversions.get(unit.lower(), 1.0)
    
    @staticmethod
    def is_dimensions(text: str) -> bool:
        """Check if text contains dimensions (L×W×H)"""
        if not text:
            return False
        # Pattern: 100x50x30 or 100 x 50 x 30 or 100×50×30
        dimension_pattern = r'\d+\s*[xX×]\s*\d+\s*[xX×]\s*\d+'
        return bool(re.search(dimension_pattern, text))
    
    @staticmethod
    def process_weight(weight_text: Optional[str]) -> Optional[float]:
        """Process weight with unit conversion"""
        if not weight_text:
            return None
        
        text_upper = weight_text.upper().strip()
        
        # Check for TBD/N/A
        if text_upper in ['TBD', 'N/A', 'NA', 'TO BE CONFIRMED', 'TBC', 'PENDING']:
            return None
        
        # Extract number
        number = NumericProcessor.extract_number(weight_text)
        if number is None:
            return None
        
        # Handle explicit zero
        if number == 0:
            return 0.0
        
        # Extract unit and convert
        unit = NumericProcessor.extract_unit(weight_text)
        weight_kg = NumericProcessor.convert_to_kg(number, unit)
        
        # Validate non-negative
        if weight_kg < 0:
            return None
        
        return round(weight_kg, 2)
    
    @staticmethod
    def process_cbm(cbm_text: Optional[str]) -> Optional[float]:
        """Process CBM volume"""
        if not cbm_text:
            return None
        
        text_upper = cbm_text.upper().strip()
        
        # Check for TBD/N/A
        if text_upper in ['TBD', 'N/A', 'NA', 'TO BE CONFIRMED', 'TBC', 'PENDING']:
            return None
        
        # Check if dimensions (don't calculate from dimensions)
        if NumericProcessor.is_dimensions(cbm_text):
            return None
        
        # Extract number
        number = NumericProcessor.extract_number(cbm_text)
        if number is None:
            return None
        
        # Handle explicit zero
        if number == 0:
            return 0.0
        
        # Validate non-negative
        if number < 0:
            return None
        
        return round(number, 2)


class DangerousGoodsDetector:
    """Detect dangerous goods with negation handling"""
    
    # CRITICAL: Check negations FIRST
    NEGATION_PATTERNS = [
        r'\bnon[-\s]?dg\b',
        r'\bnon[-\s]?hazardous\b',
        r'\bnot\s+dangerous\b',
        r'\bnon\s+dangerous\b',
        r'\bnon[-\s]?dangerous\b',
        r'\bnon\s+hazmat\b',
    ]
    
    POSITIVE_PATTERNS = [
        r'\b(dg|d\.g\.)\b',
        r'\bdangerous\b',
        r'\bhazardous\b',
        r'\bhazmat\b',
        r'\bclass\s*[0-9]\b',
        r'\bimo\b',
        r'\bimdg\b',
        r'\bun\s*[0-9]{4}\b',
        r'\bflammable\b',
    ]
    
    @classmethod
    def detect(cls, text: str) -> bool:
        """Returns True if dangerous goods detected"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Step 1: Check negations FIRST (highest priority)
        for pattern in cls.NEGATION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return False
        
        # Step 2: Check positive mentions
        for pattern in cls.POSITIVE_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # Step 3: Default to False
        return False