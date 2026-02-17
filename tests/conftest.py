"""Shared fixtures for openai-coding tests."""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = "翻译结果"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


@pytest.fixture
def mock_openai_response_factory():
    """Factory that creates mock responses with custom content."""

    def _factory(content: str = "翻译结果"):
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    return _factory


@pytest.fixture
def sample_glossary():
    """Create a sample Glossary for testing."""
    from ieeA.rules.glossary import Glossary, GlossaryEntry

    return Glossary(
        terms={
            "Transformer": GlossaryEntry(target="Transformer"),
            "Attention": GlossaryEntry(target="注意力机制"),
            "BERT": GlossaryEntry(target="BERT"),
        }
    )


@pytest.fixture
def sample_chunks():
    """Standard test chunks."""
    return [
        {"chunk_id": "chunk_1", "content": "Hello world"},
        {"chunk_id": "chunk_2", "content": "This is a test"},
        {"chunk_id": "chunk_3", "content": "Another chunk"},
    ]
