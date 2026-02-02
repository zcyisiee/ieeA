#!/usr/bin/env python3
"""Test translation functionality with user-provided API endpoint."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ieeA.translator.openai_provider import OpenAIProvider

# User-provided API configuration
API_CONFIG = {
    "base_url": "http://127.0.0.1:8045/v1",
    "api_key": "sk-174d582f879f42e297a08aad2f9d7547",
    "model": "claude-sonnet-4-5",
}

MAX_RETRIES = 5

# Test cases for translation
TEST_CASES = [
    {
        "name": "Simple sentence",
        "text": "The attention mechanism has become a fundamental component in modern deep learning architectures.",
        "expected_contains": ["注意力", "深度学习"],
    },
    {
        "name": "Academic abstract",
        "text": "We propose a novel transformer-based architecture for natural language processing tasks.",
        "expected_contains": ["transformer", "自然语言"],
    },
]


async def test_translation():
    """Test translation with the provided API endpoint."""
    print("=" * 60)
    print("ieeT Translation API Test")
    print("=" * 60)
    print(f"API Endpoint: {API_CONFIG['base_url']}")
    print(f"Model: {API_CONFIG['model']}")
    print(f"Max Retries: {MAX_RETRIES}")
    print("=" * 60)

    # Initialize provider with custom base_url
    provider = OpenAIProvider(
        model=API_CONFIG["model"],
        api_key=API_CONFIG["api_key"],
        base_url=API_CONFIG["base_url"],
    )

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}] {test_case['name']}")
        print(f"Source: {test_case['text'][:80]}...")

        last_error = None
        success = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"  Attempt {attempt}/{MAX_RETRIES}...", end=" ")

                translation = await provider.translate(
                    text=test_case["text"],
                    context="Academic paper translation",
                )

                print("SUCCESS")
                print(f"  Translation: {translation}")

                # Check if expected terms are present
                missing_terms = []
                for term in test_case.get("expected_contains", []):
                    if term not in translation:
                        missing_terms.append(term)

                if missing_terms:
                    print(f"  Warning: Missing expected terms: {missing_terms}")

                results.append(
                    {
                        "name": test_case["name"],
                        "success": True,
                        "attempts": attempt,
                        "translation": translation,
                    }
                )
                success = True
                break

            except Exception as e:
                last_error = e
                print(f"FAILED - {type(e).__name__}: {e}")

                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1)  # Brief delay before retry

        if not success:
            print(f"  All {MAX_RETRIES} attempts failed!")
            results.append(
                {
                    "name": test_case["name"],
                    "success": False,
                    "attempts": MAX_RETRIES,
                    "error": str(last_error),
                }
            )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"Total Tests: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"  [{status}] {r['name']} (attempts: {r['attempts']})")

    print("=" * 60)

    return successful == len(results)


if __name__ == "__main__":
    success = asyncio.run(test_translation())
    sys.exit(0 if success else 1)
