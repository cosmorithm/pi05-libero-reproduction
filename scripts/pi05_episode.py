#!/usr/bin/env python3
"""Run one LIBERO episode with Pi0.5 while recording all seven camera views."""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import statistics
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path("/root/autodl-tmp/pi05-libero-reproduction")

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("LIBERO_CONFIG_PATH", str(ROOT / "home/.libero"))
os.environ.setdefault("HF_HOME", str(ROOT / "cache/huggingface"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import numpy as np
import torch
from PIL import Image

import gymnasium
import mujoco
from libero.libero import get_assets_path
from lerobot.configs import PreTrainedConfig
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env, make_env_pre_post_processors
from lerobot.envs.utils import preprocess_observation
from lerobot.policies import make_policy, make_pre_post_processors
from lerobot.utils.constants import ACTION
from lerobot.utils.io_utils import write_video
from lerobot.utils.random_utils import set_seed


LIVE_OUTPUT = ROOT / "outputs" / "smoke"
PROGRESS = LIVE_OUTPUT / "progress.json"
RECORDING_ROOT = ROOT / "outputs" / "pi05_dashboard"
POLICY_CHECKPOINT = ROOT / "checkpoints" / "lerobot-pi05-libero-finetuned"

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
VIDEO_FPS = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Pi0.5 LIBERO episode")
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--steps", type=int, default=280)
    parser.add_argument("--image-every", type=int, default=1)
    parser.add_argument("--model-path", type=Path, default=POLICY_CHECKPOINT)
    args = parser.parse_args()
    if args.steps < 1 or args.steps > 1000:
        parser.error("--steps must be between 1 and 1000")
    if args.image_every < 1 or args.image_every > 100:
        parser.error("--image-every must be between 1 and 100")
    if not args.model_path.is_dir() or not (args.model_path / "model.safetensors").is_file():
        parser.error(f"--model-path is incomplete: {args.model_path}")
    return args


def scalar(value: Any, default: float = 0.0) -> float:
    array = np.asarray(value).reshape(-1)
    return float(array[0]) if array.size else default


def capture_frames(observation: dict[str, Any], inner_env: Any) -> dict[str, np.ndarray]:
    frames = {
        name: np.asarray(batch[0]).astype(np.uint8)
        for name, batch in observation["pixels"].items()
    }
    sim = inner_env._env.sim
    for camera_name, output_name in EXTRA_CAMERA_MAPPING.items():
        frames[output_name] = np.asarray(
            sim.render(camera_name=camera_name, height=256, width=256)[::-1]
        ).astype(np.uint8)
    return frames


def save_live_images(frames: dict[str, np.ndarray]) -> dict[str, list[int]]:
    shapes: dict[str, list[int]] = {}
    LIVE_OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, array in frames.items():
        shapes[name] = list(array.shape)
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        destination = LIVE_OUTPUT / f"{name}.png"
        temporary = LIVE_OUTPUT / f".{name}.png.tmp"
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(destination)
    return shapes


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def base_progress(
    *,
    phase: str,
    suite: str,
    task_id: int,
    task_name: str,
    task_instruction: str,
    seed: int,
    current_step: int,
    total_steps: int,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "suite": suite,
        "task_id": task_id,
        "task_name": task_name,
        "task_instruction": task_instruction,
        "seed": seed,
        "action_mode": "pi05",
        "current_step": current_step,
        "total_steps": total_steps,
    }


def load_pi05_pipeline(model_path: Path, env_cfg: LiberoEnv, seed: int) -> dict[str, Any]:
    policy_cfg = PreTrainedConfig.from_pretrained(model_path)
    policy_cfg.pretrained_path = model_path
    policy_cfg.n_action_steps = 10
    policy_cfg.compile_model = False
    if not policy_cfg.device or not torch.cuda.is_available():
        policy_cfg.device = "cuda" if torch.cuda.is_available() else "cpu"

    set_seed(seed)
    policy = make_policy(cfg=policy_cfg, env_cfg=env_cfg)
    policy.eval()

    preprocessor_overrides = {
        "device_processor": {"device": str(policy.config.device)},
    }
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy_cfg,
        pretrained_path=model_path,
        preprocessor_overrides=preprocessor_overrides,
    )
    env_preprocessor, env_postprocessor = make_env_pre_post_processors(
        env_cfg=env_cfg,
        policy_cfg=policy_cfg,
    )
    return {
        "policy": policy,
        "preprocessor": preprocessor,
        "postprocessor": postprocessor,
        "env_preprocessor": env_preprocessor,
        "env_postprocessor": env_postprocessor,
    }


def select_pi05_action(
    observation: dict[str, Any],
    task_instruction: str,
    pipeline: dict[str, Any],
) -> np.ndarray:
    processed = preprocess_observation(observation)
    processed["task"] = [task_instruction]
    processed = pipeline["env_preprocessor"](processed)
    processed = pipeline["preprocessor"](processed)

    policy = pipeline["policy"]
    with torch.inference_mode(), (
        torch.autocast(device_type=policy.config.device)
        if policy.config.use_amp and policy.config.device.startswith("cuda")
        else nullcontext()
    ):
        action = policy.select_action(processed)

    action = pipeline["postprocessor"](action)
    transition = {ACTION: action}
    transition = pipeline["env_postprocessor"](transition)
    return transition[ACTION].to("cpu").numpy()


def format_seconds(seconds: float) -> str:
    return f"{seconds:.3f}"


def main() -> None:
    args = parse_args()
    LIVE_OUTPUT.mkdir(parents=True, exist_ok=True)

    env_cfg = LiberoEnv(
        task=args.suite,
        task_ids=[args.task_id],
        camera_name=",".join(POLICY_CAMERA_NAMES),
        camera_name_mapping=POLICY_CAMERA_MAPPING,
        observation_height=256,
        observation_width=256,
        control_mode="relative",
    )
    envs = make_env(env_cfg, n_envs=1, use_async_envs=False)
    env = envs[args.suite][args.task_id]
    inner_env = env.envs[0]
    task_name = inner_env.task
    task_instruction = inner_env.task_description
    started_at = time.time()
    steps_executed = 0
    inference_seconds: list[float] = []
    action_trace: list[list[float]] = []
    video_paths: dict[str, str] = {}
    frames_by_camera: dict[str, list[np.ndarray]] = {
        name: [] for name in OUTPUT_CAMERA_MAPPING.values()
    }

    recording_dir = RECORDING_ROOT / (
        f"{args.suite}-task{args.task_id}-seed{args.seed}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    recording_dir.mkdir(parents=True, exist_ok=True)

    def progress(
        phase: str,
        *,
        reward: float = 0.0,
        is_success: bool = False,
        error: str | None = None,
    ) -> None:
        payload = base_progress(
            phase=phase,
            suite=args.suite,
            task_id=args.task_id,
            task_name=task_name,
            task_instruction=task_instruction,
            seed=args.seed,
            current_step=steps_executed,
            total_steps=args.steps,
        )
        payload.update(
            reward=reward,
            is_success=is_success,
            model_path=str(args.model_path),
            model_load_seconds=model_load_seconds,
            last_inference_seconds=(
                inference_seconds[-1] if inference_seconds else None
            ),
            mean_inference_seconds=(
                statistics.fmean(inference_seconds) if inference_seconds else None
            ),
        )
        if error is not None:
            payload["error"] = error
        write_json_atomic(PROGRESS, payload)

    model_load_seconds = 0.0
    pipeline: dict[str, Any] | None = None

    try:
        progress("loading_model")
        print("PI05_LOAD_MODEL start", flush=True)
        model_started_at = time.perf_counter()
        pipeline = load_pi05_pipeline(args.model_path, env_cfg, args.seed)
        model_load_seconds = time.perf_counter() - model_started_at
        print(
            f"PI05_LOAD_MODEL done model_load_seconds={format_seconds(model_load_seconds)}",
            flush=True,
        )

        pipeline["policy"].reset()
        pipeline["preprocessor"].reset()
        pipeline["postprocessor"].reset()

        observation, reset_info = env.reset(seed=args.seed)
        frames = capture_frames(observation, inner_env)
        for name, frame in frames.items():
            frames_by_camera[name].append(frame)
        image_shapes = save_live_images(frames)

        progress("running")
        for _step in range(args.steps):
            action_started_at = time.perf_counter()
            action = select_pi05_action(observation, task_instruction, pipeline)
            action_elapsed = time.perf_counter() - action_started_at
            inference_seconds.append(action_elapsed)
            action_trace.append(action.reshape(-1).astype(float).tolist())

            observation, reward, terminated, truncated, step_info = env.step(action)
            steps_executed += 1
            frames = capture_frames(observation, inner_env)
            for name, frame in frames.items():
                frames_by_camera[name].append(frame)
            if steps_executed % args.image_every == 0 or steps_executed == args.steps:
                image_shapes = save_live_images(frames)

            step_reward = scalar(reward)
            step_success = bool(
                scalar(step_info.get("is_success", [False]))
            )
            progress(
                "running",
                reward=step_reward,
                is_success=step_success,
            )
            print(
                "PI05_STEP "
                f"{steps_executed}/{args.steps} "
                f"reward={step_reward:.3f} "
                f"success={step_success} "
                f"inference_ms={action_elapsed * 1000:.1f}",
                flush=True,
            )
            if bool(np.asarray(terminated).reshape(-1)[0]) or bool(
                np.asarray(truncated).reshape(-1)[0]
            ):
                break

        video_dir = recording_dir / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        for name, frames in frames_by_camera.items():
            path = video_dir / f"{name}.mp4"
            write_video(str(path), frames, VIDEO_FPS)
            video_paths[name] = str(path)

        final_reward = scalar(reward)
        final_success = bool(scalar(step_info.get("is_success", [False])))
        report: dict[str, Any] = {
            "status": "ok",
            "action_mode": "pi05",
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
            "model_path": str(args.model_path),
            "suite": args.suite,
            "task_id": args.task_id,
            "task_name": task_name,
            "task_instruction": task_instruction,
            "seed": args.seed,
            "steps_requested": args.steps,
            "steps_executed": steps_executed,
            "model_load_seconds": round(model_load_seconds, 3),
            "first_inference_seconds": round(
                inference_seconds[0], 3
            ) if inference_seconds else None,
            "mean_inference_seconds": round(
                statistics.fmean(inference_seconds), 3
            ) if inference_seconds else None,
            "p95_inference_seconds": round(
                statistics.quantiles(inference_seconds, n=20)[18], 3
            ) if len(inference_seconds) >= 20 else (
                round(max(inference_seconds), 3) if inference_seconds else None
            ),
            "inference_seconds": [
                round(value, 3) for value in inference_seconds
            ],
            "action_trace": action_trace,
            "action_shape": list(action.shape),
            "duration_seconds": round(time.time() - started_at, 3),
            "camera_mapping": OUTPUT_CAMERA_MAPPING,
            "image_shapes": image_shapes,
            "video_fps": VIDEO_FPS,
            "video_paths": video_paths,
            "recording_dir": str(recording_dir),
            "reward": float(final_reward),
            "is_success": final_success,
            "terminated": np.asarray(terminated).tolist(),
            "truncated": np.asarray(truncated).tolist(),
            "reset_info_keys": sorted(reset_info.keys()),
            "step_info_keys": sorted(step_info.keys()),
            "peak_cuda_memory_mib": (
                round(torch.cuda.max_memory_allocated(0) / 1024**2, 1)
                if torch.cuda.is_available()
                else None
            ),
        }
        write_json_atomic(LIVE_OUTPUT / "report.json", report)
        write_json_atomic(recording_dir / "report.json", report)

        final_progress = base_progress(
            phase="complete",
            suite=args.suite,
            task_id=args.task_id,
            task_name=task_name,
            task_instruction=task_instruction,
            seed=args.seed,
            current_step=steps_executed,
            total_steps=args.steps,
        )
        final_progress.update(
            reward=final_reward,
            is_success=final_success,
            model_load_seconds=round(model_load_seconds, 3),
            mean_inference_seconds=round(
                statistics.fmean(inference_seconds), 3
            ) if inference_seconds else None,
            video_paths=video_paths,
            recording_dir=str(recording_dir),
        )
        write_json_atomic(PROGRESS, final_progress)
        write_json_atomic(recording_dir / "progress.json", final_progress)
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        error_progress = base_progress(
            phase="error",
            suite=args.suite,
            task_id=args.task_id,
            task_name=task_name,
            task_instruction=task_instruction,
            seed=args.seed,
            current_step=steps_executed,
            total_steps=args.steps,
        )
        error_progress["error"] = error
        write_json_atomic(PROGRESS, error_progress)
        write_json_atomic(recording_dir / "progress.json", error_progress)
        raise
    finally:
        env.close()


if __name__ == "__main__":
    main()
