# 当前状态

> 最后核验：2026-10-20 00:26 CST
> 维护规则：这里只放已验证事实；正在进行的步骤写到 `events.jsonl`。

新会话入口是根目录 [`README.md`](../../README.md) 的“新会话从这里开始”；
本文是启动器要求读取的实时状态文件。

## 环境

- SSH 别名：`pi05-4090d`
- 实际入口：`root@connect.westb.seetacloud.com:13591`
- 当前主机名：`autodl-container-3f5d4d8d63-18907193`
- GPU：NVIDIA GeForce RTX 4090 D，24 GB
- 项目根目录：`/root/autodl-tmp/pi05-libero-reproduction`
- 正式 LeRobot 环境：`.venv`（已验证；不得为 OpenPI 安装过程改写其 PyTorch 版本）
- 原始 OpenPI JAX 环境：`.venv-openpi`（容器/GPU 停止时中断，已被精简方案取代）
- JAX 探针环境：`.venv-openpi-lean`（已完成；只服务于 JAX VLM 探针）
- OpenPI 源码：`third_party/openpi`，固定 commit
  `215abfb217dbac7d5f1273282331b9b1866c0479`

## 已完成

### seed=1000 正式 baseline

四套 LIBERO suite 共 400 episode：

| Suite | 成功 |
| --- | ---: |
| `libero_spatial` | 98/100 |
| `libero_object` | 100/100 |
| `libero_goal` | 97/100 |
| `libero_10` | 97/100 |
| 合计 | 392/400 = 98.0% |

输出：`outputs/benchmark/pi05-libero/`

### seed=2000 第一阶段

三个共有 suite 共 300 episode：

| Suite | 成功 |
| --- | ---: |
| `libero_spatial` | 97/100 |
| `libero_object` | 98/100 |
| `libero_goal` | 97/100 |
| 合计 | 292/300 = 97.3% |

输出：`outputs/benchmark/pi05-libero-seed2000/`

### seed=2000 完整复现

`libero_10` 已于 2026-10-19 18:40 CST 完成：98/100 成功（98.0%，退出码 0，
用时 1664.897 秒）。因此 seed=2000 四套 suite 合计为 390/400 = 97.5%。
其任务账本 ID 为 `task-libero-seed2000-10`；仍应在后续报告中结合视频和
`eval_info.json` 复核失败轨迹。

### Torch VLM 语言探针

固定 100 题、固定 agentview 图像、内部 PaliGemma 直接贪心生成：

- 100/100 次调用成功，0 错误
- 100 条 completion 均不同，但全部为不可读 Unicode/token 串
- 清理后的英文词数和 ASCII 字母率均为 0
- 结论边界：这是直接文本解码消融，不代表正常 `sample_actions` 失效

报告：`reports/pi05-vlm-language-probe-2026-10-19.md`

## 当前运行 / 准备中

- `libero-web` Dashboard 曾验证可用；容器/GPU 停止后原 screen 已死亡，需要时按 RUNBOOK 重启。
- 公网入口：`https://u580081-8d63-18907193.westb.seetacloud.com:8443/`
- Dashboard 支持七路相机、π0.5 动作模式、GPU 状态和历史评测回放。
- Token 只存在于项目根目录 `.dashboard_token`，不写入文档或 Git。
- Dashboard 在模型加载阶段已增加不确定进度动画和加载秒数。
- 官方 checkpoint `gs://openpi-assets/checkpoints/pi05_libero/` 已通过服务器 IPv4 下载完成，下载日志含 `OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE`；目标目录约 12 GiB。
- `.venv-openpi-lean` 安装退出码为 0。已核验 JAX 0.5.3、Flax 0.10.2、NumPy 1.26.4、Transformers 4.53.2、OpenPI、Orbax 和 `pi05_libero` 配置均可导入；Torch 2.11.0+cu128 只从只读基线环境追加复用。
- checkpoint 共 16 个文件、约 12 GiB，并有下载完成标志；本地 tokenizer、norm stats、smoke 图像和 JAX 探针脚本均存在。GPU 开启后不需要再下载模型或 CUDA 大包。
- 完整 OpenPI 元数据仍报告 `gym-aloha` 未安装、Torch 不是官方固定的 2.7.1；这是精简 VLM 探针的刻意边界，不影响已验证的 JAX 模块/config import，但该环境不能宣称为完整 OpenPI 训练/ALOHA 环境。
- `openpi-jax-probe` 尚未运行。GPU 当前不可见，因此尚未验证 JAX CUDA device、checkpoint 真正恢复和 pilot 输出；不能提前下结论。
- seed=3000 的完整评测在执行前已按优先级延期，待 JAX 探针后再决定是否恢复。
- 阶段性证据与边界说明：`reports/OpenPI-JAX-阶段状态报告-2026-10-19.md`。

## 下一步

1. GPU 开启后运行 `./scripts/start_openpi_jax_probe.sh`；脚本必须先通过 `nvidia-smi` 和离线前置条件检查。
2. 确认 JAX 真正枚举 CUDA device，再恢复本地 checkpoint；禁止自动回退到 CPU 后误称 GPU 实验。
3. 读取 flip / no-flip pilot；成功后由编排器继续执行 100 题。
4. JAX 100 题批量完成后生成可追溯报告并推送，不将其与已有 Torch 消融混为一谈。
