# utils/validators.py
"""
Validation utilities for data integrity checks.
Ensures data conforms to expected formats.
"""
from typing import List, Dict, Any, Optional
import json
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures"""
    pass


class Validator:
    """
    Validation utilities for ensuring data integrity.
    All validation logic centralized here.
    """
    
    @staticmethod
    def validate_json_structure(
        data: Any,
        required_keys: List[str]
    ) -> bool:
        """
        Validate that a dictionary contains required keys.
        
        Args:
            data: Dictionary to validate
            required_keys: List of required key names
        
        Returns:
            True if valid
        
        Raises:
            ValidationError if validation fails
        """
        if not isinstance(data, dict):
            raise ValidationError(f"Expected dict, got {type(data)}")
        
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValidationError(f"Missing required keys: {missing_keys}")
        
        return True
    
    @staticmethod
    def validate_seniority_profile(profile: Dict) -> bool:
        """
        Validate seniority profile structure.
        
        Args:
            profile: Profile dictionary to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError if validation fails
        """
        required_keys = [
            "label",
            "reasoning_focus",
            "autonomy_level",
            "risk_avoidance",
            "vocabulary_shifts",
            "skill_filters"
        ]
        
        Validator.validate_json_structure(profile, required_keys)
        
        if not isinstance(profile["vocabulary_shifts"], dict):
            raise ValidationError("vocabulary_shifts must be a dictionary")
        
        if not isinstance(profile["skill_filters"], dict):
            raise ValidationError("skill_filters must be a dictionary")
        
        return True
    
    @staticmethod
    def validate_section_block(section: Dict) -> bool:
        """
        Validate section block structure.
        
        Args:
            section: Section block to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError if validation fails
        """
        required_keys = [
            "id",
            "original_header",
            "original_content",
            "semantic_tag",
            "status"
        ]
        
        Validator.validate_json_structure(section, required_keys)
        return True
    
    @staticmethod
    def validate_skills_list(skills: List[str]) -> bool:
        """
        Validate skills list format.
        
        Args:
            skills: List of skill strings
        
        Returns:
            True if valid
        
        Raises:
            ValidationError if validation fails
        """
        if not isinstance(skills, list):
            raise ValidationError(f"Skills must be a list, got {type(skills)}")
        
        if not skills:
            raise ValidationError("Skills list cannot be empty")
        
        for skill in skills:
            if not isinstance(skill, str):
                raise ValidationError(f"Each skill must be a string, got {type(skill)}")
            if not skill.strip():
                raise ValidationError("Skills cannot be empty strings")
        
        return True
    
    @staticmethod
    def safe_parse_json(json_string: str) -> Optional[Dict]:
        """
        Safely parse JSON string with error handling.
        
        Args:
            json_string: JSON string to parse
        
        Returns:
            Parsed dictionary or None if parsing fails
        """
        try:
            # Remove markdown code blocks if present
            cleaned = json_string.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Failed JSON string: {json_string[:200]}...")
            return None
    
    @staticmethod
    def validate_pdf_path(file_path: str) -> bool:
        """
        Validate PDF file path.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            True if valid
        
        Raises:
            ValidationError if validation fails
        """
        import os
        
        if not os.path.exists(file_path):
            raise ValidationError(f"File does not exist: {file_path}")
        
        if not file_path.lower().endswith('.pdf'):
            raise ValidationError(f"File is not a PDF: {file_path}")
        
        return True