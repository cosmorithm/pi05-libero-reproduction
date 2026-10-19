# 当前状态

> 最后核验：2026-10-19 18:34 CST
> 维护规则：这里只放已验证事实；正在进行的步骤写到 `events.jsonl`。

新会话入口是根目录 [`README.md`](../../README.md) 的“新会话从这里开始”；
本文是启动器要求读取的实时状态文件。

## 环境

- SSH 别名：`pi05-4090d`
- 实际入口：`root@connect.westb.seetacloud.com:13591`
- 当前主机名：`autodl-container-3f5d4d8d63-18907193`
- GPU：NVIDIA GeForce RTX 4090 D，24 GB
- 项目根目录：`/root/autodl-tmp/pi05-libero-reproduction`
- 正式 LeRobot 环境：`.venv`
- OpenPI JAX 环境：`.venv-openpi`，正在准备
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
注意：`libero_10` 的 seed=2000 已于 2026-10-19 18:13 CST 启动，任务账本 ID 为
`task-libero-seed2000-10`；尚无可作为最终结论的结果。

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
- `openpi-setup` 正在安装 `.venv-openpi` 依赖；18:34 的进程与 I/O 核验表明仍在下载写入，尚未出现退出码。
- 官方 checkpoint `gs://openpi-assets/checkpoints/pi05_libero/` 正通过服务器 IPv4 下载；18:34 已有 8 个文件完成校验、4 个大参数分片断点续传中，已落盘约 7.02 GiB / 11.58 GiB。
- `openpi-jax-probe` 是已脱离终端的前置条件编排器：依赖、权重和当前 Torch 评测均就绪后，自动顺序运行翻转/未翻转 pilot 及 100 题 JAX 直接 VLM 探针；在此之前不占用 GPU。
- `libero_10` 的 seed=2000 正在 `pi05-s2000-libero10` 中评测。seed=3000 的完整评测在执行前已按优先级延期，待 JAX 探针后再决定是否恢复。

## 下一步

1. 监控 `openpi-jax-probe` 的前置条件与输出，读取 pilot 后再解释结果。
2. JAX 100 题批量完成后生成可追溯报告并推送，不将其与已有 Torch 消融混为一谈。
3. 对 `libero_10` seed=2000 结束结果做视频/状态核验并更新多 seed 结论。
4. 仅在 JAX 工作完成且用户确认后，恢复或重新设计 seed=3000 评测。
