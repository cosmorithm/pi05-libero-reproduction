# 任务账本

`tasks.jsonl` 是所有会改变项目状态的任务的追加式账本。它与
`events.jsonl` 分工：前者确保每项工作都有完整生命周期，后者记录对项目历史有
长期意义的实验、决策、事故和环境变化。

## 必须登记的范围

在执行前登记下列工作：训练、评测、下载、安装、部署、代码/文档修改、数据处理、
报告生成、模型推理、服务启动/停止，以及会写入项目目录的诊断任务。

纯只读检查（例如读取 README、`git status`、`nvidia-smi`、查看日志）不登记。

## 生命周期

每个任务使用一个稳定 ID（`task-...`），必须依次写入：

1. `started`：开始前，记录目的、将执行的命令或人工流程、初始证据路径。
2. `updated`：运行中的关键进展、阻塞或变更方向；不是每一条普通日志都要写。
3. `finished`：只可使用 `complete`、`failed` 或 `blocked`，并附结果或失败日志。

一个任务只能有一条 `started`，终态后不能再追加更新。任务有子步骤时，使用各自的
任务 ID；不要把彼此独立的实验或部署混成一条记录。

## 标准命令

手动登记：

```bash
./.venv/bin/python scripts/project_memory.py task start \
  --task-id task-example-001 \
  --summary "说明目的和范围" \
  --command "完整且可复现的命令或人工步骤" \
  --evidence logs/example.log \
  --tag example

./.venv/bin/python scripts/project_memory.py task update \
  --task-id task-example-001 \
  --summary "说明关键进展或阻塞" \
  --evidence logs/example.log

./.venv/bin/python scripts/project_memory.py task finish \
  --task-id task-example-001 \
  --status complete \
  --summary "说明结果与适用边界" \
  --evidence outputs/example/result.json
```

对于前台训练、评测和脚本，优先使用自动包装器：

```bash
scripts/run_tracked_task.sh \
  --task-id task-example-001 \
  --summary "说明目的和范围" \
  --log logs/example.log \
  --tag example -- \
  ./.venv/bin/python scripts/example.py --flag value
```

后台 `screen` 任务必须在创建 screen **之前**运行 `task start`；完成后以退出码和
输出文件运行 `task finish`。任务 ID、命令、输出路径、日志和 Git commit 一起构成
最小可复现实验单元。

## 提交前检查

```bash
./.venv/bin/python scripts/project_memory.py task list
./.venv/bin/python scripts/validate_project_memory.py
```

验证器会检查字段、时间顺序、任务生命周期、证据路径、Markdown 链接和常见秘密模式。
它允许 `running` / `preparing` 任务存在；未完成不是验证错误，但必须在
`CURRENT.md` 中注明当前运行状态。
