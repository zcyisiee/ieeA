#!/usr/bin/env python3
"""Probe OpenRouter concurrency behavior and compare integration paths.

Usage:
  PYTHONPATH=src python scripts/openrouter_concurrency_probe.py \
    --key <API_KEY> \
    --model openai/gpt-5-mini \
    --endpoint https://openrouter.ai/api/v1/chat/completions \
    --concurrency 100 \
    --requests 100 \
    --output debug/openrouter_probe_20260207.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

import httpx

try:
    import openai
except Exception:  # pragma: no cover - runtime dependency
    openai = None


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: float
    status_code: Optional[int] = None
    error: Optional[str] = None


def _normalize_openai_base_url(endpoint: str) -> str:
    suffix = "/chat/completions"
    if endpoint.endswith(suffix):
        return endpoint[: -len(suffix)]
    return endpoint


def _short_error(err: Exception) -> str:
    text = f"{type(err).__name__}: {err}"
    return text[:240]


def _summarize(results: List[ProbeResult]) -> Dict[str, Any]:
    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    status_hist = Counter(str(r.status_code) for r in results if r.status_code is not None)
    err_hist = Counter(r.error for r in fail if r.error)
    latencies = [r.latency_ms for r in ok]
    return {
        "total": len(results),
        "success": len(ok),
        "failed": len(fail),
        "success_rate": round(len(ok) / len(results), 4) if results else 0.0,
        "latency_ms_avg": round(mean(latencies), 2) if latencies else None,
        "latency_ms_p95": (
            round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2)
            if latencies
            else None
        ),
        "status_histogram": dict(status_hist),
        "error_histogram": dict(err_hist.most_common(8)),
    }


async def probe_raw_http(
    *,
    endpoint: str,
    key: str,
    model: str,
    requests: int,
    concurrency: int,
    timeout_s: float,
    max_tokens: int,
) -> Dict[str, Any]:
    sem = asyncio.Semaphore(concurrency)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply exactly: OK"}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        results: List[ProbeResult] = []

        async def one_call() -> None:
            async with sem:
                t0 = time.perf_counter()
                try:
                    resp = await client.post(endpoint, headers=headers, json=payload)
                    dt = (time.perf_counter() - t0) * 1000
                    if resp.status_code == 200:
                        results.append(ProbeResult(ok=True, latency_ms=dt, status_code=200))
                    else:
                        body = resp.text[:180].replace("\n", " ")
                        results.append(
                            ProbeResult(
                                ok=False,
                                latency_ms=dt,
                                status_code=resp.status_code,
                                error=f"HTTP {resp.status_code}: {body}",
                            )
                        )
                except Exception as e:
                    dt = (time.perf_counter() - t0) * 1000
                    results.append(
                        ProbeResult(ok=False, latency_ms=dt, error=_short_error(e))
                    )

        await asyncio.gather(*(one_call() for _ in range(requests)))
        return _summarize(results)


async def probe_openai_sdk(
    *,
    base_url: str,
    key: str,
    model: str,
    requests: int,
    concurrency: int,
    timeout_s: float,
    max_tokens: int,
) -> Dict[str, Any]:
    if openai is None:
        return {"error": "openai package not available"}

    timeout_cfg = openai.Timeout(connect=30.0, read=timeout_s, write=30.0, pool=30.0)
    client = openai.AsyncOpenAI(api_key=key, base_url=base_url, timeout=timeout_cfg)
    sem = asyncio.Semaphore(concurrency)
    results: List[ProbeResult] = []

    async def one_call() -> None:
        async with sem:
            t0 = time.perf_counter()
            try:
                await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply exactly: OK"}],
                    temperature=0,
                    max_tokens=max_tokens,
                )
                dt = (time.perf_counter() - t0) * 1000
                results.append(ProbeResult(ok=True, latency_ms=dt, status_code=200))
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                status = getattr(e, "status_code", None)
                results.append(
                    ProbeResult(
                        ok=False,
                        latency_ms=dt,
                        status_code=status,
                        error=_short_error(e),
                    )
                )

    try:
        await asyncio.gather(*(one_call() for _ in range(requests)))
    finally:
        await client.close()
    return _summarize(results)


async def main_async(args: argparse.Namespace) -> Dict[str, Any]:
    normalized_base = _normalize_openai_base_url(args.endpoint)

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    result: Dict[str, Any] = {
        "started_at": started,
        "input": {
            "model": args.model,
            "endpoint": args.endpoint,
            "normalized_openai_base_url": normalized_base,
            "requests": args.requests,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
            "max_tokens": args.max_tokens,
        },
        "probes": {},
    }

    print("[1/3] Probing raw HTTP endpoint...")
    result["probes"]["raw_http"] = await probe_raw_http(
        endpoint=args.endpoint,
        key=args.key,
        model=args.model,
        requests=args.requests,
        concurrency=args.concurrency,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
    )

    print("[2/3] Probing OpenAI SDK with project-style base_url (as-is endpoint)...")
    result["probes"]["openai_sdk_as_is"] = await probe_openai_sdk(
        base_url=args.endpoint,
        key=args.key,
        model=args.model,
        requests=args.requests,
        concurrency=args.concurrency,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
    )

    print("[3/3] Probing OpenAI SDK with normalized base_url...")
    result["probes"]["openai_sdk_normalized"] = await probe_openai_sdk(
        base_url=normalized_base,
        key=args.key,
        model=args.model,
        requests=args.requests,
        concurrency=args.concurrency,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
    )

    result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenRouter concurrency probe.")
    parser.add_argument("--key", required=True, help="OpenRouter API key")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--endpoint", required=True, help="OpenRouter endpoint URL")
    parser.add_argument("--requests", type=int, default=100, help="Total requests per probe")
    parser.add_argument(
        "--concurrency", type=int, default=100, help="Concurrent requests per probe"
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="Read timeout seconds per request"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=32,
        help="max_tokens used per request (OpenRouter often requires >=16)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debug/openrouter_concurrency_probe.json"),
        help="Output JSON report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(main_async(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Probe Summary ===")
    print(json.dumps(report["probes"], ensure_ascii=False, indent=2))
    print(f"\nReport saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
