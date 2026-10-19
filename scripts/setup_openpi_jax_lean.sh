#!/usr/bin/env bash
# Build a JAX-only OpenPI runtime without changing the verified LeRobot .venv.
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

venv=.venv-openpi-lean
base_python=.venv/bin/python
base_site=$($base_python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
pip=("$venv/bin/python" -m pip)

if [[ ! -x "$venv/bin/python" ]]; then
  "$base_python" -m venv "$venv"
fi

"${pip[@]}" install --upgrade pip

# Install only the packages imported by the direct VLM checkpoint probe.  In
# particular, do not install OpenPI's pinned torch==2.7.1, TensorFlow, gym-aloha
# or LeRobot: torch/vision are read from the verified base environment at runtime.
"${pip[@]}" install --cache-dir "$project_root/cache/pip" \
  --constraint scripts/openpi_jax_lean_constraints.txt \
  'numpy>=1.22.4,<2.0.0' \
  'jax[cuda12]==0.5.3' 'flax==0.10.2' 'orbax-checkpoint==0.11.13' \
  'augmax>=0.3.4' 'dm-tree>=0.1.8' 'einops>=0.8.0' 'equinox>=0.11.8' \
  'flatbuffers>=24.3.25' 'fsspec[gcs]>=2024.6.0' 'imageio>=2.36.1' \
  'jaxtyping==0.2.36' 'ml_collections==1.0.0' 'numpydantic>=1.6.6' \
  'opencv-python>=4.10.0.84' 'pillow>=11.0.0' 'sentencepiece>=0.2.0' \
  'tqdm-loggable>=0.2' 'typing-extensions>=4.12.2' 'tyro>=0.9.5' \
  'wandb>=0.19.1' 'filelock>=3.16.1' 'beartype==0.19.0' 'chex==0.1.90' \
  'treescope>=0.1.7' 'transformers==4.53.2' 'rich>=14.0.0' 'polars>=1.30.0' \
  'websockets>=11.0' safetensors

"${pip[@]}" install --no-deps -e third_party/openpi/packages/openpi-client -e third_party/openpi

# The isolated environment shadows only the packages above.  It reads the
# working Torch/CUDA runtime from .venv without modifying it.  A .pth entry is
# appended after the lean site-packages, so the lean NumPy/Transformers pins win.
lean_site=$("$venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
printf '%s\n' "$base_site" > "$lean_site/zz_verified_lerobot_base.pth"

"$venv/bin/python" - <<'PY'
import flax
import jax
import openpi
import orbax.checkpoint
import torch
import numpy
import transformers
print({
    "jax": jax.__version__,
    "numpy": numpy.__version__,
    "torch_from_base": torch.__version__,
    "transformers": transformers.__version__,
})
PY
