"""
Multi-strategy port code matching system with name variation support
"""
import json
from typing import Optional, Dict, List
import re


class PortMatcher:
    """Multi-level port matching with fuzzy fallback and name variation support"""
    
    def __init__(self, reference_file: str):
        with open(reference_file, 'r', encoding='utf-8') as f:
            self.reference_data = json.load(f)
        
        self.code_to_canonical = {}
        self.name_to_code = {}
        self.abbrev_to_code = {}
        self.code_to_all_names = {}
        self.name_to_entry = {}  # Store full entry for each name
        
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build comprehensive lookup tables"""
        
        for entry in self.reference_data:
            code = entry['code']
            name = entry['name']
            name_key = name.lower().strip()
            
            # Canonical name (first occurrence for this code)
            if code not in self.code_to_canonical:
                self.code_to_canonical[code] = name
            
            # All name variations to code (case-insensitive)
            self.name_to_code[name_key] = code
            
            # Store full entry for name-based lookup
            self.name_to_entry[name_key] = entry
            
            # Track all names for fuzzy matching
            if code not in self.code_to_all_names:
                self.code_to_all_names[code] = []
            self.code_to_all_names[code].append(name_key)
        
        # Build abbreviation map
        self._build_abbreviation_map()
    
    def _build_abbreviation_map(self):
        """Build common abbreviations"""
        
        # Manual common abbreviations - comprehensive list
        manual = {
            'SHA': 'CNSHA',
            'MAA': 'INMAA',
            'HK': 'HKHKG',
            'SIN': 'SGSIN',
            'BLR': 'INBLR',
            'BOM': 'INNSA',
            'DEL': 'INMAA',
            'TXG': 'CNTXG',
            'BKK': 'THBKK',
            'SUB': 'IDSUB',
            'JED': 'SAJED',
            'DAM': 'SAJED',
            'RUH': 'SAJED',
            'HYD': 'INMAA',
            'GOA': 'ITGOA',
            'HAM': 'DEHAM',
            'MNL': 'PHMNL',
            'OSA': 'JPOSA',
            'YOK': 'JPYOK',
            'PUS': 'KRPUS',
            'KEL': 'TWKEL',
            'HOU': 'USHOU',
            'LAX': 'USLAX',
            'SGN': 'VNSGN',
            'CPT': 'ZACPT',
            'LCH': 'THLCH',
            'AMR': 'TRAMR',
            'IZM': 'TRIZM',
            'PKG': 'MYPKG',
            'GZG': 'CNGZG',
            'NSA': 'CNNSA',
            'QIN': 'CNQIN',
            'SZX': 'CNSZX',
            'JEA': 'AEJEA',
            'DAC': 'BDDAC',
            'MUN': 'INMUN',
            'WFD': 'INWFD',
            'JAPAN': 'JPUKB',
            'JPN': 'JPUKB',
        }
        
        # Auto-extract from port codes (last 3 letters)
        for code in self.code_to_canonical.keys():
            abbrev = code[-3:]
            if abbrev not in self.abbrev_to_code:
                self.abbrev_to_code[abbrev] = code
        
        # Manual overrides (more specific)
        self.abbrev_to_code.update(manual)
    
    def match_port(self, text: Optional[str]) -> Optional[Dict[str, str]]:
        """
        Multi-strategy matching, returns best matching name variation
        
        Returns: {"code": "INMAA", "name": "Chennai ICD"} or None
        """
        if not text:
            return None
        
        text_clean = text.strip()
        text_lower = text_clean.lower()
        text_upper = text_clean.upper()
        
        # Strategy 1: Exact code match (5 letter codes)
        if len(text_clean) == 5 and text_upper.isalpha() and text_upper in self.code_to_canonical:
            return {
                "code": text_upper,
                "name": self.code_to_canonical[text_upper]
            }
        
        # Strategy 2: Exact name match (case-insensitive) - return the matched variation
        if text_lower in self.name_to_code:
            entry = self.name_to_entry[text_lower]
            return {
                "code": entry['code'],
                "name": entry['name']  # Return the actual matched name variation
            }
        
        # Strategy 3: Abbreviation match (2-4 letter codes)
        if 2 <= len(text_upper) <= 4 and text_upper.isalpha() and text_upper in self.abbrev_to_code:
            code = self.abbrev_to_code[text_upper]
            # For abbreviations, try to find best matching name variation
            best_name = self._find_best_name_for_abbreviation(text_upper, code)
            return {
                "code": code,
                "name": best_name
            }
        
        # Strategy 4: Fuzzy match
        fuzzy = self._fuzzy_match(text_lower, text_clean)
        if fuzzy:
            return fuzzy
        
        return None
    
    def _find_best_name_for_abbreviation(self, abbrev: str, code: str) -> str:
        """Find best matching name variation for an abbreviation"""
        # For abbreviations like MAA, prefer variations with "ICD" if available
        all_names = self.code_to_all_names.get(code, [])
        
        # Check if there's a name with ICD
        icd_names = [n for n in all_names if 'icd' in n]
        if icd_names and abbrev in ['MAA', 'BLR', 'HYD']:
            # Find the simplest ICD variation
            for name_lower in all_names:
                if name_lower == f'{self._get_city_from_abbrev(abbrev).lower()} icd':
                    entry = self.name_to_entry.get(name_lower)
                    if entry:
                        return entry['name']
        
        # Default to canonical
        return self.code_to_canonical[code]
    
    def _get_city_from_abbrev(self, abbrev: str) -> str:
        """Get city name from abbreviation"""
        city_map = {
            'MAA': 'Chennai',
            'BLR': 'Bangalore',
            'HYD': 'Hyderabad',
            'BOM': 'Mumbai',
        }
        return city_map.get(abbrev, '')
    
    def _fuzzy_match(self, text: str, original_text: str) -> Optional[Dict[str, str]]:
        """Fuzzy matching for port names, returns best matching variation"""
        
        # Remove common prefixes/suffixes
        text_clean = text.replace('icd', '').replace('port', '').strip()
        
        # Exact substring matching - return the matched variation
        for code, all_names in self.code_to_all_names.items():
            for name in all_names:
                name_clean = name.replace('icd', '').replace('port', '').strip()
                if name_clean in text_clean or text_clean in name_clean:
                    # Return the actual matched name variation
                    entry = self.name_to_entry.get(name)
                    if entry:
                        return {
                            "code": code,
                            "name": entry['name']
                        }
        
        # Word-level matching with priority scoring
        text_words = set(text.split())
        best_match = None
        best_score = 0
        best_name = None
        
        for code, all_names in self.code_to_all_names.items():
            for name in all_names:
                name_words = set(name.split())
                overlap = text_words & name_words
                score = len(overlap)
                
                if score > best_score:
                    best_score = score
                    entry = self.name_to_entry.get(name)
                    if entry:
                        best_match = code
                        best_name = entry['name']
        
        if best_match:
            return {
                "code": best_match,
                "name": best_name
            }
        
        return None