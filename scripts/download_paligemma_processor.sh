#!/usr/bin/env bash
# Download only PaliGemma's small tokenizer/processor files for the Pi0.5 VLM
# probe.  This intentionally excludes any base model weights.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
export HF_HOME="${HF_HOME:-$PROJECT_ROOT/cache/huggingface}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="google/paligemma-3b-pt-224",
    allow_patterns=[
        "config.json",
        "preprocessor_config.json",
        "processor_config.json",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
        "chat_template.json",
    ],
    local_dir="assets/paligemma-processor",
    token=True,
)
PY

echo "PaliGemma processor available at assets/paligemma-processor"
