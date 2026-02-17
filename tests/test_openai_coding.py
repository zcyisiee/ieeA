"""Automated tests for openai-coding iterative mode.

Tests cover:
- LLMConfig validation (sdk='openai-coding')
- Factory function (get_sdk_client)
- OpenAICodingProvider stateful behavior
- TranslationPipeline sequential execution
- State file persistence & resume
- Retry safety, ping isolation
- Endpoint normalization
- Few-shot injection & full glossary
"""

import asyncio
import json
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Test 1: LLMConfig accepts 'openai-coding' as valid sdk
# ---------------------------------------------------------------------------
def test_config_accepts_openai_coding():
    """LLMConfig(sdk='openai-coding') should succeed without error."""
    from ieeA.rules.config import LLMConfig

    cfg = LLMConfig(sdk="openai-coding")
    assert cfg.sdk == "openai-coding"


# ---------------------------------------------------------------------------
# Test 2: LLMConfig rejects invalid sdk values
# ---------------------------------------------------------------------------
def test_config_rejects_invalid_sdk():
    """LLMConfig(sdk='invalid') should raise ValueError."""
    from ieeA.rules.config import LLMConfig

    with pytest.raises(ValueError, match="sdk must be"):
        LLMConfig(sdk="invalid")


# ---------------------------------------------------------------------------
# Test 3: Factory returns OpenAICodingProvider for sdk='openai-coding'
# ---------------------------------------------------------------------------
def test_factory_returns_correct_type():
    """get_sdk_client('openai-coding', ...) returns OpenAICodingProvider."""
    from ieeA.translator import get_sdk_client
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    provider = get_sdk_client("openai-coding", model="gpt-4o", key="test-key")
    assert isinstance(provider, OpenAICodingProvider)


# ---------------------------------------------------------------------------
# Test 4: Message history accumulates across translate calls
# ---------------------------------------------------------------------------
async def test_history_accumulates(mock_openai_response):
    """3 translate calls should produce 6 history entries (3 user + 3 assistant)."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    await provider.translate("chunk 1")
    await provider.translate("chunk 2")
    await provider.translate("chunk 3")

    assert len(provider.message_history) == 6
    # Verify alternating user/assistant roles
    for i, msg in enumerate(provider.message_history):
        expected_role = "user" if i % 2 == 0 else "assistant"
        assert msg["role"] == expected_role


# ---------------------------------------------------------------------------
# Test 5: Sequential execution — chunks translated one after another
# ---------------------------------------------------------------------------
async def test_sequential_execution(mock_openai_response):
    """Verify chunks are translated sequentially, not concurrently."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider
    from ieeA.translator.pipeline import TranslationPipeline

    timestamps: list = []

    original_create = AsyncMock(return_value=mock_openai_response)

    async def recording_create(*args, **kwargs):
        timestamps.append(("start", time.monotonic()))
        await asyncio.sleep(0.05)
        timestamps.append(("end", time.monotonic()))
        return mock_openai_response

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(side_effect=recording_create)

    pipeline = TranslationPipeline(
        provider=provider,
        sequential_mode=True,
        max_retries=1,
    )
    # Use long chunks (>= 300 chars) so they go through long_chunks path (not batched)
    chunks = [
        {"chunk_id": "c1", "content": "A" * 350},
        {"chunk_id": "c2", "content": "B" * 350},
        {"chunk_id": "c3", "content": "C" * 350},
    ]

    await pipeline.translate_document(chunks=chunks, max_concurrent=1)

    # Each chunk triggers 1 API call → 3 calls → 6 timestamps (3 start + 3 end)
    assert len(timestamps) == 6

    # Sequential means: call N+1 start >= call N end
    for i in range(0, len(timestamps) - 2, 2):
        end_time = timestamps[i + 1][1]
        next_start_time = timestamps[i + 2][1]
        assert next_start_time >= end_time, (
            f"Call {i // 2 + 1} ended at {end_time} but "
            f"call {i // 2 + 2} started at {next_start_time}"
        )

    # History should have 6 entries (3 user + 3 assistant)
    assert len(provider.message_history) == 6


# ---------------------------------------------------------------------------
# Test 6: System prompt contains consistency rule in coding_mode
# ---------------------------------------------------------------------------
def test_system_prompt_contains_consistency():
    """build_system_prompt(coding_mode=True) must contain consistency rule."""
    from ieeA.translator.prompts import build_system_prompt

    prompt = build_system_prompt(coding_mode=True)
    assert "保持专业名词一致性" in prompt


# ---------------------------------------------------------------------------
# Test 7: State file includes message_history after sequential translate
# ---------------------------------------------------------------------------
async def test_state_file_includes_history(mock_openai_response, tmp_path):
    """After sequential translate, saved state JSON must contain message_history."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider
    from ieeA.translator.pipeline import TranslationPipeline

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    state_file = tmp_path / "state.json"
    pipeline = TranslationPipeline(
        provider=provider,
        sequential_mode=True,
        state_file=str(state_file),
        max_retries=1,
    )

    chunks = [
        {"chunk_id": "c1", "content": "A" * 350},
        {"chunk_id": "c2", "content": "B" * 350},
    ]
    await pipeline.translate_document(chunks=chunks)

    # Read back state file
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "message_history" in state_data
    assert len(state_data["message_history"]) == 4  # 2 chunks × 2 (user+assistant)


# ---------------------------------------------------------------------------
# Test 8: Resume restores message history from state file
# ---------------------------------------------------------------------------
async def test_resume_restores_history(mock_openai_response, tmp_path):
    """Loading state with message_history should restore provider history."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider
    from ieeA.translator.pipeline import TranslationPipeline

    # Prepare state file with pre-existing history
    history = [
        {"role": "user", "content": "prev chunk"},
        {"role": "assistant", "content": "之前的翻译"},
    ]
    state_data = {
        "version": "2.1",
        "meta": {},
        "completed": ["c1"],
        "results": [
            {
                "source": "prev chunk",
                "translation": "之前的翻译",
                "chunk_id": "c1",
                "metadata": {},
            }
        ],
        "message_history": history,
    }
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state_data, ensure_ascii=False), encoding="utf-8")

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    pipeline = TranslationPipeline(
        provider=provider,
        sequential_mode=True,
        state_file=str(state_file),
        max_retries=1,
    )

    # Translate with c1 already completed in state, c2 new
    chunks = [
        {"chunk_id": "c1", "content": "prev chunk"},
        {"chunk_id": "c2", "content": "B" * 350},
    ]
    await pipeline.translate_document(chunks=chunks)

    # History should be restored (2 from state) + 2 new (c2) = 4
    assert len(provider.message_history) == 4
    assert provider.message_history[0]["content"] == "prev chunk"
    assert provider.message_history[1]["content"] == "之前的翻译"


# ---------------------------------------------------------------------------
# Test 9: Failed API calls do not corrupt message history
# ---------------------------------------------------------------------------
async def test_retry_no_history_corruption(mock_openai_response):
    """Failed API calls should NOT add entries to message_history."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")

    call_count = 0

    async def failing_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("API Error")
        return mock_openai_response

    provider.client.chat.completions.create = AsyncMock(side_effect=failing_create)

    # First two calls fail at provider level (no pipeline retry)
    with pytest.raises(RuntimeError):
        await provider.translate("test1")

    with pytest.raises(RuntimeError):
        await provider.translate("test2")

    # Third call succeeds
    result = await provider.translate("test3")

    # Only the successful call should be in history
    assert len(provider.message_history) == 2  # 1 user + 1 assistant
    assert provider.message_history[0]["content"] == "test3"
    assert result == "翻译结果"


# ---------------------------------------------------------------------------
# Test 10: ping() does not pollute message history
# ---------------------------------------------------------------------------
async def test_ping_no_history_pollution(mock_openai_response):
    """ping() must NOT modify message_history."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    await provider.ping()

    assert len(provider.message_history) == 0


# ---------------------------------------------------------------------------
# Test 11: Factory strips /chat/completions from endpoint
# ---------------------------------------------------------------------------
def test_endpoint_normalization():
    """get_sdk_client should strip '/chat/completions' from endpoint."""
    from ieeA.translator import get_sdk_client

    provider = get_sdk_client(
        "openai-coding",
        model="gpt-4o",
        key="test-key",
        endpoint="https://api.example.com/v1/chat/completions",
    )

    # The base_url passed to AsyncOpenAI should NOT have /chat/completions
    assert str(provider.client.base_url).rstrip("/") == "https://api.example.com/v1"


# ---------------------------------------------------------------------------
# Test 12: Few-shot examples are injected in EVERY request
# ---------------------------------------------------------------------------
async def test_few_shot_always_injected(mock_openai_response):
    """Verify few-shot examples are injected in EVERY request, not just the first."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    provider = OpenAICodingProvider(model="gpt-4o", api_key="test")
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    few_shots = [
        {"source": "Hello", "target": "你好"},
        {"source": "World", "target": "世界"},
    ]

    # First call passes few_shot_examples explicitly
    await provider.translate("test1", few_shot_examples=few_shots)
    # Subsequent calls do NOT pass few_shot_examples — should still be cached
    await provider.translate("test2")
    await provider.translate("test3")

    # Check ALL 3 calls had few-shot examples in messages
    assert provider.client.chat.completions.create.call_count == 3
    for i, call in enumerate(provider.client.chat.completions.create.call_args_list):
        messages = call.kwargs.get("messages", [])
        # Find few-shot messages: user "Hello", assistant "你好", user "World", assistant "世界"
        few_shot_contents = [
            m["content"]
            for m in messages
            if m["content"] in ("Hello", "你好", "World", "世界")
        ]
        assert len(few_shot_contents) == 4, (
            f"Call {i}: expected 4 few-shot messages, got {len(few_shot_contents)}"
        )


# ---------------------------------------------------------------------------
# Test 13: Full glossary is used (not filtered per-chunk)
# ---------------------------------------------------------------------------
async def test_full_glossary_not_filtered(mock_openai_response, sample_glossary):
    """System prompt should contain ALL glossary terms, not filtered by chunk content."""
    from ieeA.translator.openai_coding_provider import OpenAICodingProvider

    # Chunk text only mentions "Transformer" but NOT "Attention" or "BERT"
    provider = OpenAICodingProvider(
        model="gpt-4o",
        api_key="test",
        full_glossary=sample_glossary,
    )
    provider.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    await provider.translate("The Transformer model is important")

    # Get the system message from the API call
    call_args = provider.client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages", [])
    system_msg = messages[0]["content"]

    # ALL glossary terms should be in system prompt (not just "Transformer")
    assert "Transformer" in system_msg
    assert "注意力机制" in system_msg  # Attention's target
    assert "BERT" in system_msg
