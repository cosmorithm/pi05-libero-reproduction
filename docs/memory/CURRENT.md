# 当前状态

> 最后核验：2026-10-19 20:27 CST
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
- 原始 OpenPI JAX 环境：`.venv-openpi`（完整 editable install 仍在解析依赖，尚未完成）
- 后续 OpenPI JAX 环境：`.venv-openpi-lean`（已批准、尚未创建；只服务于 JAX VLM 探针）
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

- `libero-web` Dashboard 已恢复，监听容器 `6006`。
- 公网入口：`https://u580081-8d63-18907193.westb.seetacloud.com:8443/`
- Dashboard 支持七路相机、π0.5 动作模式、GPU 状态和历史评测回放。
- Token 只存在于项目根目录 `.dashboard_token`，不写入文档或 Git。
- Dashboard 在模型加载阶段已增加不确定进度动画和加载秒数。
- 官方 checkpoint `gs://openpi-assets/checkpoints/pi05_libero/` 已通过服务器 IPv4 下载完成，下载日志含 `OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE`；目标目录约 12 GiB。
- `openpi-setup` 仍在安装完整 `.venv-openpi` 依赖；20:15 的核验显示其仍在逐个解析/下载 TensorStore 候选版本，尚未出现退出码、也尚未通过任何 JAX import。
- 已决定不向已验证的 LeRobot `.venv` 写入 OpenPI 的完整依赖树：OpenPI 固定 `torch==2.7.1`，而现有可复现实验使用 `torch==2.11.0+cu128`。下一步改为独立 `.venv-openpi-lean`，通过受控最小依赖集运行 JAX VLM 探针。
- `openpi-jax-probe` 仍是已脱离终端的前置条件编排器；在精简环境创建并通过 import 前不会开始模型加载。之后将自动顺序运行翻转/未翻转 pilot 及 100 题 JAX 直接 VLM 探针。尚未产出任何 JAX 模型输出，不应提前下结论。
- seed=3000 的完整评测在执行前已按优先级延期，待 JAX 探针后再决定是否恢复。
- 阶段性证据与边界说明：`reports/OpenPI-JAX-阶段状态报告-2026-10-19.md`。

## 下一步

1. 将 JAX 探针迁移为独立 `.venv-openpi-lean`；不更改 `.venv`、其 PyTorch 2.11 或 LIBERO 复现路径。
2. 用真实 import 核验 `jax`、`flax`、`openpi`、`orbax`，并确认可恢复 `pi05_libero` checkpoint。
3. 读取 `openpi-jax-probe` 的 flip / no-flip pilot；成功后由编排器继续执行 100 题。
4. JAX 100 题批量完成后生成可追溯报告并推送，不将其与已有 Torch 消融混为一谈。
5. 对 `libero_10` seed=2000 结束结果做视频/状态核验并更新多 seed 结论。
