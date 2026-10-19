# OpenPI JAX 阶段状态报告

> 核验时间：2026-10-19 20:07 CST  
> 项目：Pi0.5-LIBERO Reproduction  
> 状态：阶段报告；不是 JAX 语言探针的最终实验报告。

## 结论先行

本阶段有两项可复现工作已经完成：第一，Pi0.5 在 `libero_10` 的
`seed=2000` 正式评测已结束，100 个 episode 中成功 98 个；第二，OpenPI
官方 `pi05_libero` checkpoint 已在服务器端通过 IPv4 下载完成。JAX 的
OpenPI 环境仍在安装，因此**尚未加载官方 JAX 模型、尚未运行 pilot、尚未运行
100 个语言问题，也没有任何 JAX 输出可解释**。

这一区分很重要：此前 Torch 版本的内部 VLM 直接文本解码结果是不可读 token 串，
它是一个消融结果，不能替代或预测 OpenPI JAX checkpoint 的结果。

## 已完成的正式评测

| 项目 | 配置 | 已核验结果 | 证据 |
| --- | --- | ---: | --- |
| LIBERO baseline | seed=1000，4 suite × 100 episode | 392/400（98.0%） | `outputs/benchmark/pi05-libero/` |
| 多 seed 前三 suite | seed=2000，300 episode | 292/300（97.3%） | `outputs/benchmark/pi05-libero-seed2000/` |
| `libero_10` 补全 | seed=2000，100 episode | 98/100（98.0%） | `outputs/benchmark/pi05-libero-seed2000/libero_10/` |
| seed=2000 合计 | 4 suite × 100 episode | 390/400（97.5%） | 同上及 `status.json` |

最后一项评测的 `status.json` 为 `state: complete`，runner 退出码为 0，记录的
评测耗时为 1664.897 秒。它完成后，GPU 不再被 Torch evaluator 占用。

## OpenPI JAX 准备情况

| 部件 | 状态 | 核验方式 |
| --- | --- | --- |
| OpenPI 源码 | 完成 | `third_party/openpi` 固定在 `215abfb217dbac7d5f1273282331b9b1866c0479` |
| 官方 checkpoint | 完成 | `logs/openpi-assets.log` 含 `OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE`；`checkpoints/openpi-pi05-libero/` 约 12 GiB |
| JAX 独立环境 | 进行中 | `openpi-setup` detached screen 仍存活，尚无 `logs/openpi-setup.exitcode` |
| JAX VLM 探针 | 已排队 | `openpi-jax-probe` detached screen 等待环境安装成功 |

安装日志目前显示 pip 正在为 OpenPI 解析并下载依赖（包括 `tensorstore` 等 JAX
生态包）。该过程会尝试多个满足约束的候选 wheel，因此日志中出现多个版本下载。
截至核验时，安装进程仍在写入，尚未返回失败退出码；这说明它慢，但不能据此判为
安装完成或安装失败。

## 已挂起的自动实验序列

后台脚本 `scripts/run_openpi_jax_probe_after_prereqs.sh` 使用独立的
`.venv-openpi`，并设置：

```bash
XLA_PYTHON_CLIENT_PREALLOCATE=false
XLA_PYTHON_CLIENT_MEM_FRACTION=0.70
```

它将严格按下面顺序执行：

1. 等待并验证 OpenPI 环境退出码为 0，随后 import `jax`、`flax`、`openpi`、`orbax`。
2. 核验官方 checkpoint 完成标志和参数目录。
3. 确认 Torch `seed=2000` evaluator 已结束，避免同时占用 24GB 显存。
4. 运行 1 题翻转图像的 JAX pilot。
5. 运行 1 题未翻转图像的 JAX pilot。
6. 两个 pilot 成功后，运行固定 100 个问题、每题最多 32 个新 token 的正式批量。

相关输出将写入 `outputs/vlm_probe/jax_pilot_flip_20261019/`、
`outputs/vlm_probe/jax_pilot_no_flip_20261019/` 和
`outputs/vlm_probe/jax_full_100_20261019/`。没有这些文件中的真实模型输出前，
任何关于“Pi0.5 去掉 A 后是否还能语言问答”的结论都应视为未验证。

## 资源与后续

本次核验时 GPU 利用率为 0%、显存约 1 MiB：这是 Torch benchmark 已结束、JAX
仍在 CPU/网络依赖安装阶段的结果，不是 JAX 试验已完成。`seed=3000` 评测仍未启动，
以避免在 JAX 即将加载时制造显存竞争。

下一次检查可使用：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
screen -ls
tail -80 logs/openpi-setup.log
tail -80 logs/openpi-jax-probe-orchestrator.log
cat logs/openpi-setup.exitcode logs/openpi-jax-probe-orchestrator.exitcode 2>/dev/null
```

任务状态以 `docs/memory/tasks.jsonl` 为准；本报告对应任务 ID
`task-openpi-jax-status-report`。
