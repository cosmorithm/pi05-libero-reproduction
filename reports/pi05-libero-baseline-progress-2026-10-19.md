# Pi0.5-LIBERO 正式基线评测：运行说明与阶段报告

> 报告时点：2026-10-19 15:01 CST。本文是阶段报告：前三个 suite 的结果已完成并可复核；`libero_10` 仍在运行，不能被纳入最终总体结论。

## 1. 这项任务究竟在做什么

这里运行的不是训练，也不是下载数据，而是 **评测已经训练好的 Pi0.5 策略** 在 LIBERO 仿真基准中的闭环表现。

一次 episode 的过程是：LIBERO 创建机械臂、桌面物体和自然语言任务；策略读取两路相机图像和机器人状态；Pi0.5 输出 7 维相对控制动作；MuJoCo 仿真推进并判定任务是否完成。每次成功/失败都会写入结构化 JSON 和回放 MP4。

本次正式 protocol 有 4 个 suite，每个 suite 10 个 task，每个 task 10 个 episode，因此计划总量为 **400 个 episode**：

| Suite | 含义（本项目中的分组） | Task 数 | Episode 数 |
| --- | --- | ---: | ---: |
| `libero_spatial` | 涉及物体相对空间位置的指令 | 10 | 100 |
| `libero_object` | 区分物体身份、属性或类别的指令 | 10 | 100 |
| `libero_goal` | 以目标状态或目标关系描述的指令 | 10 | 100 |
| `libero_10` | LIBERO-10 的十个任务集合 | 10 | 100 |

这类评测回答的是“固定模型能否在固定仿真初始条件下把任务做成”。它不是微调、预训练或真实机器人部署，也不能单独说明跨随机种子或真实世界的泛化能力。

## 2. 固定的复现实验条件

| 项目 | 固定配置 |
| --- | --- |
| 策略 checkpoint | `lerobot/pi05_libero_finetuned`，revision `7152f13e34c6c115d808aea0e5d08aca74eac14b` |
| 运行框架 | LeRobot 0.6.2，`lerobot-eval` |
| 仿真 | hf-libero 0.1.4、robosuite 1.4.0、MuJoCo 3.8.1，EGL 无头渲染 |
| GPU | NVIDIA GeForce RTX 4090 D，24 GB |
| 图像输入 | 两路 256x256 RGB：`agentview` 和 `robot0_eye_in_hand` |
| 低维输入/动作 | 8 维机器人 state，7 维相对控制 action |
| 推理参数 | CUDA、bfloat16、`n_action_steps=10`、`compile_model=false` |
| 评测协议 | `batch_size=1`、`init_states=true`、`hard_reset=true`、seed `1000`、每 task 10 episode |

额外五路相机（广角、俯视、正面、侧面和机器人本体）只用于 Dashboard 人类观察和录像，**不输入 Pi0.5 策略**。策略输入结构没有被可视化 UI 改动。

## 3. 为什么 GPU 利用率不是一直 100%

这个工作负载在两种阶段之间切换：

1. CPU/仿真端：构造环境、物理推进、渲染、视频编码和写盘；
2. GPU/策略端：将两路图像和状态送入 Pi0.5，预测后续动作块。

因此 `nvidia-smi` 的瞬时 GPU 利用率会波动，而显存会稳定保持在约 10 GB。报告时测得约 10.6 GB 显存、31% 瞬时利用率、50 C；这说明模型已加载且 episode 正常推进，并不意味着闲置或故障。

## 4. 已完成、正在运行与中断恢复

先前容器更换时，旧 `screen` 会话终止。项目位于 `/root/autodl-tmp` 的持久盘中，已完成 suite 的 JSON、元数据和视频没有丢失。旧 `libero_10` 过程没有产生最终 `eval_info.json`，因此被视作 **无效的中断过程**，不会合并到结果中。

当前容器使用：

```text
SSH: root@connect.westb.seetacloud.com:21897
Host: autodl-container-2e4d46bfa5-2ad818b7
Project: /root/autodl-tmp/pi05-libero-reproduction
```

恢复 runner 会跳过已经拥有完整 `eval_info.json` 的前三套，只从头执行 `libero_10`。报告时该 suite 已写出 66 个回放视频，正在第 7 个 task 左右继续运行；尚未生成 `libero_10/eval_info.json` 与全量 `summary.json`。

`status.json` 只在 suite 边界更新，因此它在正在运行时显示的 `updated_at` 不代表进程没有推进；应同时以 `screen -list`、GPU 显存、`run.log` 末尾和视频计数判断活跃性。

## 5. 已确认的阶段性结果

下表只统计已完整落盘的 3 个 suite，即 300 个 episode。

| Suite | 成功 / Episode | 成功率 | Wilson 95% 区间 | 总评测耗时 | 平均每 episode |
| --- | ---: | ---: | ---: | ---: | ---: |
| `libero_spatial` | 98 / 100 | 98.0% | 93.0% - 99.4% | 674.2 s | 6.74 s |
| `libero_object` | 100 / 100 | 100.0% | 96.3% - 100.0% | 711.8 s | 7.12 s |
| `libero_goal` | 97 / 100 | 97.0% | 91.5% - 99.0% | 619.7 s | 6.20 s |
| 阶段合计 | 295 / 300 | 98.3% | 不适用于跨 suite 官方比较 | 2005.7 s | 6.69 s |

已知失败 task：

- `libero_spatial`：task 5 与 task 9，各为 9/10；
- `libero_goal`：task 0、2、9，各为 9/10；
- `libero_object`：在本次固定 seed 下为 100/100。

目前没有把 98.3% 表述成“最终 400 episode 成功率”，也没有把它当作官方排行榜复现。完整第四套结果、更多 seed 和严格对齐的上游版本都还需要补齐。

## 6. 输出位置与如何复核

服务器上的原始输出被 Git 忽略（视频和权重较大），但保留在持久盘：

```text
outputs/benchmark/pi05-libero/<suite>/eval_info.json
outputs/benchmark/pi05-libero/<suite>/metadata.json
outputs/benchmark/pi05-libero/<suite>/run.log
outputs/benchmark/pi05-libero/<suite>/videos/<suite>_<task>/eval_episode_<n>.mp4
outputs/benchmark/pi05-libero/status.json
logs/benchmark-resume-20261019.log
```

完成后 runner 将生成：

```text
outputs/benchmark/pi05-libero/summary.json
outputs/benchmark/pi05-libero/summary.csv
outputs/benchmark/pi05-libero/summary.md
```

快速检查命令：

```bash
ssh pi05-4090d
cd /root/autodl-tmp/pi05-libero-reproduction
screen -list
nvidia-smi
tail -f logs/benchmark-resume-20261019.log
python -m json.tool outputs/benchmark/pi05-libero/status.json
```

## 7. Git 与工程状态

服务器已使用专用 ed25519 key 通过 GitHub SSH 认证为 `cosmorithm`。remote 为：

```text
git@github.com:cosmorithm/pi05-libero-reproduction.git
```

阶段性文档、SSH 入口变更和上一份 PDF 已推送到 `main` 的提交 `ef69443`。本报告会作为新的提交推送；`libero_10` 完成且结果核验后还会再推送一次最终更新。

## 8. 结论与下一步

当前任务的价值是建立一个可以重复、可审计的 Pi0.5-LIBERO 推理基线，而不是消耗 GPU 做没有目标的计算。已经确认：模型、tokenizer、两路策略相机、相对控制、EGL 仿真、评测写盘和视频输出形成了有效闭环；前三套结果高且可复核。

接下来的顺序是：

1. 等待 `libero_10` 写出完整结果；
2. 核验四套 task 数、episode 数、视频数和 `summary`；
3. 更新本报告为最终 400-episode 版本并推送；
4. 再运行多 seed，分析失败视频，而不是直接开始微调；
5. 最后才设计 24 GB 显存下的参数高效微调实验。
