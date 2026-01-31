# LLM Provider Implementation Notes

## Architecture
- **Abstract Base Class**: `LLMProvider` defines the interface `translate` (async) and `estimate_tokens`.
- **Factory Pattern**: `get_provider` instantiates specific providers based on string names.
- **Optional Dependencies**: Each provider module imports its SDK inside a `try/except` block and sets a flag (e.g., `HAS_OPENAI`). The `__init__` method checks this flag and raises `ImportError` with installation instructions if missing. This avoids requiring users to install all SDKs if they only use one.

## Providers Implemented
1. **OpenAI**: Uses `openai` package (`AsyncOpenAI`). Fallback token estimation with `tiktoken` or char-count heuristic.
2. **Claude**: Uses `anthropic` package (`AsyncAnthropic`). Handles content blocks in response.
3. **Qwen (DashScope)**: Uses `dashscope` package. Wraps synchronous `dashscope.Generation.call` in `asyncio.to_thread` because the SDK is sync-only (or primarily sync).
4. **Doubao (Volcengine)**: Uses `volcenginesdkarkruntime`. Compatible with OpenAI-style client structure.

## Token Estimation
- **OpenAI**: Uses `tiktoken` if available.
- **Others**: Currently using character-count heuristics (e.g., len/3.5 for English, len/2.5 for mixed) as accurate local tokenizers are often heavy or require API calls. This is sufficient for rough cost estimation and context window checks.

## Async Support
- All `translate` methods are `async`.
- Qwen implementation required adapting sync SDK to async using `run_in_executor` pattern (via `asyncio.to_thread`).
