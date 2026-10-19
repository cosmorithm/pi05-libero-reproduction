# Pi0.5 内部 VLM 语言探针（2026-10-19）

## 一句话结论

在相同已部署 Pi0.5-LIBERO checkpoint 上，绕过动作专家、直接从内部 PaliGemma 流做 100 次贪心文本生成：100 次调用均成功返回，但没有任何可读英文回答。它不应被拆出来充当聊天式 VLM/LLM；这不影响正常 Pi0.5 `sample_actions` 路径已完成的 LIBERO 392/400（98.0%）基线。

## 被测边界

- checkpoint：`checkpoints/lerobot-pi05-libero-finetuned`
- 调用：`policy.model.paligemma_with_expert.paligemma.generate()`
- 不调用：300M `gemma_expert`、flow-matching 动作采样、动作反归一化、环境 step
- 性质：这是非官方支持的 direct-generation 消融，不是动作策略评测或通用 VQA 基准。

## 输入与协议

- 固定视觉上下文：`outputs/smoke/image.png`（LIBERO `agentview`；SHA-256 前缀 `762a2e30`）
- 原始相机帧为 256×256；实际 checkpoint 的 VLM 预处理为 224×224、patch 14、256 image tokens。
- prompt：`<image>answer en {question}`
- 解码：`do_sample=false`、`use_cache=true`、`max_new_tokens=32`
- 100 个英文问题：视觉理解 35、一般语言 35、机器人推理/操作 30。一般语言题保留固定画面，故不是纯文本 LLM 测试。

## 结果

| 类别 | 题数 | 成功调用 | 平均 token | 平均英文词 | 平均 ASCII 字母率 | 4-gram 重复 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 视觉理解 | 35 | 35/35 | 32.0 | 0.0 | 0.000 | 5 |
| 一般语言 | 35 | 35/35 | 32.0 | 0.0 | 0.000 | 0 |
| 机器人推理 | 30 | 30/30 | 32.0 | 0.0 | 0.000 | 6 |
| 总计 | 100 | 100/100 | 32.0 | 0.0 | 0.000 | 11 |

- 总墙钟：152.33 秒；大部分为约两分钟的冷加载。加载后单题平均 0.320 秒，中位数 0.302 秒。
- 100 条 completion 均不同，表明不是固定 API 报错；但它们均为非自然语言 Unicode/token 串，且全部到达 32-token 上限。
- 最终 GPU 已空闲。

## 工程适配记录

最初试图把 256×256 原始画面直接送入 PaliGemma 通用 `generate`，触发 SigLIP 位置编码的 `324 vs 256` 错误。根因是混淆了仿真相机输出分辨率与 Pi0.5 checkpoint 的内部 VLM 分辨率。最终脚本从已加载模型推导视觉规格，严格使用 224px/256-token，并显式对齐 OpenPI 端口的 legacy `image_token_index` 与现代 Transformers `image_token_id`（均为 257152）。100 题正式运行 0 error。

这也说明此前基线没有因此出错：正常 `sample_actions` 早已走内部 224px 预处理，正式 benchmark 从未走此处的 generic `generate` 路径。

## 原始数据、复验与解释边界

- 原始逐题数据：`outputs/vlm_probe/full_100_20261019/results.jsonl`
- SHA-256：`95ef03885b1785bf0b2109ebf77f7d1c39d12e87441e3c508c8f3b5c238728c3`
- 复验脚本：`scripts/probe_pi05_vlm_language.py`
- processor 获取脚本：`scripts/download_paligemma_processor.sh`（仅 tokenizer/processor 小文件；服务器镜像下载）

这个结果可以说明：在固定协议下，该 VLA 微调 checkpoint 的直接文本解码分布不再对齐自然语言。它不能证明原始预训练 PaliGemma “没有知识”，也不能说明换一个 checkpoint、提示模板或解码策略一定失败。若需要机器人解释、问答或上层规划，应使用独立受支持的 VLM/LLM，并通过结构化子任务或安全约束与 Pi0.5 的低层动作策略连接。
