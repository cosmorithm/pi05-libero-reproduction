#!/usr/bin/env python3
"""Probe Pi0.5's *internal* PaliGemma stream as a direct VLM generator.

This is deliberately an ablation, not the supported Pi0.5 policy API.  It
loads the deployed Pi0.5 checkpoint, calls only
``paligemma_with_expert.paligemma.generate`` and never invokes the action
expert or flow-matching sampler.  Each result is written to JSONL immediately
so an interrupted GPU instance still leaves an auditable partial experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoProcessor

from lerobot.policies.pi05.modeling_pi05 import PI05Policy


def question_bank() -> list[dict[str, str]]:
    """Exactly 100 fixed English questions, grouped for later analysis."""
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
        "What is the main language spoken in Japan?",
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
    rows = ([{"category": "visual", "question": q} for q in visual]
            + [{"category": "general_language", "question": q} for q in general]
            + [{"category": "robot_reasoning", "question": q} for q in robot_reasoning])
    assert len(rows) == 100
    for i, row in enumerate(rows, start=1):
        row["id"] = f"q{i:03d}"
    return rows


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def text_metrics(token_ids: list[int], raw: str, clean: str) -> dict[str, Any]:
    nonspace = [ch for ch in clean if not ch.isspace()]
    printable = sum(ch.isprintable() for ch in nonspace)
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in nonspace)
    words = re.findall(r"[A-Za-z]+", clean.lower())
    common = Counter(words).most_common(1)
    most_common_ratio = (common[0][1] / len(words)) if words else 0.0
    return {
        "generated_tokens": len(token_ids),
        "characters_raw": len(raw),
        "characters_clean": len(clean),
        "word_count": len(words),
        "printable_ratio": round(printable / len(nonspace), 4) if nonspace else 0.0,
        "ascii_letter_ratio": round(ascii_letters / len(nonspace), 4) if nonspace else 0.0,
        "most_common_word_ratio": round(most_common_ratio, 4),
        "most_common_word": common[0][0] if common else None,
        "has_repeated_4gram": any(
            clean[i : i + 4] == clean[i + 4 : i + 8]
            for i in range(max(0, len(clean) - 7))
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--processor",
        type=Path,
        default=Path("assets/paligemma-processor"),
        help="Local PaliGemma tokenizer/processor directory (no model weights are downloaded).",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("This probe requires CUDA; no CUDA device is available.")
    if not args.checkpoint.is_dir():
        raise FileNotFoundError(args.checkpoint)
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    if not args.processor.is_dir():
        raise FileNotFoundError(
            f"PaliGemma processor not found: {args.processor}. "
            "Download only tokenizer/processor files to this local path first."
        )
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit must be in [1, 100]")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "results.jsonl"
    status_path = args.output_dir / "status.json"
    manifest_path = args.output_dir / "manifest.json"
    existing: set[str] = set()
    if args.resume and result_path.exists():
        for line in result_path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    elif result_path.exists():
        raise FileExistsError(f"{result_path} exists; use --resume or choose another directory")

    expected_image_tokens = 18 * 18  # Pi0.5 uses 256x256 images with 14px patches.
    image_sha256 = hashlib.sha256(args.image.read_bytes()).hexdigest()
    started = time.time()
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "purpose": "Direct VLM-generation ablation of Pi0.5 internal PaliGemma stream; action expert is not called.",
        "started_at_utc": now,
        "checkpoint": str(args.checkpoint.resolve()),
        "image": str(args.image.resolve()),
        "processor": str(args.processor.resolve()),
        "image_sha256": image_sha256,
        "questions_total": args.limit,
        "decoding": {"do_sample": False, "max_new_tokens": args.max_new_tokens, "use_cache": True},
        "prompt_template": "answer en {question}",
        "fixed_visual_context": True,
        "expected_image_tokens": expected_image_tokens,
    }
    write_json(manifest_path, manifest)
    write_json(status_path, {**manifest, "state": "loading", "completed": len(existing), "errors": 0})

    print("Loading Pi0.5 policy checkpoint …", flush=True)
    policy = PI05Policy.from_pretrained(
        args.checkpoint,
        device="cuda",
        local_files_only=True,
    )
    policy.eval()
    # Crucial ablation boundary: generation happens only through the pretrained VLM stream.
    vlm = policy.model.paligemma_with_expert.paligemma
    vlm.eval()
    print(f"Loaded VLM: {vlm.__class__.__name__}", flush=True)

    processor = AutoProcessor.from_pretrained(args.processor, local_files_only=True)
    # The cached processor originates from 224px PaliGemma.  Pi0.5 was instantiated at
    # 256px; update both geometry and image-token prefix so the VLM's visual features and
    # input image-token positions agree (18x18 = 324 tokens).
    processor.image_processor.size = {"height": 256, "width": 256}
    processor.image_processor.crop_size = {"height": 256, "width": 256}
    processor.image_seq_length = expected_image_tokens
    # This OpenPI port sets the legacy ``image_token_index`` during
    # construction, while recent Transformers reads ``image_token_id`` in the
    # generic PaliGemma forward path.  Normal Pi0.5 action inference bypasses
    # this generic path entirely; the explicit assignment makes this direct
    # VLM ablation use the same special token emitted by the processor.
    vlm.config.image_token_id = processor.image_token_id
    vlm.config.image_token_index = processor.image_token_id
    image = Image.open(args.image).convert("RGB")

    metadata = {
        **manifest,
        "state": "running",
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "vlm_class": vlm.__class__.__name__,
        "processor_class": processor.__class__.__name__,
        "vlm_image_size": int(vlm.config.vision_config.image_size),
        "vlm_image_token_id": int(vlm.config.image_token_id),
        "processor_image_token_id": int(processor.image_token_id),
        # This OpenPI-compatible PaliGemma config does not expose the newer
        # Transformers ``image_seq_length`` field.  The expected count is
        # recorded explicitly from the Pi0.5 256px/14px geometry instead.
        "vlm_image_seq_length": int(getattr(vlm.config, "image_seq_length", expected_image_tokens)),
    }
    write_json(manifest_path, metadata)

    errors = 0
    rows = question_bank()[: args.limit]
    for index, row in enumerate(rows, start=1):
        if row["id"] in existing:
            continue
        prompt = f"answer en {row['question']}"
        t0 = time.perf_counter()
        record: dict[str, Any] = {**row, "prompt": prompt}
        try:
            inputs = processor(images=image, text=prompt, return_tensors="pt")
            inputs = {key: value.to("cuda") for key, value in inputs.items()}
            with torch.inference_mode():
                output_ids = vlm.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
                    use_cache=True,
                    pad_token_id=processor.tokenizer.pad_token_id,
                    eos_token_id=processor.tokenizer.eos_token_id,
                )
            prompt_length = int(inputs["input_ids"].shape[1])
            completion_ids = output_ids[0, prompt_length:].detach().cpu().tolist()
            raw = processor.tokenizer.decode(completion_ids, skip_special_tokens=False)
            clean = clean_text(processor.tokenizer.decode(completion_ids, skip_special_tokens=True))
            record.update(
                {
                    "status": "ok",
                    "completion_token_ids": completion_ids,
                    "completion_raw": raw,
                    "completion_clean": clean,
                    "elapsed_s": round(time.perf_counter() - t0, 4),
                    "metrics": text_metrics(completion_ids, raw, clean),
                }
            )
        except Exception as exc:  # retain failures as experimental evidence
            errors += 1
            record.update(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "elapsed_s": round(time.perf_counter() - t0, 4),
                }
            )
        append_jsonl(result_path, record)
        completed = index
        write_json(
            status_path,
            {**metadata, "state": "running", "completed": completed, "errors": errors, "last_id": row["id"], "elapsed_s": round(time.time() - started, 2)},
        )
        print(f"[{index:03d}/{len(rows):03d}] {row['id']} {record['status']} {record.get('completion_clean', record.get('error', ''))[:140]}", flush=True)

    final_state = "complete" if errors == 0 else "complete_with_errors"
    write_json(
        status_path,
        {**metadata, "state": final_state, "completed": len(rows), "errors": errors, "elapsed_s": round(time.time() - started, 2), "finished_at_utc": datetime.now(timezone.utc).isoformat()},
    )
    print(f"Finished: {len(rows)} prompts, {errors} errors, elapsed={time.time() - started:.1f}s", flush=True)
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
