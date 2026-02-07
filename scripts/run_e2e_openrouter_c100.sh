#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/run_e2e_openrouter_c100.sh <OPENROUTER_KEY> [ARXIV_ID]
#
# Example:
#   bash scripts/run_e2e_openrouter_c100.sh sk-or-v1-xxx 2504.19793

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/run_e2e_openrouter_c100.sh <OPENROUTER_KEY> [ARXIV_ID]"
  exit 1
fi

KEY="$1"
ARXIV_ID="${2:-2504.19793}"
MODEL="openai/gpt-5-mini"
ENDPOINT="https://openrouter.ai/api/v1/chat/completions"
CONCURRENCY=100
REQUESTS=100
TIMEOUT=60
MAX_RETRY=5
TS="$(date +%Y%m%d_%H%M%S)"

OUT_ROOT="output/gpt5mini_openrouter_e2e_c100_${TS}"
PAPER_DIR="${OUT_ROOT}/${ARXIV_ID}"
PROBE_REPORT="debug/openrouter_concurrency_probe_${TS}.json"

echo "== [1/3] OpenRouter 并发探针（${CONCURRENCY} 并发 / ${REQUESTS} 请求） =="
PYTHONPATH=src python scripts/openrouter_concurrency_probe.py \
  --key "${KEY}" \
  --model "${MODEL}" \
  --endpoint "${ENDPOINT}" \
  --requests "${REQUESTS}" \
  --concurrency "${CONCURRENCY}" \
  --timeout "${TIMEOUT}" \
  --max-tokens 32 \
  --output "${PROBE_REPORT}"

echo
echo "== [2/3] 全流程翻译测试（模块入口，${CONCURRENCY} 并发） =="
ok=0
for i in $(seq 1 "${MAX_RETRY}"); do
  RUN_LOG="${OUT_ROOT}/run_attempt_${i}.log"
  mkdir -p "${OUT_ROOT}"
  echo "-- Attempt ${i}/${MAX_RETRY}"
  if PYTHONPATH=src python -m ieeA.cli translate "${ARXIV_ID}" \
      --output-dir "${OUT_ROOT}" \
      --model "${MODEL}" \
      --endpoint "${ENDPOINT}" \
      --key "${KEY}" \
      --concurrency "${CONCURRENCY}" 2>&1 | tee "${RUN_LOG}"; then
    ok=1
    break
  fi
  echo "Attempt ${i} failed, retrying..."
done

if [[ "${ok}" -ne 1 ]]; then
  echo
  echo "E2E failed after ${MAX_RETRY} attempts."
  echo "Probe report: ${PROBE_REPORT}"
  echo "Run logs: ${OUT_ROOT}/run_attempt_*.log"
  exit 2
fi

echo
echo "== [3/3] 结果汇总 =="
echo "Probe report: ${PROBE_REPORT}"
echo "Output root: ${OUT_ROOT}"
echo "Paper dir: ${PAPER_DIR}"

if [[ -d "${PAPER_DIR}" ]]; then
  echo
  echo "-- Key files --"
  ls -1 "${PAPER_DIR}" | rg -n "translation_state|translation_log|main_translated|\\.pdf$" || true

  LATEST_LOG="$(ls -1t "${PAPER_DIR}"/translation_log_*.json 2>/dev/null | head -n 1 || true)"
  if [[ -n "${LATEST_LOG}" ]]; then
    echo
    echo "-- Latest translation log --"
    echo "${LATEST_LOG}"
  fi
fi

echo
echo "Done."
