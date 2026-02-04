"""Translation pipeline with glossary preprocessing and postprocessing."""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Any, Union, Callable, cast

from pydantic import BaseModel, Field

from ..rules.glossary import Glossary
from .llm_base import LLMProvider
from .prompts import build_batch_translation_text


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
        abstract_context: Optional[str] = None,
        custom_system_prompt: Optional[str] = None,
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
            abstract_context: Optional abstract text for high-quality mode context.
            custom_system_prompt: Optional custom system prompt to replace default style.
        """
        self.provider = provider
        self.glossary = glossary or Glossary()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay
        self.state_file = Path(state_file) if state_file else None
        self.few_shot_examples = few_shot_examples or []
        self.abstract_context = abstract_context
        self.custom_system_prompt = custom_system_prompt

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
                    custom_system_prompt=self.custom_system_prompt,
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Check if it's a rate limit error (429)
                    error_str = str(e).lower()
                    if "429" in error_str or "rate limit" in error_str:
                        # Longer delay for rate limit errors
                        delay = max(5.0, self.retry_delay * (3**attempt))
                    else:
                        # Standard exponential backoff
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

        # Merge abstract context with provided context for high-quality mode
        merged_context = context
        if self.abstract_context:
            if context:
                merged_context = (
                    f"{context}\n\nDocument Abstract:\n{self.abstract_context}"
                )
            else:
                merged_context = f"Document Abstract:\n{self.abstract_context}"

        # Call LLM with retry
        raw_translation = await self._call_with_retry(
            text=preprocessed_text,
            context=merged_context,
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

    async def translate_batch(
        self,
        chunks: List[Dict[str, str]],
        context: Optional[str] = None,
    ) -> List[TranslatedChunk]:
        preprocessed_chunks = []
        mappings = []
        for chunk_data in chunks:
            preprocessed_text, mapping = self._preprocessor.preprocess(
                chunk_data["content"]
            )
            preprocessed_chunks.append(
                {"chunk_id": chunk_data["chunk_id"], "content": preprocessed_text}
            )
            mappings.append(mapping)

        batch_text = build_batch_translation_text(preprocessed_chunks)
        glossary_hints = self._build_glossary_hints()

        merged_context = context
        if self.abstract_context:
            if context:
                merged_context = (
                    f"{context}\n\nDocument Abstract:\n{self.abstract_context}"
                )
            else:
                merged_context = f"Document Abstract:\n{self.abstract_context}"

        batch_instruction = "请翻译以下编号内容，保持相同的编号格式返回。"
        if merged_context:
            merged_context = f"{batch_instruction}\n\n{merged_context}"
        else:
            merged_context = batch_instruction

        raw_response = await self._call_with_retry(
            text=batch_text,
            context=merged_context,
            glossary_hints=glossary_hints,
        )

        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)"
        matches = re.findall(pattern, raw_response, re.DOTALL)

        if len(matches) != len(chunks):
            return []

        results = []
        for i, (idx_str, translated_text) in enumerate(matches):
            idx = int(idx_str) - 1
            if idx < 0 or idx >= len(chunks):
                return []

            final_translation = self._preprocessor.postprocess(
                translated_text.strip(), mappings[idx]
            )

            results.append(
                TranslatedChunk(
                    source=chunks[idx]["content"],
                    translation=final_translation,
                    chunk_id=chunks[idx]["chunk_id"],
                    metadata={
                        "had_glossary_terms": len(mappings[idx]) > 0,
                        "glossary_terms_count": len(mappings[idx]),
                        "batch_translated": True,
                    },
                )
            )

        result_map = {r.chunk_id: r for r in results}
        ordered_results = [result_map[c["chunk_id"]] for c in chunks]

        return ordered_results

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
        max_concurrent: int = 50,
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

        # Separate pure placeholder chunks from translatable chunks
        placeholder_pattern = re.compile(r"^\[\[[A-Z_]+_\d+\]\]$")
        placeholder_chunks = []
        translatable_chunks = []

        for c in chunks:
            if c["chunk_id"] not in completed_ids:
                if placeholder_pattern.fullmatch(c["content"].strip()):
                    placeholder_chunks.append(c)
                else:
                    translatable_chunks.append(c)

        # Create TranslatedChunk objects for pure placeholders (no LLM call)
        for chunk_data in placeholder_chunks:
            chunk_id = chunk_data["chunk_id"]
            content = chunk_data["content"]
            placeholder_result = TranslatedChunk(
                source=content,
                translation=content,
                chunk_id=chunk_id,
                metadata={"skipped_placeholder": True},
            )
            results_map[chunk_id] = placeholder_result
            state["completed"].append(chunk_id)
            state["results"].append(placeholder_result.model_dump())

        if not translatable_chunks:
            self._save_state(state)
            return [results_map[chunk_data["chunk_id"]] for chunk_data in chunks]

        short_chunks = []
        long_chunks = []
        for c in translatable_chunks:
            if len(c["content"]) < 100:
                short_chunks.append(c)
            else:
                long_chunks.append(c)

        batches = []
        for i in range(0, len(short_chunks), 10):
            batches.append(short_chunks[i : i + 10])

        semaphore = asyncio.Semaphore(max_concurrent)
        completed_count = 0
        progress_lock = asyncio.Lock()
        total_pending = len(translatable_chunks)

        async def translate_batch_with_semaphore(
            batch_chunks: List[Dict[str, str]],
        ) -> List[TranslatedChunk]:
            nonlocal completed_count
            async with semaphore:
                try:
                    batch_results = await self.translate_batch(
                        chunks=batch_chunks,
                        context=context,
                    )

                    if not batch_results:
                        fallback_results = []
                        for chunk_data in batch_chunks:
                            result = await self.translate_chunk(
                                chunk=chunk_data["content"],
                                chunk_id=chunk_data["chunk_id"],
                                context=context,
                            )
                            fallback_results.append(result)
                        batch_results = fallback_results

                    async with progress_lock:
                        completed_count += len(batch_chunks)
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total_pending)
                            except Exception:
                                pass

                    return batch_results
                except Exception:
                    fallback_results = []
                    for chunk_data in batch_chunks:
                        result = await self.translate_chunk(
                            chunk=chunk_data["content"],
                            chunk_id=chunk_data["chunk_id"],
                            context=context,
                        )
                        fallback_results.append(result)

                    async with progress_lock:
                        completed_count += len(batch_chunks)
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total_pending)
                            except Exception:
                                pass

                    return fallback_results

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

        batch_tasks = [translate_batch_with_semaphore(batch) for batch in batches]
        long_tasks = [translate_with_semaphore(c) for c in long_chunks]

        all_tasks = batch_tasks + long_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if i < len(batches):
                    batch = batches[i]
                    chunk_ids = [c["chunk_id"] for c in batch]
                    raise RuntimeError(
                        f"Batch translation failed for chunks {chunk_ids}: {result}"
                    )
                else:
                    chunk_idx = i - len(batches)
                    chunk_id = long_chunks[chunk_idx]["chunk_id"]
                    raise RuntimeError(
                        f"Translation failed for chunk {chunk_id}: {result}"
                    )

            if i < len(batches):
                batch_results = cast(List[TranslatedChunk], result)
                for translated_chunk in batch_results:
                    results_map[translated_chunk.chunk_id] = translated_chunk
                    state["completed"].append(translated_chunk.chunk_id)
                    state["results"].append(translated_chunk.model_dump())
            else:
                success_result = cast(TranslatedChunk, result)
                results_map[success_result.chunk_id] = success_result
                state["completed"].append(success_result.chunk_id)
                state["results"].append(success_result.model_dump())

        # Save final state
        self._save_state(state)

        # Return results in original order
        return [results_map[chunk_data["chunk_id"]] for chunk_data in chunks]
