"""
Main extraction pipeline with retry logic
"""
import json
import os
import time
import sys
import logging
import re
from typing import List, Optional, Dict
from groq import Groq
from dotenv import load_dotenv

from schemas import ShipmentExtraction, LLMExtraction
from port_matcher import PortMatcher
from utils import NumericProcessor, DangerousGoodsDetector
from prompts import PromptVersion, get_prompt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiShipmentHandler:
    """Handle emails with multiple shipments (semicolon-separated)"""
    
    @staticmethod
    def detect_multiple_shipments(body: str) -> bool:
        """Check if email contains multiple shipments"""
        return ';' in body and '→' in body
    
    @staticmethod
    def should_aggregate(shipments: List[dict], port_matcher) -> bool:
        """
        Check if all shipments go to same country (should aggregate)
        Returns True if all destinations are in India or all origins are in India
        """
        dest_codes = [s.get('destination_code') for s in shipments if s.get('destination_code')]
        origin_codes = [s.get('origin_code') for s in shipments if s.get('origin_code')]
        
        # All destinations in India
        all_dest_india = all(code and code.startswith('IN') for code in dest_codes) if dest_codes else False
        
        # All origins in India  
        all_origin_india = all(code and code.startswith('IN') for code in origin_codes) if origin_codes else False
        
        return all_dest_india or all_origin_india
    
    @staticmethod
    def parse_shipments(body: str, port_matcher) -> List[dict]:
        """Parse multiple shipments from body"""
        # Pattern: PORT→PORT value; PORT→PORT value
        shipment_pattern = r'([A-Z]{2,5})\s*→\s*([A-Z\s]{2,20}(?:ICD)?)\s*([0-9.,]+\s*(?:cbm|kg|KGS|CBM|RT|MT)?)?'
        
        matches = re.findall(shipment_pattern, body, re.IGNORECASE)
        
        shipments = []
        for origin_text, dest_text, cargo_text in matches:
            origin_match = port_matcher.match_port(origin_text.strip())
            dest_match = port_matcher.match_port(dest_text.strip())
            
            shipments.append({
                'origin_code': origin_match['code'] if origin_match else None,
                'origin_name': origin_match['name'] if origin_match else None,
                'destination_code': dest_match['code'] if dest_match else None,
                'destination_name': dest_match['name'] if dest_match else None,
                'cargo_text': cargo_text.strip() if cargo_text else None
            })
        
        return shipments
    
    @staticmethod
    def aggregate_shipments(shipments: List[dict]) -> dict:
        """Aggregate multiple shipments into combined ports"""
        # Collect unique origin and destination codes/names
        origin_codes = list(dict.fromkeys([s['origin_code'] for s in shipments if s.get('origin_code')]))
        origin_names = list(dict.fromkeys([s['origin_name'] for s in shipments if s.get('origin_name')]))
        dest_codes = list(dict.fromkeys([s['destination_code'] for s in shipments if s.get('destination_code')]))
        dest_names = list(dict.fromkeys([s['destination_name'] for s in shipments if s.get('destination_name')]))
        
        # Use first code, combined names with slashes
        result = {
            'origin_port_code': origin_codes[0] if origin_codes else None,
            'origin_port_name': ' / '.join(origin_names) if origin_names else None,
            'destination_port_code': dest_codes[0] if dest_codes else None,
            'destination_port_name': ' / '.join(dest_names) if dest_names else None,
        }
        
        # Extract weight and CBM from cargo texts
        all_cargo = [s.get('cargo_text', '') for s in shipments if s.get('cargo_text')]
        
        # Find first CBM value
        for cargo in all_cargo:
            if cargo and 'cbm' in cargo.lower():
                result['cargo_cbm_text'] = cargo
                break
        
        # Find first weight value (kg, RT, MT)
        for cargo in all_cargo:
            if cargo and any(unit in cargo.lower() for unit in ['kg', 'rt', 'mt']):
                result['cargo_weight_text'] = cargo
                break
        
        return result


class EmailExtractor:
    """Main extraction pipeline"""
    
    def __init__(self, api_key: str, port_reference: str, prompt_version: PromptVersion):
        logger.info("Initializing EmailExtractor...")
        self.client = Groq(api_key=api_key)
        self.port_matcher = PortMatcher(port_reference)
        self.prompt_version = prompt_version
        self.max_retries = 3
        self.base_delay = 1
        logger.info(f"Using prompt version: {prompt_version.value}")
    
    def extract_single(self, email: dict) -> ShipmentExtraction:
        """Extract with retry and validation"""
        email_id = email['id']
        try:
            logger.debug(f"Calling LLM for {email_id}")
            llm_output = self._call_llm_with_retry(email)
            
            logger.debug(f"Post-processing {email_id}")
            processed = self._post_process(llm_output, email_id, email)
            
            logger.debug(f"Validating {email_id}")
            result = ShipmentExtraction(**processed)
            
            logger.info(f"✓ Successfully extracted {email_id}")
            return result
            
        except Exception as e:
            logger.error(f"✗ Error extracting {email_id}: {e}", exc_info=True)
            return self._create_null_extraction(email_id)
    
    def _call_llm_with_retry(self, email: dict) -> dict:
        """Call LLM with exponential backoff"""
        prompt = get_prompt(self.prompt_version, email)
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                return json.loads(content)
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {delay}s: {str(e)[:100]}")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed after {self.max_retries} attempts")
                    raise
    
    def _post_process(self, llm_output: dict, email_id: str, email: dict) -> dict:
        """Apply business rules and port matching"""
        
        logger.debug(f"LLM output for {email_id}: {llm_output}")
        
        # Check for multiple shipments
        if MultiShipmentHandler.detect_multiple_shipments(email.get('body', '')):
            logger.info(f"{email_id}: Detected multiple shipments")
            shipments = MultiShipmentHandler.parse_shipments(email['body'], self.port_matcher)
            
            if shipments and MultiShipmentHandler.should_aggregate(shipments, self.port_matcher):
                logger.info(f"{email_id}: Aggregating {len(shipments)} shipments")
                aggregated = MultiShipmentHandler.aggregate_shipments(shipments)
                
                # Use aggregated ports
                origin_match = {
                    'code': aggregated.get('origin_port_code'),
                    'name': aggregated.get('origin_port_name')
                } if aggregated.get('origin_port_code') else None
                
                dest_match = {
                    'code': aggregated.get('destination_port_code'),
                    'name': aggregated.get('destination_port_name')
                } if aggregated.get('destination_port_code') else None
                
                # Update LLM output with aggregated cargo values
                if 'cargo_cbm_text' in aggregated:
                    llm_output['cargo_cbm_text'] = aggregated['cargo_cbm_text']
                if 'cargo_weight_text' in aggregated:
                    llm_output['cargo_weight_text'] = aggregated['cargo_weight_text']
            else:
                # Use first shipment (normal flow)
                origin_match = self.port_matcher.match_port(llm_output.get('origin_port'))
                dest_match = self.port_matcher.match_port(llm_output.get('destination_port'))
        else:
            # Normal single shipment matching
            origin_match = self.port_matcher.match_port(llm_output.get('origin_port'))
            dest_match = self.port_matcher.match_port(llm_output.get('destination_port'))
        
        logger.debug(f"Port matching - Origin: {origin_match}, Dest: {dest_match}")
        
        # Determine product line
        is_import = False
        is_export = False
        
        if dest_match and dest_match.get('code') and dest_match['code'].startswith('IN'):
            is_import = True
        elif origin_match and origin_match.get('code') and origin_match['code'].startswith('IN'):
            is_export = True
        else:
            llm_import = llm_output.get('is_import_to_india', False)
            llm_export = llm_output.get('is_export_from_india', False)
            
            if llm_export:
                is_export = True
            elif llm_import:
                is_import = True
            else:
                is_import = True
        
        product_line = "pl_sea_import_lcl" if is_import else "pl_sea_export_lcl"
        logger.debug(f"Product line: {product_line}")
        
        # Process numeric fields
        weight = NumericProcessor.process_weight(llm_output.get('cargo_weight_text'))
        cbm = NumericProcessor.process_cbm(llm_output.get('cargo_cbm_text'))
        
        # Process dangerous goods
        dg_mentioned = llm_output.get('dangerous_goods_mentioned', 'NOT_MENTIONED')
        if dg_mentioned == 'YES':
            is_dangerous = True
        elif dg_mentioned == 'NO':
            is_dangerous = False
        else:
            full_text = f"{email.get('subject', '')} {email.get('body', '')}"
            is_dangerous = DangerousGoodsDetector.detect(full_text)
        
        # Process incoterm
        incoterm = llm_output.get('incoterm')
        if not incoterm or str(incoterm).lower() in ['null', 'none', '', 'not mentioned']:
            incoterm = 'FOB'
        else:
            incoterm = str(incoterm).upper().strip()
            valid_incoterms = ['FOB', 'CIF', 'CFR', 'EXW', 'DDP', 'DAP', 'FCA', 'CPT', 'CIP', 'DPU']
            if incoterm not in valid_incoterms:
                incoterm = 'FOB'
        
        return {
            'id': email_id,
            'product_line': product_line,
            'origin_port_code': origin_match['code'] if origin_match and origin_match.get('code') else None,
            'origin_port_name': origin_match['name'] if origin_match and origin_match.get('name') else None,
            'destination_port_code': dest_match['code'] if dest_match and dest_match.get('code') else None,
            'destination_port_name': dest_match['name'] if dest_match and dest_match.get('name') else None,
            'incoterm': incoterm,
            'cargo_weight_kg': weight,
            'cargo_cbm': cbm,
            'is_dangerous': is_dangerous
        }
    
    def _create_null_extraction(self, email_id: str) -> ShipmentExtraction:
        """Create null extraction for failed cases"""
        logger.warning(f"Creating null extraction for {email_id}")
        return ShipmentExtraction(
            id=email_id,
            product_line="pl_sea_import_lcl",
            origin_port_code=None,
            origin_port_name=None,
            destination_port_code=None,
            destination_port_name=None,
            incoterm="FOB",
            cargo_weight_kg=None,
            cargo_cbm=None,
            is_dangerous=False
        )
    
    def extract_batch(self, emails: List[dict]) -> List[dict]:
        """Extract all emails with rate limiting"""
        results = []
        total = len(emails)
        
        for i, email in enumerate(emails, 1):
            logger.info(f"Processing {i}/{total}: {email['id']}")
            result = self.extract_single(email)
            results.append(result.dict())
            
            # Rate limiting: Wait 2 seconds between requests to avoid 429 errors
            if i < total:
                logger.debug(f"Rate limiting: waiting 2s before next request...")
                time.sleep(2.0)
        
        return results


def main():
    """Main execution"""
    logger.info("="*60)
    logger.info("FREIGHT EXTRACTION SYSTEM - STARTING")
    logger.info("="*60)
    
    try:
        # Load environment
        logger.info("Loading environment variables...")
        load_dotenv()
        
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in .env file")
        logger.info(f"API key loaded: {api_key[:15]}...")
        
        # Load emails
        logger.info("Loading input emails...")
        with open('emails_input.json', 'r', encoding='utf-8') as f:
            emails = json.load(f)
        logger.info(f"Loaded {len(emails)} emails for extraction")
        
        # Initialize extractor
        logger.info("Initializing extractor...")
        extractor = EmailExtractor(
            api_key=api_key,
            port_reference='port_codes_reference.json',
            prompt_version=PromptVersion.V4
        )
        
        # Extract
        logger.info("Starting batch extraction...")
        results = extractor.extract_batch(emails)
        logger.info(f"Extraction complete. Processed {len(results)} emails")
        
        # CRITICAL: Save results
        logger.info("Saving results to output.json...")
        with open('output.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Results saved successfully")
        
        logger.info("="*60)
        logger.info("SUCCESS - Extraction complete!")
        logger.info(f"Output: output.json ({len(results)} records)")
        logger.info("Next: Run 'python evaluate.py' to check accuracy")
        logger.info("="*60)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        logger.error("Required files: emails_input.json, port_codes_reference.json, .env")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()