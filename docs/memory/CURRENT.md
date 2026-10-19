# 当前状态

> 最后核验：2026-10-19 17:50 CST  
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
注意：`libero_10` 的 seed=2000 尚未运行。

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
- OpenPI JAX 依赖正在 `.venv-openpi` 中安装。
- 官方 checkpoint `gs://openpi-assets/checkpoints/pi05_libero/` 正在通过服务器 IPv4 下载。
- JAX 探针脚本已放到 `scripts/probe_pi05_vlm_language_jax.py`，尚未完成模型加载和 pilot。

## 下一步

1. 完成 `.venv-openpi` 依赖安装和 import 验证。
2. 完成官方 checkpoint 下载、大小校验和 `restore_params` 验证。
3. 先跑 1 个 prompt 的 JAX pilot，再做 10 到 20 题的预处理对照。
4. 根据 pilot 结果决定是否跑完整 100 题。
5. 安排 `libero_10` 的 seed=2000。
