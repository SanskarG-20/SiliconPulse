import google.generativeai as genai
from app.settings import settings
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.available_models = []
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            # Initialize model discovery
            self._discover_models()
        else:
            logger.warning("Gemini API Key not configured.")

    def _discover_models(self):
        """
        Dynamically find all available models that support generateContent,
        sorted by preference.
        """
        try:
            all_models = []
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    all_models.append(m.name)
            
            logger.info(f"All available Gemini models: {all_models}")
            
            # Priority list
            preferred_order = [
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
                "models/gemini-1.0-pro",
                "models/gemini-pro"
            ]
            
            # 1. Add preferred models if they exist
            self.available_models = []
            for preferred in preferred_order:
                if preferred in all_models:
                    self.available_models.append(preferred)
            
            # 2. Add any other models not in preferred list (as backup)
            for m in all_models:
                if m not in self.available_models:
                    self.available_models.append(m)
            
            if not self.available_models:
                logger.error("No models found supporting generateContent.")
            else:
                logger.info(f"Gemini models ready for use: {self.available_models}")
                
        except Exception as e:
            logger.error(f"Failed to discover models: {e}")
            # Fallback to settings default
            self.available_models = [settings.gemini_model]

    @retry(
        stop=stop_after_attempt(2), # Reduce retries to avoid wasting quota
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _generate_with_timeout(self, model_name: str, prompt: str, timeout: int = 10) -> str:
        """
        Generate content with strict timeout and retries.
        """
        model = genai.GenerativeModel(model_name)
        # Use async generation
        response = await asyncio.wait_for(
            model.generate_content_async(prompt),
            timeout=timeout
        )
        return response.text

    async def generate_content_with_fallback(self, prompt: str) -> str:
        """
        Generate content using available models, falling back if one is rate limited.
        """
        if not self.available_models:
            return "Insight generation unavailable: No Gemini models found."

        errors = []
        
        for model_name in self.available_models:
            try:
                logger.info(f"Attempting generation with model: {model_name}")
                return await self._generate_with_timeout(model_name, prompt)
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Model {model_name} failed: {error_str}")
                
                # Check for Rate Limit (429)
                if "429" in error_str or "Quota exceeded" in error_str:
                    logger.warning(f"Rate limit hit for {model_name}, trying next model...")
                    errors.append(f"{model_name}: Rate Limit")
                    continue # Try next model
                
                # For other errors, we might also want to try next model, 
                # but let's be conservative and try next only if it seems like a model-specific issue
                errors.append(f"{model_name}: {error_str}")
                continue

        # If we get here, all models failed
        logger.error(f"All Gemini models failed. Errors: {'; '.join(errors)}")
        return "Insight generation unavailable. Please try again later."

    def list_available_models(self) -> list[dict]:
        """List available models and their methods."""
        try:
            models = []
            for m in genai.list_models():
                models.append({
                    "name": m.name,
                    "supported_generation_methods": m.supported_generation_methods
                })
            return models
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def check_health(self) -> dict:
        """Check API key validity and model availability."""
        status = {
            "api_key_configured": bool(settings.gemini_api_key),
            "available_models": self.available_models,
            "generation_test": "skipped"
        }
        
        if settings.gemini_api_key and self.available_models:
            try:
                # Try with first model
                model_name = self.available_models[0]
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async("Hello", generation_config={"max_output_tokens": 5})
                status["generation_test"] = "success"
                status["test_response"] = response.text
                status["tested_model"] = model_name
            except Exception as e:
                status["generation_test"] = "failed"
                status["error"] = str(e)
                
        return status

gemini_client = GeminiClient()
