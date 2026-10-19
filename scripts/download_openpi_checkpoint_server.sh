#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/pi05-libero-reproduction
DEST="$PROJECT/checkpoints/openpi-pi05-libero"
API="https://storage.googleapis.com/storage/v1/b/openpi-assets/o?prefix=checkpoints%2Fpi05_libero%2F&maxResults=1000"
MANIFEST=/tmp/openpi_pi05_libero_manifest.tsv
LISTING=/tmp/openpi_pi05_libero_listing.json

cd "$PROJECT"
curl -4 --fail --retry 10 --retry-all-errors -sS "$API" -o "$LISTING"
.venv/bin/python - "$LISTING" "$MANIFEST" <<'PY'
import json
import sys

source, target = sys.argv[1:3]
with open(source, encoding="utf-8") as handle:
    payload = json.load(handle)
with open(target, "w", encoding="utf-8") as handle:
    for item in payload["items"]:
        name = item["name"]
        if "size" not in item:
            continue
        relative = name.removeprefix("checkpoints/pi05_libero/")
        handle.write(f"{relative}\t{item['size']}\t{item.get('md5Hash') or '-'}\n")
PY

download_one() {
  local relative="$1"
  local expected_size="$2"
  local expected_md5="$3"
  local output="$DEST/$relative"
  local url="https://storage.googleapis.com/openpi-assets/checkpoints/pi05_libero/$relative"
  mkdir -p "$(dirname "$output")"
  if [ -f "$output" ] && [ "$(stat -c %s "$output")" = "$expected_size" ]; then
    if [ "$expected_md5" = "-" ]; then
      echo "skip complete: $relative"
      return
    fi
    local skipped_md5
    skipped_md5=$(openssl dgst -md5 -binary "$output" | base64 -w0)
    if [ "$skipped_md5" = "$expected_md5" ]; then
      echo "skip verified: $relative"
      return
    fi
  fi
  echo "download: $relative ($expected_size bytes)"
  curl -4 -L --fail --retry 10 --retry-delay 2 --retry-all-errors \
    --create-dirs -C - -o "$output" "$url"
  local actual_size
  actual_size=$(stat -c %s "$output")
  if [ "$actual_size" != "$expected_size" ]; then
    echo "size mismatch: $relative expected=$expected_size actual=$actual_size" >&2
    return 1
  fi
  if [ "$expected_md5" != "-" ]; then
    local actual_md5
    actual_md5=$(openssl dgst -md5 -binary "$output" | base64 -w0)
    if [ "$actual_md5" != "$expected_md5" ]; then
      echo "md5 mismatch: $relative expected=$expected_md5 actual=$actual_md5" >&2
      return 1
    fi
  fi
  echo "verified: $relative"
}
export -f download_one
export DEST

if ! cat "$MANIFEST" | xargs -r -P 4 -n 3 bash -c 'download_one "$0" "$1" "$2"'; then
  echo "OPENPI_CHECKPOINT_DOWNLOAD_FAILED" >&2
  exit 1
fi
echo "OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE"
