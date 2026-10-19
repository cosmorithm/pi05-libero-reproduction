# Pi0.5-LIBERO 长期项目记忆

这套目录用于让人类和 AI 在跨会话、跨容器、跨实验中快速恢复上下文。
它不是运行日志的替代品，也不是“把所有内容塞进一个文件”的笔记。

根目录 [`README.md`](../../README.md) 是完整操作接口，包含 SSH、环境、
benchmark、Dashboard HTTP API、OpenPI JAX、Git 和本记忆系统的命令；
`docs/memory/` 负责保存可长期演进的事实、决策和证据索引。

## 阅读顺序

1. `CURRENT.md`：当前可验证状态和正在进行的任务。
2. `EXPERIMENTS.md`：实验台账，回答“跑过什么、结果是什么、证据在哪里”。
3. `DECISIONS.md`：已经做出的关键决策和理由。
4. `OPEN_QUESTIONS.md`：尚未解决的问题和风险。
5. `RUNBOOK.md`：可直接复制执行的命令。
6. `events.jsonl`：机器可读的追加式事件流。
7. `schema.json`：事件字段和枚举值的机器可读 schema。
8. `templates/`：实验记录和会话交接模板。
9. `TASKS.md` 与 `tasks.jsonl`：全部会改变项目状态的任务及其生命周期。

## 维护原则

- **事实与推测分开。** 结果必须带日期、命令或输出路径；推测放在“开放问题”。
- **状态与历史分开。** `CURRENT.md` 只写当前状态，历史变化追加到 `events.jsonl` 和实验台账。
- **证据优先。** 不把“正在运行”当成“已经完成”，不把单个 seed 当成泛化结论。
- **只记录可复现信息。** 记录 checkpoint revision、commit、seed、协议、输出目录和关键指标。
- **不记录秘密。** 不写入 SSH 私钥、Hugging Face token、Dashboard token、模型权重或大视频。
- **不覆盖别人的记录。** 事件流与任务账本都采用追加模式；旧结论被推翻时新增事件说明原因。
- **任务先于变更。** 除纯只读检查外，开始任务前必须在 `tasks.jsonl` 写入
  `started`；关键进展写 `updated`；终态写 `finished` 并附证据。

## 状态标记

`planned`：已计划，尚未开始  
`preparing`：正在准备环境、资产或代码  
`running`：正在执行，尚无可作为最终结论的结果  
`complete`：已完成并有证据  
`failed`：已失败，原因和日志已保留  
`blocked`：有明确外部阻塞，尚未解决

## AI 接手流程

1. 先读 `CURRENT.md`、`EXPERIMENTS.md` 的最近条目和 `OPEN_QUESTIONS.md`。
2. 用 `RUNBOOK.md` 的命令自行探索，不把旧记忆当作实时状态。
3. 开始任何会改变项目状态的任务前，在 `tasks.jsonl` 追加 `started` 记录；纯只读
   检查不登记。具体命令见 [`TASKS.md`](TASKS.md)。
4. 关键进度写 `updated`；完成、失败或阻塞时追加 `finished`，并附输出或日志。
5. 对长期有意义的结果、决策或事故，另外在 `events.jsonl` 追加
   `experiment_completed`、`decision` 或 `incident` 事件。
6. 只更新 `CURRENT.md` 中已经有证据支持的事实。
7. 同步更新根目录 `README.md` 和 `PROJECT_MEMORY.md` 的入口链接，再提交 Git。

提交前运行：

```bash
./.venv/bin/python scripts/validate_project_memory.py
```

追加规范事件：

```bash
./.venv/bin/python scripts/project_memory.py add-event \
  --event experiment_completed \
  --status complete \
  --summary "一句话说明结果" \
  --evidence outputs/experiment/status.json \
  --tag experiment-name
```

新增实验或交接会话时，复制 `templates/experiment.md` 或
`templates/handoff.md`，不要直接修改模板本身。

## 事件格式

`events.jsonl` 每行是一个独立 JSON 对象，至少包含：

```json
{
  "time": "2026-10-19T09:00:00Z",
  "event": "experiment_completed",
  "status": "complete",
  "summary": "一句话结果",
  "evidence": ["outputs/..."],
  "commit": "git-commit-if-any",
  "tags": ["libero", "seed=2000"]
}
```

允许的事件类型建议使用：

`task_started`、`task_finished`、`experiment_completed`、`incident`、
`decision`、`environment_changed`、`handoff`、`open_question`。

## 记录边界

- 原始 JSON、MP4、图片和大型日志留在 `outputs/`、`logs/` 或外部存储，只在记忆中写路径和摘要。
- Dashboard token 不进入 Markdown、JSONL 或 Git；只写 `.dashboard_token` 的位置。
- 任何实验结论都写明适用 checkpoint、seed、suite 和实现路径。
- 如果状态发生变化，先追加事件，再改当前状态文档。
