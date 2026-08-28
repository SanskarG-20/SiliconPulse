from __future__ import annotations

import asyncio
import logging

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.settings import settings

logger = logging.getLogger(__name__)

# Try new SDK (google-genai), fallback to legacy (google-generativeai)
try:
    from google import genai as genai_new  # type: ignore
    from google.genai import types as genai_types  # type: ignore

    NEW_SDK = True
except ImportError:
    genai_new = None  # type: ignore
    genai_types = None  # type: ignore
    NEW_SDK = False

try:
    import google.generativeai as genai_legacy  # type: ignore

    LEGACY_AVAILABLE = True
except ImportError:
    genai_legacy = None  # type: ignore
    LEGACY_AVAILABLE = False

class GeminiClient:
    def __init__(self):
        self.available_models: list[str] = []
        self.client = None
        if not settings.gemini_api_key:
            logger.warning("Gemini API Key not configured.")
            return

        if NEW_SDK:
            try:
                self.client = genai_new.Client(api_key=settings.gemini_api_key)
                self._discover_models()
            except Exception as exc:
                logger.warning(f"New SDK init failed ({exc}), trying legacy")
                self.client = None
                if LEGACY_AVAILABLE:
                    genai_legacy.configure(api_key=settings.gemini_api_key)
                    self._discover_models()
        elif LEGACY_AVAILABLE:
            genai_legacy.configure(api_key=settings.gemini_api_key)
            self._discover_models()
        else:
            logger.warning("No Gemini SDK available (install google-genai or google-generativeai)")

    def _discover_models(self):
        """
        Dynamically find all available models that support generateContent,
        sorted by preference.
        """
        try:
            all_models: list[str] = []

            if NEW_SDK and self.client is not None:
                # New SDK: client.models.list()
                try:
                    for m in self.client.models.list():
                        # m.name like 'models/gemini-2.0-flash' or 'gemini-2.0-flash'
                        name = getattr(m, "name", str(m))
                        # Filter by supported actions if available
                        actions = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
                        if not actions or "generateContent" in actions or "generate_content" in str(actions):
                            all_models.append(name)
                except Exception as e:
                    logger.warning(f"New SDK list failed: {e}")

            if not all_models and LEGACY_AVAILABLE:
                try:
                    for m in genai_legacy.list_models():
                        if "generateContent" in m.supported_generation_methods:
                            all_models.append(m.name)
                except Exception as e:
                    logger.warning(f"Legacy list failed: {e}")

            # Fallback: if still empty, use settings default
            if not all_models:
                all_models = [settings.gemini_model]

            logger.info(f"All available Gemini models: {all_models}")

            # Priority list (handle both with and without 'models/' prefix)
            preferred_order = [
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
                "models/gemini-2.0-flash",
                "models/gemini-2.5-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash",
                "gemini-2.5-flash",
            ]

            # 1. Add preferred models if they exist
            self.available_models = []
            # normalize for comparison (strip prefix)
            normalized_map = {m.replace("models/", ""): m for m in all_models}
            for preferred in preferred_order:
                norm = preferred.replace("models/", "")
                if norm in normalized_map and normalized_map[norm] not in self.available_models:
                    self.available_models.append(normalized_map[norm])
                elif preferred in all_models and preferred not in self.available_models:
                    self.available_models.append(preferred)

            # 2. Add any other models not in preferred list (as backup)
            for m in all_models:
                if m not in self.available_models:
                    self.available_models.append(m)

            if not self.available_models:
                logger.error("No models found supporting generateContent.")
                self.available_models = [settings.gemini_model]
            else:
                logger.info(f"Gemini models ready for use: {self.available_models}")

        except Exception as e:
            logger.error(f"Failed to discover models: {e}")
            # Fallback to settings default
            self.available_models = [settings.gemini_model]

    @retry(
        stop=stop_after_attempt(2),  # Reduce retries to avoid wasting quota
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _generate_with_timeout(self, model_name: str, prompt: str, timeout: int = 10, response_schema=None) -> str:
        """
        Generate content with strict timeout and retries.
        Supports both new and legacy SDKs.
        """
        # Normalize model name for new SDK (strip 'models/' prefix)
        clean_name = model_name.replace("models/", "") if model_name.startswith("models/") else model_name

        if NEW_SDK and self.client is not None:
            # New SDK: use aio client
            try:
                config_kwargs = {}
                if response_schema:
                    config_kwargs["response_mime_type"] = "application/json"
                    config_kwargs["response_schema"] = response_schema
                
                config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=clean_name,
                        contents=prompt,
                        config=config
                    ),
                    timeout=timeout,
                )
                # New SDK response has .text
                return getattr(response, "text", str(response))
            except Exception as e:
                # Fallback to legacy if new SDK fails with model not found
                logger.warning(f"New SDK generate failed for {clean_name}: {e}, trying legacy if available")
                if LEGACY_AVAILABLE:
                    model = genai_legacy.GenerativeModel(model_name)
                    kwargs = {}
                    if response_schema:
                        import google.generativeai.types as legacy_types
                        kwargs["generation_config"] = legacy_types.GenerationConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema
                        )
                    
                    response = await asyncio.wait_for(
                        model.generate_content_async(prompt, **kwargs),
                        timeout=timeout,
                    )
                    return response.text
                raise

        if LEGACY_AVAILABLE:
            model = genai_legacy.GenerativeModel(model_name)
            kwargs = {}
            if response_schema:
                import google.generativeai.types as legacy_types
                kwargs["generation_config"] = legacy_types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            response = await asyncio.wait_for(
                model.generate_content_async(prompt, **kwargs),
                timeout=timeout,
            )
            return response.text

        raise RuntimeError("No Gemini SDK available for generation")

    async def generate_content_with_fallback(self, prompt: str, response_schema=None) -> str:
        """
        Generate content using available models, falling back if one is rate limited.
        """
        if not self.available_models:
            return "Insight generation unavailable: No Gemini models found."

        errors = []

        for model_name in self.available_models:
            try:
                logger.info(f"Attempting generation with model: {model_name}")
                return await self._generate_with_timeout(model_name, prompt, response_schema=response_schema)
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

    async def _generate_stream_with_timeout(self, model_name: str, prompt: str, timeout: int = 10, response_schema=None):
        """
        Generate content stream. Yields text chunks.
        """
        clean_name = model_name.replace("models/", "") if model_name.startswith("models/") else model_name

        if NEW_SDK and self.client is not None:
            try:
                config_kwargs = {}
                if response_schema:
                    config_kwargs["response_mime_type"] = "application/json"
                    config_kwargs["response_schema"] = response_schema
                
                config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content_stream(
                        model=clean_name,
                        contents=prompt,
                        config=config
                    ),
                    timeout=timeout,
                )
                async for chunk in response:
                    text = getattr(chunk, "text", str(chunk))
                    if text:
                        yield text
                return
            except Exception as e:
                logger.warning(f"New SDK stream failed for {clean_name}: {e}, trying legacy if available")
                if not LEGACY_AVAILABLE:
                    raise

        if LEGACY_AVAILABLE:
            model = genai_legacy.GenerativeModel(model_name)
            kwargs = {}
            if response_schema:
                import google.generativeai.types as legacy_types
                kwargs["generation_config"] = legacy_types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            # Legacy async streaming
            response = await asyncio.wait_for(
                model.generate_content_async(prompt, stream=True, **kwargs),
                timeout=timeout,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
            return

        raise RuntimeError("No Gemini SDK available for generation")

    async def generate_content_stream_with_fallback(self, prompt: str, response_schema=None):
        """
        Generate content stream using available models.
        """
        if not self.available_models:
            yield "Insight generation unavailable: No Gemini models found."
            return

        errors = []

        for model_name in self.available_models:
            try:
                logger.info(f"Attempting stream generation with model: {model_name}")
                async for chunk in self._generate_stream_with_timeout(model_name, prompt, response_schema=response_schema):
                    yield chunk
                return
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Model {model_name} failed: {error_str}")
                if "429" in error_str or "Quota exceeded" in error_str:
                    errors.append(f"{model_name}: Rate Limit")
                    continue
                errors.append(f"{model_name}: {error_str}")
                continue

        logger.error(f"All Gemini models failed. Errors: {'; '.join(errors)}")
        yield "Insight generation unavailable. Please try again later."

    def list_available_models(self) -> list[dict]:
        """List available models and their methods."""
        try:
            models: list[dict] = []
            if NEW_SDK and self.client is not None:
                try:
                    for m in self.client.models.list():
                        models.append(
                            {
                                "name": getattr(m, "name", str(m)),
                                "supported_generation_methods": getattr(m, "supported_actions", getattr(m, "supported_generation_methods", [])),
                            }
                        )
                    if models:
                        return models
                except Exception as e:
                    logger.warning(f"New SDK list_available failed: {e}")

            if LEGACY_AVAILABLE:
                for m in genai_legacy.list_models():
                    models.append(
                        {
                            "name": m.name,
                            "supported_generation_methods": m.supported_generation_methods,
                        }
                    )
                return models
            return models
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def check_health(self) -> dict:
        """Check API key validity and model availability."""
        status = {
            "api_key_configured": bool(settings.gemini_api_key),
            "available_models": self.available_models,
            "generation_test": "skipped",
        }

        if settings.gemini_api_key and self.available_models:
            try:
                model_name = self.available_models[0]
                # Use the timeout wrapper for health check
                text = await self._generate_with_timeout(model_name, "Hello", timeout=10)
                status["generation_test"] = "success"
                status["test_response"] = text[:200] if text else ""
                status["tested_model"] = model_name
            except Exception as e:
                status["generation_test"] = "failed"
                status["error"] = str(e)

        return status

gemini_client = GeminiClient()
