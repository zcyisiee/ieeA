from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs
        self._last_cache_meta: Optional[Dict[str, Any]] = None

    @abstractmethod
    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
        prompt_variant: str = "individual",
    ) -> str:
        """
        Translate the given text.

        Args:
            text: The text to translate.
            context: Optional context for the translation (e.g. "This is a paper about AI").
            glossary_hints: Optional dictionary of glossary terms to hint the model.
            few_shot_examples: Optional list of few-shot examples (dictionaries with 'source' and 'target').

        Returns:
            The translated text.
        """
        pass

    def _get_prebuilt_prompt(self, prompt_variant: str = "individual") -> Optional[str]:
        """Return the prebuilt prompt for the requested variant, if available."""
        if prompt_variant == "batch":
            batch_prompt = getattr(self, "_prebuilt_batch_prompt", None)
            if batch_prompt is not None:
                return batch_prompt
        return getattr(self, "_prebuilt_system_prompt", None)

    async def prepare_prompt_cache_variants(
        self,
        prompt_variants: List[str],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Optional provider hook to prewarm prompt/prefix caches."""
        _ = prompt_variants
        _ = few_shot_examples
        return None

    async def ping(self) -> str:
        return await self.translate("Hi", context=None)

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in the given text.

        Args:
            text: The text to estimate tokens for.

        Returns:
            The estimated number of tokens.
        """
        pass
