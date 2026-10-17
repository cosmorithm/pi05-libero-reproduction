#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/root/autodl-tmp/pi05-libero-reproduction
VENV_ROOT="$PROJECT_ROOT/.venv"
LEROBOT_ROOT="$PROJECT_ROOT/lerobot"
LEROBOT_COMMIT="$(tr -d '[:space:]' < "$PROJECT_ROOT/LEROBOT_COMMIT")"

export DEBIAN_FRONTEND=noninteractive
export PIP_CACHE_DIR="$PROJECT_ROOT/cache/pip"
export HF_HOME="$PROJECT_ROOT/cache/huggingface"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=600
export HF_HUB_ETAG_TIMEOUT=60
export HOME="$PROJECT_ROOT/home"
export MUJOCO_GL=egl

mkdir -p \
  "$PROJECT_ROOT/cache/pip" \
  "$PROJECT_ROOT/cache/huggingface" \
  "$PROJECT_ROOT/assets" \
  "$PROJECT_ROOT/datasets" \
  "$PROJECT_ROOT/home/.libero" \
  "$PROJECT_ROOT/logs" \
  "$PROJECT_ROOT/outputs/smoke"

apt-get update
apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  curl \
  ffmpeg \
  libegl1 \
  libgl1 \
  libgles2 \
  libglew2.2 \
  libglfw3 \
  libosmesa6 \
  libsm6 \
  libxext6 \
  libxrender1 \
  pkg-config

if [[ ! -f "$LEROBOT_ROOT/pyproject.toml" ]]; then
  archive="$PROJECT_ROOT/cache/lerobot-$LEROBOT_COMMIT.tar.gz"
  staging="$(mktemp -d "$PROJECT_ROOT/cache/lerobot.extract.XXXXXX")"
  echo "Downloading LeRobot source at $LEROBOT_COMMIT from GitHub codeload"
  curl --fail --location \
    --retry 8 --retry-all-errors --retry-delay 5 \
    --output "$archive.part" \
    "https://codeload.github.com/huggingface/lerobot/tar.gz/$LEROBOT_COMMIT"
  mv "$archive.part" "$archive"
  tar -xzf "$archive" --strip-components=1 -C "$staging"
  printf '%s\n' "$LEROBOT_COMMIT" > "$staging/.source-commit"
  mv "$staging" "$LEROBOT_ROOT"
fi

if [[ -f "$LEROBOT_ROOT/.source-commit" ]] && \
   [[ "$(tr -d '[:space:]' < "$LEROBOT_ROOT/.source-commit")" != "$LEROBOT_COMMIT" ]]; then
  echo "LeRobot source commit does not match LEROBOT_COMMIT" >&2
  exit 1
fi

if [[ ! -x "$VENV_ROOT/bin/python" ]]; then
  /root/miniconda3/bin/python -m venv "$VENV_ROOT"
fi

"$VENV_ROOT/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV_ROOT/bin/python" -m pip install \
  'setuptools<82' \
  filelock \
  typing-extensions \
  sympy \
  networkx \
  jinja2 \
  fsspec \
  numpy \
  pillow \
  mpmath \
  MarkupSafe \
  'cuda-bindings>=12.9.4,<13' \
  'cuda-pathfinder~=1.1'
"$VENV_ROOT/bin/python" -m pip install \
  --index-url https://download.pytorch.org/whl/cu128 \
  'torch==2.11.0+cu128' 'torchvision==0.26.0+cu128'
"$VENV_ROOT/bin/python" -m pip install -e "$LEROBOT_ROOT[pi,libero,evaluation]"

"$VENV_ROOT/bin/python" - <<'PY'
import json
from importlib.util import find_spec
from pathlib import Path

from huggingface_hub import snapshot_download

assets = Path("/root/autodl-tmp/pi05-libero-reproduction/assets")

try:
    snapshot_download(
        repo_id="lerobot/libero-assets",
        repo_type="dataset",
        local_dir=assets,
        # hf-mirror.com rate-limits bursts; one worker is slower but reliable.
        max_workers=1,
    )
except Exception as exc:
    print(f"Asset mirror request ended with: {exc}")

# Validate against huggingface_hub's cached repository tree. A mirror may return
# HTTP 429 while revalidating an already complete local_dir, so the local
# manifest is the source of truth before failing the setup.
trees = sorted((assets / ".cache" / "huggingface" / "trees").glob("*.json"))
if not trees:
    raise RuntimeError("LIBERO asset manifest is missing; rerun after mirror cooldown")
manifest = json.loads(trees[-1].read_text(encoding="utf-8"))
files = manifest["files"]
bad = []
for relative_path, metadata in files.items():
    path = assets / relative_path
    expected_size = metadata.get("size")
    if not path.is_file() or (expected_size is not None and path.stat().st_size != expected_size):
        bad.append(relative_path)
if bad:
    raise RuntimeError(
        f"LIBERO assets are incomplete ({len(bad)}/{len(files)} bad); "
        f"first entries: {bad[:10]}"
    )
print(f"Validated {len(files)} LIBERO asset files in {assets}")

# hf-libero 0.1.4's get_assets_path() does not consult config.yaml. Point the
# package's expected assets location at persistent autodl-tmp storage.
spec = find_spec("libero.libero")
if spec is None or spec.origin is None:
    raise RuntimeError("Could not locate the installed libero.libero package")
package_assets = Path(spec.origin).parent / "assets"
if package_assets.is_symlink() and package_assets.resolve() != assets.resolve():
    package_assets.unlink()
if not package_assets.exists():
    package_assets.symlink_to(assets, target_is_directory=True)
print(f"LIBERO package assets: {package_assets} -> {package_assets.resolve()}")
PY

"$VENV_ROOT/bin/python" "$PROJECT_ROOT/scripts/smoke_libero.py"

