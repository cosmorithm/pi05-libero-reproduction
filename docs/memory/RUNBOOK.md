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

## 任务账本（任何写操作前）

除只读检查外，训练、评测、下载、安装、部署、代码/文档修改和报告生成必须先在
[`TASKS.md`](TASKS.md) 中登记。前台命令优先用包装器，它会自动写入开始和终态：

```bash
scripts/run_tracked_task.sh \
  --task-id task-example-001 \
  --summary "说明目的和范围" \
  --log logs/example.log \
  --tag example -- \
  ./.venv/bin/python scripts/example.py
```

后台 `screen` 任务先使用 `project_memory.py task start`，结束后用
`project_memory.py task finish`，并把 `screen` 名称、日志和输出目录作为证据。

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

1. 每项非只读任务先写入 `task start`，进展写 `task update`，结束写 `task finish`：

```bash
./.venv/bin/python scripts/project_memory.py task list
```

2. 对实验、环境或决策使用 CLI 追加高层事件：

```bash
./.venv/bin/python scripts/project_memory.py add-event \
  --event environment_changed \
  --status complete \
  --summary "说明发生了什么" \
  --evidence logs/example.log \
  --tag environment
```

3. 更新 `docs/memory/CURRENT.md` 的已验证状态。
4. 新实验追加到 `docs/memory/EXPERIMENTS.md`。
5. 新决策或风险更新 `DECISIONS.md` / `OPEN_QUESTIONS.md`。
6. 同步更新 `README.md` 和根目录 `PROJECT_MEMORY.md` 的入口链接。
7. 运行 `./.venv/bin/python scripts/validate_project_memory.py`。
