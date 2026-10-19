#!/usr/bin/env python3
"""Direct language-generation probe for the official OpenPI JAX pi05_libero model.

This is an ablation, not a supported OpenPI inference API. It keeps the
Pi0.5 PaliGemma visual-language stream, skips the action expert and flow
matching sampler, and greedily decodes text tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
from PIL import Image
import sentencepiece

from openpi.models import gemma as _gemma
from openpi.models import model as _model
from openpi.models import pi0 as _pi0
from openpi.models import tokenizer as _tokenizer
from openpi.shared import image_tools
from openpi.training import config as _config


ROOT = Path("/root/autodl-tmp/pi05-libero-reproduction")
DEFAULT_CHECKPOINT = ROOT / "checkpoints" / "openpi-pi05-libero"
DEFAULT_IMAGE = ROOT / "outputs" / "smoke" / "image.png"
DEFAULT_TOKENIZER = ROOT / "assets" / "paligemma-processor" / "tokenizer.model"


def question_bank() -> list[dict[str, str]]:
    visual = [
        "What objects are visible in this image?",
        "Is a robot arm visible in this image?",
        "Describe the scene in one short sentence.",
        "What is the most prominent object in the image?",
        "Is there a table or a countertop in the image?",
        "Are there any bowls, cups, or plates visible?",
        "What color is the largest object in the image?",
        "How many distinct objects can you identify?",
        "Is the scene indoors or outdoors?",
        "What is on the left side of the image?",
        "What is on the right side of the image?",
        "What is near the center of the image?",
        "Is the gripper open or closed?",
        "Where is the robot gripper relative to the table?",
        "Is there an object close to the gripper?",
        "What could the robot interact with next?",
        "What material does the main surface appear to be?",
        "Is the camera looking down at the scene or across it?",
        "Is the workspace cluttered or mostly clear?",
        "Which object appears closest to the camera?",
        "Which object appears farthest from the camera?",
        "Are any objects stacked on top of each other?",
        "Is there an empty container in the scene?",
        "Is the image bright or dark?",
        "What colors are most common in the image?",
        "Is the robot arm above the workspace?",
        "Can you identify a movable object?",
        "Can you identify a target location for an object?",
        "Would moving the closest object require grasping it?",
        "Is the scene suitable for a pick-and-place task?",
        "What should a robot avoid colliding with in this scene?",
        "Is there a visible background behind the workspace?",
        "Does the image show a single workspace or multiple workspaces?",
        "What is the likely purpose of the robot in this image?",
        "What visual evidence suggests this is a robot-manipulation scene?",
    ]
    general = [
        "What is 2 plus 2?",
        "What is the capital of France?",
        "How many days are there in a week?",
        "Which is larger, 9 or 6?",
        "What color do blue and yellow make when mixed?",
        "What is the opposite of hot?",
        "Complete the sequence: 2, 4, 6, 8, ?",
        "How many sides does a triangle have?",
        "What does CPU stand for?",
        "What is the first month of the year?",
        "Which animal says meow?",
        "What is water made of?",
        "What is the square root of 16?",
        "Which planet is known as the Red Planet?",
        "How many minutes are in one hour?",
        "What is a synonym for happy?",
        "Which number comes after 99?",
        "What is the main language spoken by a person in Japan?",
        "What is the freezing point of water in Celsius?",
        "What shape has four equal sides?",
        "What is the opposite of left?",
        "How many letters are in the English alphabet?",
        "What do bees make?",
        "Which season comes after spring?",
        "What is 10 minus 3?",
        "What do you call a baby dog?",
        "What is the largest ocean on Earth?",
        "Which gas do plants absorb from the air?",
        "What is the past tense of run?",
        "What is a book used for?",
        "Which is a fruit: apple, chair, or pencil?",
        "What is the next day after Monday?",
        "How many seconds are in one minute?",
        "What is the opposite of empty?",
        "What does URL stand for?",
    ]
    robot_reasoning = [
        "What is the first safe step before picking up an object?",
        "Why should a robot open its gripper before a grasp?",
        "What should a robot do after it reaches above an object?",
        "How can a robot avoid knocking over a cup?",
        "What does pick and place mean in robotics?",
        "Why is a stable grasp important?",
        "What should a robot check before closing its gripper?",
        "How should a robot move a fragile object?",
        "Why is collision avoidance useful for a robot arm?",
        "What should happen after an object is placed at the goal?",
        "How can a robot tell whether a grasp failed?",
        "What is a waypoint in robot motion planning?",
        "Why does a robot need a camera for manipulation?",
        "What is the difference between a grasp and a push?",
        "When should a robot slow down during a task?",
        "Why should a robot keep an object level while carrying it?",
        "What is a robot workspace?",
        "What information does a gripper state provide?",
        "How can a robot recover after missing an object?",
        "Why is depth useful for picking an object?",
        "What should a robot do if an obstacle blocks the path?",
        "What makes a placement successful?",
        "Why can a top-down grasp be easier than a side grasp?",
        "What is visual servoing?",
        "How can a robot verify that a container is empty?",
        "Why should a robot avoid moving too fast near a target?",
        "What is the role of an action policy in a robot?",
        "How does a language instruction help a robot?",
        "What is a safe way to move an object across a table?",
        "Why might a robot need to re-observe a scene during a task?",
    ]
    rows = (
        [{"category": "visual", "question": q} for q in visual]
        + [{"category": "general_language", "question": q} for q in general]
        + [{"category": "robot_reasoning", "question": q} for q in robot_reasoning]
    )
    assert len(rows) == 100
    for index, row in enumerate(rows, start=1):
        row["id"] = f"q{index:03d}"
    return rows


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def text_metrics(token_ids: list[int], raw: str, clean: str) -> dict[str, Any]:
    nonspace = [ch for ch in clean if not ch.isspace()]
    printable = sum(ch.isprintable() for ch in nonspace)
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in nonspace)
    words = re.findall(r"[A-Za-z]+", clean.lower())
    common = Counter(words).most_common(1)
    return {
        "generated_tokens": len(token_ids),
        "characters_raw": len(raw),
        "characters_clean": len(clean),
        "word_count": len(words),
        "printable_ratio": round(printable / len(nonspace), 4) if nonspace else 0.0,
        "ascii_letter_ratio": round(ascii_letters / len(nonspace), 4) if nonspace else 0.0,
        "most_common_word_ratio": round(common[0][1] / len(words), 4) if words else 0.0,
        "most_common_word": common[0][0] if common else None,
        "has_repeated_4gram": any(
            clean[index : index + 4] == clean[index + 4 : index + 8]
            for index in range(max(0, len(clean) - 7))
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def local_tokenizer(model_file: Path, max_len: int) -> _tokenizer.PaligemmaTokenizer:
    tokenizer = _tokenizer.PaligemmaTokenizer.__new__(_tokenizer.PaligemmaTokenizer)
    tokenizer._max_len = max_len
    tokenizer._tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(model_file))
    return tokenizer


def prepare_image(path: Path, flip: bool) -> jax.Array:
    image = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    if flip:
        image = np.ascontiguousarray(image[::-1, ::-1])
    resized = image_tools.resize_with_pad(image, *_model.IMAGE_RESOLUTION)
    return (resized.astype(jnp.float32) / 127.5 - 1.0)[None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--tokenizer-model", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--prompt-template", default="answer en {question}")
    parser.add_argument("--no-flip-image", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be in [1, 100]")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be positive")
    return args


def main() -> int:
    args = parse_args()
    if not (args.checkpoint / "params").is_dir():
        raise FileNotFoundError(args.checkpoint / "params")
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    if not args.tokenizer_model.is_file():
        raise FileNotFoundError(args.tokenizer_model)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    status_path = args.output_dir / "status.json"
    manifest_path = args.output_dir / "manifest.json"
    existing: set[str] = set()
    if args.resume and results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    elif results_path.exists():
        raise FileExistsError(f"{results_path} exists; use --resume or choose another directory")

    image_hash = hashlib.sha256(args.image.read_bytes()).hexdigest()
    manifest = {
        "purpose": "Direct text-generation ablation of the official OpenPI JAX pi05_libero PaliGemma stream.",
        "checkpoint": str(args.checkpoint.resolve()),
        "image": str(args.image.resolve()),
        "image_sha256": image_hash,
        "tokenizer_model": str(args.tokenizer_model.resolve()),
        "questions_total": args.limit,
        "prompt_template": args.prompt_template,
        "image_flip_180": not args.no_flip_image,
        "decoding": {"do_sample": False, "max_new_tokens": args.max_new_tokens},
        "action_expert_called": False,
        "flux_matching_called": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(manifest_path, manifest)
    write_json(status_path, {**manifest, "state": "loading", "completed": len(existing), "errors": 0})

    train_config = _config.get_config("pi05_libero")
    print("Restoring OpenPI JAX params ...", flush=True)
    params = _model.restore_params(args.checkpoint / "params", dtype=jnp.bfloat16)
    model = train_config.model.load(params)
    print("Model loaded", flush=True)

    tokenizer = local_tokenizer(args.tokenizer_model, train_config.model.max_token_len)
    image = prepare_image(args.image, flip=not args.no_flip_image)
    image_tokens, _ = model.PaliGemma.img(image, train=False)
    image_len = int(image_tokens.shape[1])
    print(f"image_tokens={image_len}", flush=True)

    # The OpenPI Gemma trunk exposes tied-embedding input projection, but no
    # language-model method. Add a probe-only method that uses the same tied
    # embedding table for the output logits.
    if not hasattr(_gemma.Module, "decode"):
        def _decode(self, hidden):
            return self.embedder.decode(hidden)

        _gemma.Module.decode = _decode

    prefix_len = image_len + train_config.model.max_token_len
    max_total_len = prefix_len + args.max_new_tokens

    def make_prefix(prompt: str):
        tokens, token_mask = tokenizer.tokenize(prompt, state=None)
        tokens_array = jnp.asarray(tokens)[None]
        mask_array = jnp.asarray(token_mask)[None]
        text_tokens = model.PaliGemma.llm(tokens_array, method="embed")
        prefix = jnp.concatenate([image_tokens, text_tokens], axis=1)
        prefix_mask = jnp.concatenate(
            [jnp.ones((1, image_len), dtype=jnp.bool_), mask_array], axis=1
        )
        return prefix, prefix_mask, tokens, token_mask

    @jax.jit
    def forward(embeddings, input_mask):
        ar_mask = jnp.concatenate(
            [jnp.zeros((prefix_len,), dtype=jnp.bool_), jnp.ones((args.max_new_tokens,), dtype=jnp.bool_)]
        )
        attn_mask = _pi0.make_attn_mask(input_mask, ar_mask[None])
        positions = jnp.cumsum(input_mask, axis=1) - 1
        output, _ = model.PaliGemma.llm(
            [embeddings, None], mask=attn_mask, positions=positions
        )
        return output

    @jax.jit
    def token_embedding(token):
        return model.PaliGemma.llm(jnp.asarray([[token]], dtype=jnp.int32), method="embed")

    @jax.jit
    def logits_from_hidden(hidden):
        return model.PaliGemma.llm(hidden[None, None], method="decode")

    def generate(prompt: str):
        prefix, prefix_mask, _, token_mask = make_prefix(prompt)
        embeddings = jnp.zeros((1, max_total_len, prefix.shape[-1]), dtype=prefix.dtype)
        embeddings = embeddings.at[:, :prefix_len].set(prefix)
        input_mask = jnp.zeros((1, max_total_len), dtype=jnp.bool_)
        input_mask = input_mask.at[:, :prefix_len].set(prefix_mask)
        generated: list[int] = []
        last_index = image_len + int(np.asarray(token_mask).sum()) - 1
        for step in range(args.max_new_tokens):
            output = forward(embeddings, input_mask)
            last_hidden = output[:, last_index, :]
            logits = logits_from_hidden(last_hidden)
            token = int(jnp.argmax(logits[0, 0]))
            generated.append(token)
            embeddings = embeddings.at[:, prefix_len + step, :].set(token_embedding(token))
            input_mask = input_mask.at[:, prefix_len + step].set(True)
            last_index = prefix_len + step
        return generated

    errors = 0
    rows = question_bank()[: args.limit]
    started = time.time()
    for index, row in enumerate(rows, start=1):
        if row["id"] in existing:
            continue
        prompt = args.prompt_template.format(question=row["question"])
        record: dict[str, Any] = {**row, "prompt": prompt}
        token_started = time.time()
        try:
            completion_ids = generate(prompt)
            raw = tokenizer._tokenizer.decode(completion_ids)
            clean = clean_text(raw)
            record.update(
                {
                    "status": "ok",
                    "completion_token_ids": completion_ids,
                    "completion_raw": raw,
                    "completion_clean": clean,
                    "elapsed_s": round(time.time() - token_started, 4),
                    "metrics": text_metrics(completion_ids, raw, clean),
                }
            )
        except Exception as exc:
            errors += 1
            record.update(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "elapsed_s": round(time.time() - token_started, 4),
                }
            )
        append_jsonl(results_path, record)
        write_json(
            status_path,
            {
                **manifest,
                "state": "running",
                "completed": index,
                "errors": errors,
                "last_id": row["id"],
                "elapsed_s": round(time.time() - started, 2),
                "vlm_image_size": _model.IMAGE_RESOLUTION[0],
                "vlm_image_tokens": image_len,
                "jax": jax.__version__,
            },
        )
        print(f"[{index:03d}/{len(rows):03d}] {row['id']} {record['status']}", flush=True)

    final_state = "complete" if errors == 0 else "complete_with_errors"
    write_json(
        status_path,
        {
            **manifest,
            "state": final_state,
            "completed": len(rows),
            "errors": errors,
            "elapsed_s": round(time.time() - started, 2),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "vlm_image_size": _model.IMAGE_RESOLUTION[0],
            "vlm_image_tokens": image_len,
            "jax": jax.__version__,
        },
    )
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
