from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs

    @abstractmethod
    async def translate(
        self, 
        text: str, 
        context: Optional[str] = None, 
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None
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
