#!/usr/bin/env python3
"""
Test whether Anthropic SDK temperature parameter works on a custom endpoint.

Experiment Design:
- Use fixed prompt across different temperatures (0.0, 0.3, 0.7, 1.0)
- Each temperature repeated 10 times
- Measure output diversity:
  - Exact match ratio (how many outputs are identical)
  - Vocabulary diversity (unique words ratio)
  - Length variance (standard deviation of output lengths)

If temperature works:
  - Low temp (0.0): high consistency, low diversity
  - High temp (1.0): low consistency, high diversity
"""

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

API_CONFIG = {
    "base_url": "http://127.0.0.1:8045",  # No /v1 suffix
    "api_key": "sk-174d582f879f42e297a08aad2f9d7547",
    "model": "claude-opus-4-6-thinking",
}

# Temperature values to test
TEMPERATURES = [0.0, 0.3, 0.7, 1.0]

# Repetitions per temperature
REPEATS = 10

# Test prompt - designed to have multiple valid responses
TEST_PROMPT = """请用一句话描述"人工智能"这个概念。每次回答尽量使用不同的表达方式。"""

# Max tokens for response
MAX_TOKENS = 200

# Output directory
OUTPUT_DIR = Path(__file__).parent / "temperature_test_results"


# ============================================================================
# CORE FUNCTIONS
# ============================================================================


def call_anthropic_with_temperature(
    client: Anthropic,
    temperature: float,
    prompt: str,
    model: str,
    max_tokens: int = 200,
) -> dict[str, Any]:
    """
    Make a single API call with specified temperature.
    Returns response data including text and metadata.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response - handle both thinking and text blocks
        thinking_text = ""
        output_text = ""

        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "thinking":
                # ThinkingBlock
                thinking_text = getattr(block, "thinking", "")
            elif block_type == "text":
                # TextBlock
                output_text = getattr(block, "text", "")

        # Use output_text as the main response; include thinking if present
        main_text = output_text.strip() if output_text else ""

        return {
            "success": True,
            "text": main_text,
            "thinking": thinking_text.strip() if thinking_text else None,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "response_id": response.id,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def calculate_diversity_metrics(texts: list[str]) -> dict[str, Any]:
    """
    Calculate diversity metrics for a list of texts.
    """
    if not texts:
        return {"error": "No texts to analyze"}

    # Filter successful responses
    valid_texts = [t for t in texts if t]
    n = len(valid_texts)

    if n == 0:
        return {"error": "No valid texts"}

    # Exact match analysis
    text_counts = Counter(valid_texts)
    unique_texts = len(text_counts)
    most_common_count = text_counts.most_common(1)[0][1] if text_counts else 0
    exact_match_ratio = most_common_count / n if n > 0 else 0

    # Length statistics
    lengths = [len(t) for t in valid_texts]
    avg_length = sum(lengths) / n
    length_variance = sum((l - avg_length) ** 2 for l in lengths) / n
    length_std = length_variance**0.5

    # Vocabulary diversity (character-level for Chinese)
    all_chars = set()
    text_char_sets = []
    for text in valid_texts:
        chars = set(
            text.replace(" ", "").replace("，", "").replace("。", "").replace("\n", "")
        )
        text_char_sets.append(chars)
        all_chars.update(chars)

    # Average pairwise character overlap
    if len(text_char_sets) > 1:
        overlaps = []
        for i in range(len(text_char_sets)):
            for j in range(i + 1, len(text_char_sets)):
                intersection = len(text_char_sets[i] & text_char_sets[j])
                union = len(text_char_sets[i] | text_char_sets[j])
                if union > 0:
                    overlaps.append(intersection / union)
        avg_char_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
    else:
        avg_char_overlap = 1.0

    # Vocabulary richness (type-token ratio across all texts)
    all_tokens = []
    for text in valid_texts:
        all_tokens.extend(text.replace(" ", "").replace("，", "").replace("。", ""))
    total_tokens = len(all_tokens)
    unique_tokens = len(set(all_tokens))
    type_token_ratio = unique_tokens / total_tokens if total_tokens > 0 else 0

    return {
        "total_responses": len(texts),
        "valid_responses": n,
        "unique_texts": unique_texts,
        "exact_match_ratio": round(exact_match_ratio, 4),
        "most_common_count": most_common_count,
        "length": {
            "min": min(lengths),
            "max": max(lengths),
            "avg": round(avg_length, 2),
            "std": round(length_std, 2),
        },
        "vocabulary": {
            "total_tokens": total_tokens,
            "unique_tokens": unique_tokens,
            "type_token_ratio": round(type_token_ratio, 4),
            "avg_char_overlap": round(avg_char_overlap, 4),
        },
    }


def run_temperature_experiment(
    client: Anthropic,
    temperature: float,
    prompt: str,
    model: str,
    repeats: int = 10,
    max_tokens: int = 200,
) -> dict[str, Any]:
    """
    Run experiment for a single temperature value.
    """
    print(f"\n{'=' * 60}")
    print(f"Temperature: {temperature}")
    print(f"Repeats: {repeats}")
    print(f"{'=' * 60}")

    results = []
    texts = []

    for i in range(repeats):
        print(f"  [{i + 1}/{repeats}] ", end="", flush=True)

        result = call_anthropic_with_temperature(
            client=client,
            temperature=temperature,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )

        results.append(result)

        if result["success"]:
            texts.append(result["text"])
            display_text = (
                result["text"][:60] + "..."
                if len(result["text"]) > 60
                else result["text"]
            )
            print(f"✓ {display_text}")
        else:
            print(
                f"✗ Error: {result.get('error_type', 'Unknown')}: {result.get('error', '')[:50]}"
            )

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    # Calculate diversity metrics
    metrics = calculate_diversity_metrics(texts)

    print(f"\n  Results Summary:")
    print(f"    Successful: {len(texts)}/{repeats}")
    print(f"    Unique outputs: {metrics.get('unique_texts', 'N/A')}")
    print(f"    Exact match ratio: {metrics.get('exact_match_ratio', 'N/A')}")
    print(f"    Length std: {metrics.get('length', {}).get('std', 'N/A')}")

    return {
        "temperature": temperature,
        "repeats": repeats,
        "results": results,
        "texts": texts,
        "metrics": metrics,
    }


def analyze_temperature_effect(experiments: list[dict]) -> dict[str, Any]:
    """
    Analyze the relationship between temperature and output diversity.
    """
    analysis = {
        "conclusion": None,
        "evidence": [],
    }

    # Extract metrics per temperature
    temp_metrics = []
    for exp in experiments:
        temp = exp["temperature"]
        metrics = exp["metrics"]
        if "error" not in metrics:
            temp_metrics.append(
                {
                    "temperature": temp,
                    "exact_match_ratio": metrics["exact_match_ratio"],
                    "length_std": metrics["length"]["std"],
                    "type_token_ratio": metrics["vocabulary"]["type_token_ratio"],
                    "unique_texts": metrics["unique_texts"],
                }
            )

    if len(temp_metrics) < 2:
        analysis["conclusion"] = "INSUFFICIENT_DATA"
        return analysis

    # Sort by temperature
    sorted_by_temp = sorted(temp_metrics, key=lambda x: x["temperature"])

    # Check if low temp has higher consistency than high temp
    low_temp = sorted_by_temp[0]  # Lowest temp
    high_temp = sorted_by_temp[-1]  # Highest temp

    consistency_decreases = (
        low_temp["exact_match_ratio"] >= high_temp["exact_match_ratio"]
    )
    diversity_increases = low_temp["type_token_ratio"] <= high_temp["type_token_ratio"]

    # Calculate correlation between temperature and diversity
    temps = [m["temperature"] for m in temp_metrics]
    diversities = [1 - m["exact_match_ratio"] for m in temp_metrics]

    # Simple correlation check (Pearson)
    if len(temps) > 2:
        temp_mean = sum(temps) / len(temps)
        div_mean = sum(diversities) / len(diversities)

        numerator = sum(
            (t - temp_mean) * (d - div_mean) for t, d in zip(temps, diversities)
        )
        denom_temp = sum((t - temp_mean) ** 2 for t in temps) ** 0.5
        denom_div = sum((d - div_mean) ** 2 for d in diversities) ** 0.5

        if denom_temp > 0 and denom_div > 0:
            correlation = numerator / (denom_temp * denom_div)
        else:
            correlation = 0
    else:
        correlation = 0

    # Gather evidence
    evidence = []
    evidence.append(f"Correlation (temp vs diversity): {correlation:.4f}")
    evidence.append(
        f"Low temp ({low_temp['temperature']}) exact match: {low_temp['exact_match_ratio']:.4f}"
    )
    evidence.append(
        f"High temp ({high_temp['temperature']}) exact match: {high_temp['exact_match_ratio']:.4f}"
    )
    evidence.append(f"Consistency decreases with temp: {consistency_decreases}")
    evidence.append(f"Diversity increases with temp: {diversity_increases}")

    analysis["evidence"] = evidence
    analysis["metrics_by_temperature"] = temp_metrics
    analysis["correlation"] = correlation

    # Final conclusion
    if correlation > 0.5 and consistency_decreases:
        analysis["conclusion"] = "TEMPERATURE_WORKS"
        analysis["summary"] = (
            "Temperature parameter is working correctly. Higher temperatures produce more diverse outputs."
        )
    elif correlation < -0.5:
        analysis["conclusion"] = "TEMPERATURE_REVERSED"
        analysis["summary"] = (
            "Temperature may be working in reverse (higher temp = more consistent). This is unusual."
        )
    elif abs(correlation) < 0.3:
        analysis["conclusion"] = "TEMPERATURE_IGNORED"
        analysis["summary"] = (
            "Temperature parameter appears to be IGNORED by the endpoint. Outputs show similar diversity across all temperatures."
        )
    else:
        analysis["conclusion"] = "INCONCLUSIVE"
        analysis["summary"] = (
            "Results are inconclusive. More data or different test prompts may be needed."
        )

    return analysis


def main():
    """Main experiment runner."""
    print("=" * 60)
    print("Anthropic SDK Temperature Test")
    print("=" * 60)
    print(f"Endpoint: {API_CONFIG['base_url']}")
    print(f"Model: {API_CONFIG['model']}")
    print(f"Temperatures: {TEMPERATURES}")
    print(f"Repeats per temp: {REPEATS}")
    print(f"Prompt: {TEST_PROMPT[:50]}...")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = OUTPUT_DIR / f"temperature_test_{timestamp}.json"

    # Initialize client (synchronous)
    client = Anthropic(
        api_key=API_CONFIG["api_key"],
        base_url=API_CONFIG["base_url"],
    )

    # Run experiments
    experiments = []
    for temp in TEMPERATURES:
        exp = run_temperature_experiment(
            client=client,
            temperature=temp,
            prompt=TEST_PROMPT,
            model=API_CONFIG["model"],
            repeats=REPEATS,
            max_tokens=MAX_TOKENS,
        )
        experiments.append(exp)

    # Analyze results
    analysis = analyze_temperature_effect(experiments)

    # Print final analysis
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print(f"\nConclusion: {analysis['conclusion']}")
    print(f"\nSummary: {analysis.get('summary', 'N/A')}")
    print("\nEvidence:")
    for e in analysis.get("evidence", []):
        print(f"  - {e}")

    print("\nMetrics by Temperature:")
    for m in analysis.get("metrics_by_temperature", []):
        print(
            f"  Temp {m['temperature']}: exact_match={m['exact_match_ratio']:.4f}, "
            f"unique={m['unique_texts']}, length_std={m['length_std']:.2f}"
        )

    # Save results
    output = {
        "config": {
            "endpoint": API_CONFIG["base_url"],
            "model": API_CONFIG["model"],
            "temperatures": TEMPERATURES,
            "repeats": REPEATS,
            "prompt": TEST_PROMPT,
            "max_tokens": MAX_TOKENS,
            "timestamp": timestamp,
        },
        "experiments": [
            {
                "temperature": exp["temperature"],
                "texts": exp["texts"],
                "metrics": exp["metrics"],
            }
            for exp in experiments
        ],
        "analysis": analysis,
    }

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {result_file}")

    # Print all outputs for visual inspection
    print("\n" + "=" * 60)
    print("ALL OUTPUTS (for visual inspection)")
    print("=" * 60)
    for exp in experiments:
        print(f"\n[Temp {exp['temperature']}]")
        for i, text in enumerate(exp["texts"], 1):
            print(f"  {i}. {text}")

    return analysis["conclusion"]


if __name__ == "__main__":
    conclusion = main()
    print(f"\n{'=' * 60}")
    print(f"FINAL RESULT: {conclusion}")
    print(f"{'=' * 60}")
