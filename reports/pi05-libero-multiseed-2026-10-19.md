# Pi0.5-LIBERO 多 seed 阶段性报告（2026-10-19）

## 一句话结论

`seed=2000` 的 `libero_spatial`、`libero_object` 和 `libero_goal` 已全部完成：
三个 suite 共 300 个 episode，成功 292 个，成功率 97.3%。与 `seed=1000`
对应的三个 suite 合并后，共 600 个 episode，成功 587 个，成功率 97.8%。
本次结果仍是有限 seed 的阶段性复现，不能外推为完整泛化或真机性能。

## 评测范围

这是 `seed=2000` 多 seed 计划的第一部分，覆盖三个共有 suite：

| Suite | Task 数 | Episode 数 |
| --- | ---: | ---: |
| `libero_spatial` | 10 | 100 |
| `libero_object` | 10 | 100 |
| `libero_goal` | 10 | 100 |

`libero_10` 的 `seed=2000` 尚未安排，因此本报告不把它纳入多 seed 总计。
`seed=1000` 的四套 400-episode baseline 已在之前的报告中完成，共 392/400。

## 固定协议

| 项目 | 配置 |
| --- | --- |
| checkpoint | `checkpoints/lerobot-pi05-libero-finetuned` |
| seed | `2000` |
| task / episode | 每个 task 10 episode |
| batch size | 1 |
| `n_action_steps` | 10 |
| `compile_model` | false |
| 控制方式 | 7D relative control |
| 观测 | 2 x 256x256 RGB + 8D state |
| 仿真 | `init_states=true`、`hard_reset=true` |
| GPU | NVIDIA GeForce RTX 4090 D，24 GB |

## 最终结果

| Suite | 成功 / Episode | 成功率 | Wilson 95% 区间 | Evaluator 时间 |
| --- | ---: | ---: | ---: | ---: |
| `libero_spatial` | 97 / 100 | 97.0% | 91.5% - 99.0% | 834.64 s |
| `libero_object` | 98 / 100 | 98.0% | 93.0% - 99.4% | 843.09 s |
| `libero_goal` | 97 / 100 | 97.0% | 91.5% - 99.0% | 717.73 s |
| 三 suite 合计 | 292 / 300 | 97.3% | 94.8% - 98.7% | 2395.46 s |

失败 task 和 episode 如下：

| Suite | Task | 成功 / 10 | 失败 episode |
| --- | ---: | ---: | --- |
| `libero_spatial` | 5 | 7 | 2、3、4 |
| `libero_object` | 3 | 9 | 1 |
| `libero_object` | 9 | 9 | 5 |
| `libero_goal` | 2 | 9 | 2 |
| `libero_goal` | 3 | 8 | 4、9 |

## 与 seed=1000 对比

| Suite | seed=1000 | seed=2000 | 差异 |
| --- | ---: | ---: | ---: |
| `libero_spatial` | 98/100 | 97/100 | -1 |
| `libero_object` | 100/100 | 98/100 | -2 |
| `libero_goal` | 97/100 | 97/100 | 0 |
| 合计 | 295/300 | 292/300 | -3 |

两个 seed 的共有三 suite 合计为 587/600，成功率 97.8%，
Wilson 95% 区间约 96.2% 到 98.9%。

`libero_spatial` task 5 在两个 seed 中均有失败；`libero_goal` task 2
在两个 seed 中均有失败。其余失败 task 分布不同，暂不能证明存在确定性、
跨 seed 固定的失败模式。

## 输出核验

- `status.json` 为 `complete`，最终 suite 为 `libero_goal`
- runner 退出码：`0`
- `libero_spatial`：100 个 MP4
- `libero_object`：100 个 MP4
- `libero_goal`：100 个 MP4
- 三个 suite 均存在完整 `eval_info.json`
- `summary.json`、`summary.csv`、`summary.md` 均已生成
- 当前 `pi05-s2000-object-goal` screen 已正常退出，仅 Dashboard 继续运行

输出目录：

```text
outputs/benchmark/pi05-libero-seed2000/
```

## 解释边界

`seed=2000` 的 `libero_object` 从 `seed=1000` 的 100/100 下降到 98/100，
但这只代表两个随机种子和固定初始状态集合下的差异。三个 suite 的波动较小，
不能据此判断模型能力下降，也不能把 97.3% 直接视为稳定期望。

后续仍应完成 `libero_10` 的 `seed=2000`，并逐失败视频复核轨迹，再形成
四 suite 多 seed 的最终结论。
