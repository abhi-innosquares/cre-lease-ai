"""
CRE Lease Abstraction AI
Extracts structured lease data from raw lease document text using AI.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
import os

from src.utils.currency import enrich_structured_data_with_currency


class LeaseExtractor:
    """Main class for extracting structured data from lease documents."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the lease extractor.
        
        Args:
            api_key: OpenAI API key (optional, will use OPENAI_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            print("Warning: No OpenAI API key provided. Using rule-based extraction only.")
            self.use_ai = False
        else:
            self.use_ai = True
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                print("Warning: openai package not installed. Using rule-based extraction only.")
                self.use_ai = False
    
    def get_schema(self) -> Dict[str, Any]:
        """Returns the expected JSON schema structure."""
        return {
            "leaseIdentification": {
                "leaseId": None,
                "leaseExecutionDate": None,
                "leaseType": None
            },
            "parties": {
                "landlordName": None,
                "tenantName": None,
                "parentTenantId": None,
                "guarantorName": None,
                "isGuaranteed": False
            },
            "premises": {
                "propertyId": None,
                "market": None,
                "propertyAddress": None,
                "premisesDescription": None,
                "rentableSquareFeet": None
            },
            "leaseTerm": {
                "commencementDate": None,
                "expirationDate": None,
                "rentCommencementDate": None
            },
            "financialTerms": {
                "baseRentSchedule": [],
                "annualBaseRent": None,
                "currency": None,
                "normalizedAnnualBaseRent": None,
                "normalizedCurrency": None,
                "rentEscalationType": None,
                "securityDeposit": None,
                "proRataShare": None,
                "tenantImprovementAllowance": None,
                "operatingExpensePassThrough": None
            },
            "options": {
                "hasRenewalOption": False,
                "renewalNoticePeriodDays": None,
                "renewalRentBasis": None,
                "hasTerminationOption": False,
                "terminationNoticePeriodDays": None
            },
            "riskFlags": {
                "coTenancyClause": False,
                "exclusiveUseClause": False,
                "sndaInPlace": False
            },
            "confidenceScore": 0
        }
    
    def extract_with_ai(self, lease_text: str) -> Dict[str, Any]:
        """
        Extract lease data using OpenAI GPT model.
        
        Args:
            lease_text: Raw lease document text
            
        Returns:
            Structured lease data dictionary
        """
        schema = self.get_schema()
        
        prompt = f"""You are an expert Commercial Real Estate (CRE) Lease Abstraction AI.

Your job is to extract structured lease data from raw lease document text.

You MUST:
- Return valid JSON only
- Follow the exact schema provided
- Do not hallucinate missing values
- If data is not found, return null
- Infer leaseType and operatingExpensePassThrough logically
- Convert textual numbers to numeric values
- Normalize dates to ISO format (YYYY-MM-DD)
- Convert rent expressed as $/SF/year into total annual and monthly rent
- Capture rent currency using ISO currency codes such as USD, INR, or CNY
- Parse conditional clauses but flag if ambiguous
- Extract renewal and termination options carefully

Expected JSON Schema:
{json.dumps(schema, indent=2)}

Lease Type Definitions:
- Full Service: Landlord pays all operating expenses
- Modified Gross: Some expenses passed to tenant
- Triple Net (NNN): Tenant pays taxes, insurance, CAM
- Absolute NNN: Tenant pays everything including structural

Operating Expense PassThrough Types:
- NNN: Tenant pays proportionate share of all operating expenses
- Base Year: Expenses over base year passed to tenant
- Expense Stop: Expenses over fixed cap passed to tenant
- Gross: No pass-through

Extract the following lease attributes from the document text below.

Document Text:
---------------------
{lease_text}
---------------------

Return ONLY valid JSON matching the schema above. Do not include any explanatory text."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional lease abstraction AI. You return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error using AI extraction: {e}")
            return self.extract_with_rules(lease_text)
    
    def extract_with_rules(self, lease_text: str) -> Dict[str, Any]:
        """
        Fallback rule-based extraction when AI is not available.
        
        Args:
            lease_text: Raw lease document text
            
        Returns:
            Structured lease data dictionary
        """
        result = self.get_schema()
        text = lease_text.upper()
        
        # Basic pattern matching for key terms
        # Parties
        landlord_match = re.search(r'LANDLORD[:\s]+([A-Z\s\.,&]+?)(?:TENANT|ADDRESS|\n)', lease_text, re.IGNORECASE)
        if landlord_match:
            result['parties']['landlordName'] = landlord_match.group(1).strip()
        
        tenant_match = re.search(r'TENANT[:\s]+([A-Z\s\.,&]+?)(?:LANDLORD|ADDRESS|\n)', lease_text, re.IGNORECASE)
        if tenant_match:
            result['parties']['tenantName'] = tenant_match.group(1).strip()
        
        # Check for guarantor
        if re.search(r'GUARANTOR|GUARANTEE', text):
            result['parties']['isGuaranteed'] = True
            guarantor_match = re.search(r'GUARANTOR[:\s]+([A-Z\s\.,&]+?)(?:\n|,)', lease_text, re.IGNORECASE)
            if guarantor_match:
                result['parties']['guarantorName'] = guarantor_match.group(1).strip()
        
        # Square footage
        sf_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*(?:RENTABLE\s*)?(?:SQUARE\s*)?(?:FEET|SF|SQ\.?\s*FT)', text)
        if sf_match:
            result['premises']['rentableSquareFeet'] = int(sf_match.group(1).replace(',', ''))
        
        # Dates (looking for common patterns)
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
            r'(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2}),?\s+(\d{4})'
        ]
        
        # Security deposit
        deposit_match = re.search(r'SECURITY\s+DEPOSIT[:\s]+\$?\s*([\d,]+)', text)
        if deposit_match:
            result['financialTerms']['securityDeposit'] = float(deposit_match.group(1).replace(',', ''))
        
        # Lease type inference
        if 'TRIPLE NET' in text or 'NNN' in text:
            result['leaseIdentification']['leaseType'] = 'Triple Net'
            result['financialTerms']['operatingExpensePassThrough'] = 'NNN'
        elif 'FULL SERVICE' in text:
            result['leaseIdentification']['leaseType'] = 'Full Service'
            result['financialTerms']['operatingExpensePassThrough'] = 'Gross'
        elif 'MODIFIED GROSS' in text:
            result['leaseIdentification']['leaseType'] = 'Modified Gross'
        
        # Renewal option
        if re.search(r'RENEWAL\s+OPTION|OPTION\s+TO\s+RENEW', text):
            result['options']['hasRenewalOption'] = True
            
            # Extract notice period
            notice_match = re.search(r'(\d+)\s*DAYS?\s+(?:PRIOR\s+)?NOTICE|NOTICE\s+OF\s+(\d+)\s*DAYS?', text)
            if notice_match:
                days = notice_match.group(1) or notice_match.group(2)
                result['options']['renewalNoticePeriodDays'] = int(days)
        
        # Termination option
        if re.search(r'TERMINATION\s+OPTION|EARLY\s+TERMINATION|RIGHT\s+TO\s+TERMINATE', text):
            result['options']['hasTerminationOption'] = True
        
        # Risk flags
        result['riskFlags']['coTenancyClause'] = bool(re.search(r'CO-?TENANCY', text))
        result['riskFlags']['exclusiveUseClause'] = bool(re.search(r'EXCLUSIVE\s+USE|EXCLUSIVITY', text))
        result['riskFlags']['sndaInPlace'] = bool(re.search(r'SNDA|SUBORDINATION.*NON-?DISTURBANCE', text))
        
        # Confidence score (lower for rule-based)
        result['confidenceScore'] = 40
        
        return result
    
    def extract(self, lease_text: str) -> Dict[str, Any]:
        """
        Main extraction method that routes to AI or rule-based extraction.
        
        Args:
            lease_text: Raw lease document text
            
        Returns:
            Structured lease data dictionary in JSON format
        """
        if not lease_text or not lease_text.strip():
            raise ValueError("Lease text cannot be empty")
        
        if self.use_ai:
            result = self.extract_with_ai(lease_text)
        else:
            result = self.extract_with_rules(lease_text)

        return enrich_structured_data_with_currency(result, lease_text)
    
    def extract_to_json(self, lease_text: str, pretty: bool = True) -> str:
        """
        Extract lease data and return as JSON string.
        
        Args:
            lease_text: Raw lease document text
            pretty: Whether to format JSON with indentation
            
        Returns:
            JSON string
        """
        result = self.extract(lease_text)
        if pretty:
            return json.dumps(result, indent=2)
        return json.dumps(result)
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text content from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        try:
            import pdfplumber
            
            text_content = []
            with pdfplumber.open(pdf_path) as pdf:
                print(f"  PDF has {len(pdf.pages)} page(s)")
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text and text.strip():
                        text_content.append(text)
                        print(f"  ✓ Extracted text from page {i} ({len(text)} chars)")
                    else:
                        print(f"  ⚠ Page {i} has no extractable text (may be scanned image)")
            
            if not text_content:
                raise ValueError(
                    "No text could be extracted from PDF. "
                    "The PDF may contain scanned images rather than text. "
                    "Consider using OCR tools to convert images to text first."
                )
            
            extracted_text = "\n\n".join(text_content)
            print(f"  Total extracted: {len(extracted_text)} characters")
            return extracted_text
            
        except ImportError:
            print("Warning: pdfplumber not installed. Trying PyPDF2...")
            try:
                from PyPDF2 import PdfReader
                
                reader = PdfReader(pdf_path)
                text_content = []
                
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                
                return "\n\n".join(text_content)
                
            except ImportError:
                raise ImportError(
                    "PDF support requires either pdfplumber or PyPDF2. "
                    "Install with: pip install pdfplumber PyPDF2"
                )
    
    def extract_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Extract lease data from a text or PDF file.
        
        Args:
            file_path: Path to lease document file (.txt or .pdf)
            
        Returns:
            Structured lease data dictionary
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            print(f"Extracting text from PDF: {os.path.basename(file_path)}")
            lease_text = self.extract_text_from_pdf(file_path)
        elif file_extension in ['.txt', '.text']:
            with open(file_path, 'r', encoding='utf-8') as f:
                lease_text = f.read()
        else:
            # Try to read as text file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lease_text = f.read()
            except:
                raise ValueError(
                    f"Unsupported file type: {file_extension}. "
                    "Supported formats: .txt, .pdf"
                )
        
        return self.extract(lease_text)


def main():
    """Example usage of the LeaseExtractor."""
    import sys
    
    # Example usage
    if len(sys.argv) > 1:
        # Extract from file
        file_path = sys.argv[1]
        extractor = LeaseExtractor()
        result = extractor.extract_from_file(file_path)
        print(json.dumps(result, indent=2))
    else:
        # Example with sample text
        sample_lease = """
        COMMERCIAL LEASE AGREEMENT
        
        This Lease Agreement is entered into on January 15, 2024
        
        LANDLORD: ABC Properties LLC
        TENANT: XYZ Corporation
        
        PREMISES: 1234 Main Street, Suite 500, Chicago, IL 60601
        Rentable Square Feet: 5,000 SF
        
        TERM: 
        Commencement Date: February 1, 2024
        Expiration Date: January 31, 2029
        
        BASE RENT:
        Years 1-2: $25.00 per square foot per year ($125,000 annually, $10,416.67 monthly)
        Years 3-5: $27.50 per square foot per year ($137,500 annually, $11,458.33 monthly)
        
        SECURITY DEPOSIT: $20,000
        
        LEASE TYPE: Triple Net (NNN) - Tenant is responsible for all operating expenses, 
        taxes, insurance, and common area maintenance.
        
        RENEWAL OPTION: Tenant has one (1) option to renew for an additional five (5) year term.
        Tenant must provide 180 days prior written notice.
        Renewal rent to be determined at Fair Market Value.
        
        The Tenant's proportionate share is 12.5% of the building.
        """
        
        extractor = LeaseExtractor()
        result = extractor.extract(sample_lease)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
