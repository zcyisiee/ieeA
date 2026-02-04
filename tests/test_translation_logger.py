"""Tests for TranslationLogger."""

import json
import tempfile
from pathlib import Path
import pytest

from ieeA.translator.logger import TranslationLogger


class TestTranslationLogger:
    """Test suite for TranslationLogger."""

    def test_log_prompt_config_basic(self):
        """Test log_prompt_config records all fields."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_prompt_config(
                system_prompt="test system prompt",
                custom_system_prompt="custom prompt",
                glossary_terms={"term1": "translation1"},
                few_shot_count=3,
                context="test context",
            )

            config = logger.log_data["prompt_config"]
            assert config["system_prompt"] == "test system prompt"
            assert config["custom_system_prompt"] == "custom prompt"
            assert config["glossary_terms"] == {"term1": "translation1"}
            assert config["few_shot_count"] == 3
            assert config["context"] == "test context"
            assert "timestamp" in config

    def test_log_prompt_config_with_none_values(self):
        """Test log_prompt_config handles None values."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_prompt_config(
                system_prompt="prompt",
                custom_system_prompt=None,
                glossary_terms=None,
                few_shot_count=0,
                context=None,
            )

            config = logger.log_data["prompt_config"]
            assert config["custom_system_prompt"] is None
            assert config["glossary_terms"] is None
            assert config["context"] is None

    def test_log_chunk(self):
        """Test log_chunk records chunk info."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_chunk("chunk_1", "paragraph", 100, batched=False)

            assert len(logger.log_data["chunks"]) == 1
            chunk = logger.log_data["chunks"][0]
            assert chunk["chunk_id"] == "chunk_1"
            assert chunk["type"] == "paragraph"
            assert chunk["length"] == 100
            assert chunk["batched"] is False

    def test_log_chunk_batched(self):
        """Test log_chunk with batch info."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_chunk("chunk_1", "short", 50, batched=True, batch_id="batch_0")

            chunk = logger.log_data["chunks"][0]
            assert chunk["batched"] is True
            assert chunk["batch_id"] == "batch_0"

    def test_log_skip(self):
        """Test log_skip records skipped chunks."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_skip("chunk_1", "pure_placeholder", "[[MACRO_0]]")

            assert len(logger.log_data["skipped"]) == 1
            skip = logger.log_data["skipped"][0]
            assert skip["chunk_id"] == "chunk_1"
            assert skip["reason"] == "pure_placeholder"
            assert skip["content"] == "[[MACRO_0]]"

    def test_log_batch(self):
        """Test log_batch records batch info."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.log_batch("batch_0", "short_chunks", 5, 250)

            assert len(logger.log_data["batches"]) == 1
            batch = logger.log_data["batches"][0]
            assert batch["batch_id"] == "batch_0"
            assert batch["type"] == "short_chunks"
            assert batch["chunk_count"] == 5
            assert batch["total_chars"] == 250

    def test_add_llm_time(self):
        """Test add_llm_time accumulates time."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.add_llm_time(1.5)
            logger.add_llm_time(2.5)

            assert logger.llm_time_total == 4.0

    def test_save_creates_json_file(self):
        """Test save creates valid JSON file."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.set_source_file("test.tex")
            logger.start_timing()
            logger.log_prompt_config(
                system_prompt="prompt",
                custom_system_prompt=None,
                glossary_terms={},
                few_shot_count=0,
                context=None,
            )
            logger.log_chunk("c1", "test", 100)
            logger.add_llm_time(1.0)

            log_path = logger.save()

            assert log_path is not None
            assert log_path.exists()

            with open(log_path) as f:
                data = json.load(f)

            assert data["source_file"] == "test.tex"
            assert "prompt_config" in data
            assert len(data["chunks"]) == 1
            assert data["timing"]["llm_seconds"] == 1.0

    def test_verbose_mode(self):
        """Test logger works in verbose mode without error."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td), verbose=True)
            # Should not raise
            logger.log_prompt_config(
                system_prompt="prompt",
                custom_system_prompt=None,
                glossary_terms={"a": "b"},
                few_shot_count=2,
                context=None,
            )
            logger.log_chunk("c1", "test", 100)
            logger.log_skip("c2", "reason", "content")
            logger.log_batch("b1", "type", 3, 150)

    def test_log_skip_with_long_content(self):
        """Test log_skip truncates long content."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            long_content = "x" * 200
            logger.log_skip("chunk_1", "test", long_content)

            skip = logger.log_data["skipped"][0]
            # Should be truncated to 100 chars + "..."
            assert len(skip["content"]) == 103
            assert skip["content"].endswith("...")

    def test_hq_mode_flag(self):
        """Test hq_mode flag is recorded."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td), hq_mode=True)
            assert logger.log_data["hq_mode"] is True

            logger2 = TranslationLogger(Path(td), hq_mode=False)
            assert logger2.log_data["hq_mode"] is False

    def test_multiple_chunks_and_batches(self):
        """Test logging multiple chunks and batches."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))

            # Log multiple chunks
            logger.log_chunk("c1", "paragraph", 200)
            logger.log_chunk("c2", "short", 50, batched=True, batch_id="b1")
            logger.log_chunk("c3", "short", 60, batched=True, batch_id="b1")

            # Log batch
            logger.log_batch("b1", "short_chunks", 2, 110)

            assert len(logger.log_data["chunks"]) == 3
            assert len(logger.log_data["batches"]) == 1
            assert logger.log_data["batches"][0]["total_chars"] == 110

    def test_save_without_timing_start(self):
        """Test save works even if start_timing was not called."""
        with tempfile.TemporaryDirectory() as td:
            logger = TranslationLogger(Path(td))
            logger.set_source_file("test.tex")

            log_path = logger.save()

            assert log_path is not None
            assert log_path.exists()

            with open(log_path) as f:
                data = json.load(f)

            # Should have timing section with 0 total_seconds
            assert data["timing"]["total_seconds"] == 0
            assert data["timing"]["llm_seconds"] == 0
