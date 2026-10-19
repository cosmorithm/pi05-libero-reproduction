# 实验台账

> 只追加，不删除旧实验。表格中的“完成”必须有原始结果或明确日志。

| ID | 日期 | 实验 | 状态 | 结果 / 证据 |
| --- | --- | --- | --- | --- |
| L1000 | 2026-10-19 | Pi0.5-LIBERO seed=1000 四 suite baseline | complete | 392/400，98.0%；`outputs/benchmark/pi05-libero/`；报告 `reports/Pi05-LIBERO-详细最终技术报告-2026-10-19.pdf` |
| L2000-A | 2026-10-19 | Pi0.5-LIBERO seed=2000 三 suite | complete | 292/300，97.3%；`outputs/benchmark/pi05-libero-seed2000/`；报告 commit `4198452` |
| L2000-B | 2026-10-19 | Pi0.5-LIBERO seed=2000 `libero_10` 补全 | complete | 98/100，98.0%；退出码 0，用时 1664.897 秒；`outputs/benchmark/pi05-libero-seed2000/libero_10/` |
| VLM-TORCH | 2026-10-19 | Torch Pi0.5 内部 PaliGemma 直接文本探针 | complete | 100/100 调用成功，0 可读英文；`outputs/vlm_probe/full_100_20261019/` |
| VLM-JAX | 2026-10-19 | 官方 OpenPI JAX `pi05_libero` 内部 PaliGemma 探针 | preparing | 环境安装、checkpoint 下载和脚本准备中；尚未产生结果 |
| VLM-JAX-ENV | 2026-10-19 | JAX 探针环境迁移 | preparing | checkpoint 已完成；完整 `.venv-openpi` 安装过慢，已决策使用独立 `.venv-openpi-lean`，不修改 LeRobot `.venv`；任务 `task-openpi-jax-lean-env` |

## 实验记录模板

新增实验时追加以下字段到本表，并在 `events.jsonl` 写一条机器可读事件：

- ID：稳定的短 ID，例如 `VLM-JAX-001`
- 日期：使用客户端时区或显式标注 UTC/CST
- 实现/checkpoint：Torch 或 JAX、repo、revision
- 协议：suite、seed、task、episode、prompt、解码参数
- 状态：`planned` / `preparing` / `running` / `complete` / `failed` / `blocked`
- 结果：成功数、分母、关键指标或明确失败原因
- 证据：输出目录、报告、commit、哈希
- 解释边界：这个结论不能外推到哪里
