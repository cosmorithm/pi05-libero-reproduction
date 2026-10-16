#!/usr/bin/env python3
import argparse
import io
import json
import math
import os
import platform
import time
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("LIBERO_CONFIG_PATH", "/root/autodl-tmp/pi05-libero-reproduction/home/.libero")

import numpy as np
import torch
from PIL import Image

import gymnasium
import mujoco
from libero.libero import get_assets_path
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env


ROOT = Path("/root/autodl-tmp/pi05-libero-reproduction")
OUTPUT = ROOT / "outputs" / "smoke"
PROGRESS = OUTPUT / "progress.json"
POLICY_CAMERA_NAMES = ("agentview_image", "robot0_eye_in_hand_image")
POLICY_CAMERA_MAPPING = {
    "agentview_image": "image",
    "robot0_eye_in_hand_image": "image2",
}
EXTRA_CAMERA_MAPPING = {
    "galleryview": "image3",
    "birdview": "image4",
    "frontview": "image5",
    "sideview": "image6",
    "robot0_robotview": "image7",
}
OUTPUT_CAMERA_MAPPING = {**POLICY_CAMERA_MAPPING, **EXTRA_CAMERA_MAPPING}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small headless LIBERO episode")
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--step-delay", type=float, default=0.0)
    parser.add_argument("--action-mode", choices=("idle", "demo"), default="idle")
    parser.add_argument("--image-every", type=int, default=1)
    args = parser.parse_args()
    if args.steps < 1 or args.steps > 1000:
        parser.error("--steps must be between 1 and 1000")
    if args.step_delay < 0 or args.step_delay > 1:
        parser.error("--step-delay must be between 0 and 1 second")
    if args.image_every < 1 or args.image_every > 100:
        parser.error("--image-every must be between 1 and 100")
    return args


def save_images(observation: dict, inner_env) -> dict[str, list[int]]:
    image_shapes = {}
    images = {name: np.asarray(batch[0]) for name, batch in observation["pixels"].items()}
    # hf-libero only includes the two policy cameras in observations. Render
    # the five human-monitoring views directly from the same MuJoCo state.
    sim = inner_env._env.sim
    for camera_name, output_name in EXTRA_CAMERA_MAPPING.items():
        # Direct MuJoCo rendering uses an OpenGL bottom-left origin. Flip it for
        # conventional human viewing; the two policy observations stay untouched.
        images[output_name] = sim.render(camera_name=camera_name, height=256, width=256)[::-1]
    for name, raw_array in images.items():
        array = np.asarray(raw_array).astype(np.uint8)
        image_shapes[name] = list(array.shape)
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        destination = OUTPUT / f"{name}.png"
        temporary = OUTPUT / f".{name}.png.tmp"
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(destination)
    return image_shapes


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def make_action(mode: str, step: int, total_steps: int) -> np.ndarray:
    action = np.zeros((1, 7), dtype=np.float32)
    action[:, -1] = -1.0
    if mode == "demo":
        # A small, zero-mean loop that makes the end effector visibly move while
        # remaining a visualization demo rather than a task-solving policy.
        phase = 2 * math.pi * step / max(total_steps, 20)
        action[0, 0] = 0.08 * math.sin(phase)
        action[0, 1] = 0.06 * math.cos(phase)
        action[0, 2] = 0.03 * math.sin(2 * phase)
        action[0, 5] = 0.05 * math.cos(phase)
    return action


def main() -> None:
    args = parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = LiberoEnv(
        task=args.suite,
        task_ids=[args.task_id],
        camera_name=",".join(POLICY_CAMERA_NAMES),
        camera_name_mapping=POLICY_CAMERA_MAPPING,
        observation_height=256,
        observation_width=256,
        control_mode="relative",
    )
    envs = make_env(config, n_envs=1, use_async_envs=False)
    env = envs[args.suite][args.task_id]
    inner_env = env.envs[0]
    task_name = inner_env.task
    task_instruction = inner_env.task_description
    started_at = time.time()

    try:
        write_json_atomic(
            PROGRESS,
            {
                "phase": "initializing",
                "suite": args.suite,
                "task_id": args.task_id,
                "task_name": task_name,
                "task_instruction": task_instruction,
                "seed": args.seed,
                "action_mode": args.action_mode,
                "current_step": 0,
                "total_steps": args.steps,
            },
        )
        observation, reset_info = env.reset(seed=args.seed)
        image_shapes = save_images(observation, inner_env)
        steps_executed = 0
        for step in range(args.steps):
            action = make_action(args.action_mode, step, args.steps)
            observation, reward, terminated, truncated, step_info = env.step(action)
            steps_executed += 1
            if steps_executed % args.image_every == 0 or steps_executed == args.steps:
                image_shapes = save_images(observation, inner_env)
            write_json_atomic(
                PROGRESS,
                {
                    "phase": "running",
                    "suite": args.suite,
                    "task_id": args.task_id,
                    "task_name": task_name,
                    "task_instruction": task_instruction,
                    "seed": args.seed,
                    "action_mode": args.action_mode,
                    "current_step": steps_executed,
                    "total_steps": args.steps,
                    "reward": float(np.asarray(reward).reshape(-1)[0]),
                    "is_success": bool(np.asarray(step_info.get("is_success", [False])).reshape(-1)[0]),
                },
            )
            print(f"SIM_PROGRESS {steps_executed}/{args.steps}", flush=True)
            if bool(np.asarray(terminated)[0]) or bool(np.asarray(truncated)[0]):
                break
            if args.step_delay:
                time.sleep(args.step_delay)
    except Exception as exc:
        write_json_atomic(
            PROGRESS,
            {
                "phase": "error",
                "suite": args.suite,
                "task_id": args.task_id,
                "task_instruction": task_instruction,
                "current_step": locals().get("steps_executed", 0),
                "total_steps": args.steps,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise

    report = {
        "status": "ok",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torchvision": version("torchvision"),
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "lerobot": version("lerobot"),
        "hf_libero": version("hf-libero"),
        "robosuite": version("robosuite"),
        "robomimic": version("robomimic"),
        "mujoco": mujoco.__version__,
        "gymnasium": gymnasium.__version__,
        "assets_path": str(Path(get_assets_path()).resolve()),
        "suite": args.suite,
        "task_id": args.task_id,
        "task_name": task_name,
        "task_instruction": task_instruction,
        "seed": args.seed,
        "action_mode": args.action_mode,
        "steps_requested": args.steps,
        "steps_executed": steps_executed,
        "duration_seconds": round(time.time() - started_at, 3),
        "camera_mapping": OUTPUT_CAMERA_MAPPING,
        "image_shapes": image_shapes,
        "action_shape": list(action.shape),
        "reward": np.asarray(reward).tolist(),
        "is_success": [bool(np.asarray(step_info.get("is_success", [False])).reshape(-1)[0])],
        "terminated": np.asarray(terminated).tolist(),
        "truncated": np.asarray(truncated).tolist(),
        "reset_info_keys": sorted(reset_info.keys()),
        "step_info_keys": sorted(step_info.keys()),
    }
    report_json = json.dumps(report, indent=2)
    write_json_atomic(OUTPUT / "report.json", report)
    write_json_atomic(
        PROGRESS,
        {
            "phase": "complete",
            "suite": args.suite,
            "task_id": args.task_id,
            "task_name": task_name,
            "task_instruction": task_instruction,
            "seed": args.seed,
            "action_mode": args.action_mode,
            "current_step": steps_executed,
            "total_steps": args.steps,
            "reward": float(np.asarray(reward).reshape(-1)[0]),
            "is_success": report["is_success"][0],
        },
    )
    print(report_json, flush=True)
    env.close()


if __name__ == "__main__":
    main()

