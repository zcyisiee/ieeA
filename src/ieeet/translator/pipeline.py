"""Translation pipeline with glossary preprocessing and postprocessing."""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Any, Union, Callable, cast

from pydantic import BaseModel, Field

from ..rules.glossary import Glossary
from .llm_base import LLMProvider
from .prompts import build_translation_prompt


class TranslatedChunk(BaseModel):
    """A translated chunk with source, translation, and metadata."""

    source: str
    translation: str
    chunk_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GlossaryPreprocessor:
    """Preprocessor that replaces glossary terms with placeholders."""

    def __init__(self, glossary: Glossary):
        self.glossary = glossary
        self._placeholder_counter = 0

    def preprocess(self, text: str) -> tuple[str, Dict[str, str]]:
        """
        Replace glossary terms with numbered placeholders.

        Args:
            text: The input text to preprocess.

        Returns:
            A tuple of (preprocessed_text, mapping) where mapping maps
            placeholders back to original terms.
        """
        if not text:
            return "", {}

        mapping: Dict[str, str] = {}
        result = text

        # Sort terms by length (longest first) to handle overlapping terms
        terms = sorted(self.glossary.terms.keys(), key=len, reverse=True)

        for term in terms:
            if term in result:
                # Find all occurrences and replace them
                # Use word boundary-aware replacement for case sensitivity
                pattern = re.escape(term)
                matches = list(re.finditer(pattern, result))

                # Replace from end to start to preserve indices
                for match in reversed(matches):
                    self._placeholder_counter += 1
                    placeholder = f"{{{{GLOSS_{self._placeholder_counter:03d}}}}}"
                    mapping[placeholder] = term
                    result = (
                        result[: match.start()] + placeholder + result[match.end() :]
                    )

        return result, mapping

    def postprocess(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Restore placeholders with their translated glossary terms.

        Args:
            text: The translated text with placeholders.
            mapping: The mapping from placeholders to original terms.

        Returns:
            The text with placeholders replaced by translations.
        """
        result = text

        for placeholder, original_term in mapping.items():
            entry = self.glossary.get(original_term)
            if entry:
                translation = entry.target
            else:
                # Fallback to original term if not found
                translation = original_term
            result = result.replace(placeholder, translation)

        return result


class TranslationPipeline:
    """
    Translation pipeline that orchestrates chunk translation with glossary
    preprocessing and postprocessing.
    """

    def __init__(
        self,
        provider: LLMProvider,
        glossary: Optional[Glossary] = None,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 0.0,
        state_file: Optional[Union[str, Path]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Initialize the translation pipeline.

        Args:
            provider: The LLM provider to use for translation.
            glossary: Optional glossary for term translation.
            max_retries: Maximum number of retry attempts on failure.
            retry_delay: Base delay between retries (exponential backoff).
            rate_limit_delay: Delay between API calls for rate limiting.
            state_file: Optional file path to save/load intermediate state.
            few_shot_examples: Optional few-shot examples for the prompt.
        """
        self.provider = provider
        self.glossary = glossary or Glossary()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay
        self.state_file = Path(state_file) if state_file else None
        self.few_shot_examples = few_shot_examples or []

        self._preprocessor = GlossaryPreprocessor(self.glossary)

    def _build_glossary_hints(self) -> Dict[str, str]:
        """Build glossary hints dictionary from glossary."""
        return {term: entry.target for term, entry in self.glossary.terms.items()}

    async def _call_with_retry(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Call the LLM provider with exponential backoff retry.

        Args:
            text: The text to translate.
            context: Optional context for the translation.
            glossary_hints: Optional glossary hints.

        Returns:
            The translated text.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = await self.provider.translate(
                    text=text,
                    context=context,
                    glossary_hints=glossary_hints,
                    few_shot_examples=self.few_shot_examples,
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        raise last_error  # type: ignore

    async def translate_chunk(
        self,
        chunk: str,
        chunk_id: str,
        context: Optional[str] = None,
    ) -> TranslatedChunk:
        """
        Translate a single chunk with glossary preprocessing and postprocessing.

        Args:
            chunk: The text chunk to translate.
            chunk_id: Unique identifier for this chunk.
            context: Optional context information.

        Returns:
            TranslatedChunk with the translation result.
        """
        # Preprocess: Replace glossary terms with placeholders
        preprocessed_text, mapping = self._preprocessor.preprocess(chunk)

        # Build glossary hints for the prompt
        glossary_hints = self._build_glossary_hints()

        # Call LLM with retry
        raw_translation = await self._call_with_retry(
            text=preprocessed_text,
            context=context,
            glossary_hints=glossary_hints,
        )

        # Postprocess: Restore placeholders with translated terms
        final_translation = self._preprocessor.postprocess(raw_translation, mapping)

        return TranslatedChunk(
            source=chunk,
            translation=final_translation,
            chunk_id=chunk_id,
            metadata={
                "had_glossary_terms": len(mapping) > 0,
                "glossary_terms_count": len(mapping),
            },
        )

    def _load_state(self) -> Dict[str, Any]:
        """Load intermediate state from file."""
        if self.state_file and self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {"completed": [], "results": []}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save intermediate state to file."""
        if self.state_file:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def translate_document(
        self,
        chunks: List[Dict[str, str]],
        context: Optional[str] = None,
        max_concurrent: int = 20,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TranslatedChunk]:
        """
        Translate a document consisting of multiple chunks with concurrent requests.

        Args:
            chunks: List of chunk dictionaries with 'chunk_id' and 'content' keys.
            context: Optional context for all chunks.
            max_concurrent: Maximum number of concurrent translation requests.
            progress_callback: Optional callback (completed, total) for progress updates.

        Returns:
            List of TranslatedChunk objects in the same order as input.
        """
        # Load existing state for resume capability
        state = self._load_state()
        completed_ids = set(state["completed"])

        # Build results map from existing state
        results_map: Dict[str, TranslatedChunk] = {}
        for result_data in state["results"]:
            chunk = TranslatedChunk(**result_data)
            results_map[chunk.chunk_id] = chunk

        # Filter out already completed chunks
        pending_chunks = [c for c in chunks if c["chunk_id"] not in completed_ids]

        if not pending_chunks:
            return [results_map[chunk_data["chunk_id"]] for chunk_data in chunks]

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        completed_count = 0
        progress_lock = asyncio.Lock()
        total_pending = len(pending_chunks)

        async def translate_with_semaphore(
            chunk_data: Dict[str, str],
        ) -> TranslatedChunk:
            async with semaphore:
                chunk_id = chunk_data["chunk_id"]
                content = chunk_data["content"]
                result = await self.translate_chunk(
                    chunk=content,
                    chunk_id=chunk_id,
                    context=context,
                )

                nonlocal completed_count
                async with progress_lock:
                    completed_count += 1
                    if progress_callback:
                        try:
                            progress_callback(completed_count, total_pending)
                        except Exception:
                            pass

                return result

        # Execute all translations concurrently
        tasks = [translate_with_semaphore(c) for c in pending_chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update state
        for i, result in enumerate(results):
            chunk_id = pending_chunks[i]["chunk_id"]
            if isinstance(result, Exception):
                raise RuntimeError(f"Translation failed for chunk {chunk_id}: {result}")

            success_result = cast(TranslatedChunk, result)
            results_map[chunk_id] = success_result
            state["completed"].append(chunk_id)
            state["results"].append(success_result.model_dump())

        # Save final state
        self._save_state(state)

        # Return results in original order
        return [results_map[chunk_data["chunk_id"]] for chunk_data in chunks]
