# llm/groq_client.py
"""
Groq API client with rate limiting and error handling.
Centralized LLM interaction with retry logic.
"""
import time
from typing import Dict, Optional
from groq import Groq
from config.settings import settings
from utils.logger import setup_logger
from utils.validators import Validator
from groq import RateLimitError, APIError

logger = setup_logger(__name__)


class GroqClient:
    """
    Wrapper around Groq API with built-in safeguards.
    Handles rate limiting, retries, and JSON parsing.
    """
    
    def __init__(self):
        """Initialize Groq client with API key from settings"""
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.last_call_time = 0
        self.call_delay = settings.GROQ_CALL_DELAY
        
        logger.info("GroqClient initialized")
    
    def _rate_limit(self) -> None:
        """
        Enforce rate limiting between API calls.
        Prevents hitting Groq free tier limits.
        """
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.call_delay:
            sleep_time = self.call_delay - time_since_last_call
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
    
    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> str:
        """
        Send completion request to Groq.
        
        Args:
            prompt: Input prompt text
            model: Model name (defaults to reasoning model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Completion text
        
        Raises:
            Exception: If API call fails
        """
        estimated_tokens = len(prompt) // 4
        
        # 2. Dynamic Rate Limiting (TPM Smoothing)
        # If payload is large, force a longer cooldown to respect TPM
        if estimated_tokens > 2000:
            logger.debug(f"Large payload ({estimated_tokens} tokens). Enforcing TPM cooldown.")
            time.sleep(5) # Dynamic wait
        else:
            self._rate_limit()
        
        model = model or settings.GROQ_REASONING_MODEL
        
        try:
            logger.debug(f"Calling Groq API with model: {model}")
            logger.debug(f"Prompt length: {len(prompt)} chars")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise AI assistant. Follow instructions exactly. Output valid JSON when requested."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            
            logger.debug(f"Received response: {len(result)} chars")
            return result
            
        except RateLimitError:
            logger.warning("Groq Rate Limit hit (429).")
            time.sleep(10) # Heavy penalty sleep
            raise # Let logic layer decide to retry
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise Exception(f"LLM API call failed: {str(e)}")
    
    def complete_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Dict:
        """
        Send completion request expecting JSON response.
        
        Args:
            prompt: Input prompt text
            model: Model name (defaults to reasoning model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Parsed JSON as dictionary
        
        Raises:
            Exception: If parsing fails after retries
        """
        response_text = self.complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        parsed = Validator.safe_parse_json(response_text)
        
        if parsed is None:
            # RETRY ONCE
            logger.warning("JSON parsing failed. Retrying...")
            response_text = self.complete(f"Fix this invalid JSON: {response_text}")
            parsed = Validator.safe_parse_json(response_text)
            
            if parsed is None:
                # NOW return fallback
                return {"raw_response": response_text, "parsing_failed": True}
        
        return parsed
    
    def complete_fast(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> str:
        """
        Fast completion using speed model.
        
        Args:
            prompt: Input prompt text
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Completion text
        """
        return self.complete(
            prompt=prompt,
            model=settings.GROQ_SPEED_MODEL,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def complete_reasoning(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> str:
        """
        Deep reasoning completion using 70B model.
        
        Args:
            prompt: Input prompt text
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Completion text
        """
        return self.complete(
            prompt=prompt,
            model=settings.GROQ_REASONING_MODEL,
            temperature=temperature,
            max_tokens=max_tokens
        )