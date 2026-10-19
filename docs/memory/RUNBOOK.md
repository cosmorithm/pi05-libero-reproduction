# 运行手册

## 连接与状态

```bash
ssh pi05-4090d
cd /root/autodl-tmp/pi05-libero-reproduction
git status --short
git log -8 --oneline
screen -ls
nvidia-smi
```

## 正式 LeRobot 环境

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
source .venv/bin/activate
export LIBERO_CONFIG_PATH=$PWD/home/.libero
export HF_HOME=$PWD/cache/huggingface
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl
```

## Dashboard

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
screen -dmS libero-web bash -lc './scripts/start_dashboard.sh >> logs/dashboard.log 2>&1'
cat .dashboard_token
curl http://127.0.0.1:6006/healthz
```

公网入口为 `https://u580081-8d63-18907193.westb.seetacloud.com:8443/`。
访问根页和 API 时在 URL 中使用 `?token=<.dashboard_token>`。

## Benchmark

```bash
./.venv/bin/python scripts/benchmark_libero.py \
  --suites libero_spatial,libero_object,libero_goal \
  --n-episodes 10 \
  --seed 2000 \
  --output-root outputs/benchmark/pi05-libero-seed2000
```

## OpenPI JAX

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
screen -ls
tail -f logs/openpi-assets.log
tail -f logs/openpi-setup.log
.venv-openpi/bin/python -c 'import jax, flax, openpi; print(jax.__version__)'
```

服务器直连 GCS 时使用 IPv4：

```bash
curl -4 -I https://storage.googleapis.com/openpi-assets/
```

## 记忆维护

每次实验或环境变化后：

1. 在 `docs/memory/events.jsonl` 追加事件。
2. 更新 `docs/memory/CURRENT.md` 的已验证状态。
3. 新实验追加到 `docs/memory/EXPERIMENTS.md`。
4. 新决策或风险更新 `DECISIONS.md` / `OPEN_QUESTIONS.md`。
5. 同步 `README.md` 和根目录 `PROJECT_MEMORY.md` 的入口链接。
