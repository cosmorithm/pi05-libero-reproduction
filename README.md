# Pi0.5-LIBERO Reproduction

独立的 LeRobot/PyTorch + LIBERO 仿真复现环境。远端根目录固定为：

```text
/root/autodl-tmp/pi05-libero-reproduction
```

旧实例已完成仿真部署、七视角可视化和真实 π0.5 闭环评测。项目于 2026-10-17 迁移到新服务器：代码、Git 历史、运行环境、586 个 LIBERO assets、Pi0.5 checkpoint、七视角 smoke 和本地 Dashboard 已恢复；PaliGemma tokenizer 正等待新实例 Hugging Face device OAuth。旧实例上的正式四套 LIBERO baseline 已中断。

## 当前状态

> 迁移提示：当前 SSH 入口为 `root@connect.westb.seetacloud.com:23741`，主机名为 `autodl-container-c85144bc1a-c9f2625b`。环境、assets、checkpoint、smoke 和本地 Dashboard 已在新实例恢复；下列“第一次真实评测”成功率仍是旧实例基线，必须在 tokenizer 授权后复验。

- 服务器：RTX 4090 D 24 GB，CUDA runtime 12.8
- Python 3.12.3、PyTorch 2.11.0+cu128、torchvision 0.26.0+cu128
- LeRobot 0.6.2，源码固定在提交 `146d8474932c8b566717eb2738ba459337ab71c4`
- hf-libero 0.1.4、robosuite 1.4.0、robomimic 0.2.0、MuJoCo 3.8.1
- `pip check`：无依赖冲突
- LIBERO assets：586/586 个文件校验通过，位于 `assets/`
- smoke test：`libero_spatial` task 0 完成 reset、多步动作和 EGL 无头渲染，生成全部 7 路 256×256 RGB 相机画面
- Web 控制台 v3：已在新实例本地 6006 端口运行，支持 `idle`、`demo` 和真实 π0.5 模式；公网仍需新容器映射
- Pi0.5 checkpoint：`lerobot/pi05_libero_finetuned`，固定 revision `7152f13e34c6c115d808aea0e5d08aca74eac14b`，已通过服务器端镜像 + hf-xet 恢复并验证
- 第一次真实评测：`libero_spatial` task 0、seed 7，1/1 episode 成功，模型在第 73 步完成任务
- Benchmark smoke：`libero_spatial` task 0、seed 7，1/1 episode 成功，runner 结果和汇总链路通过

## 登录

```bash
ssh pi05-4090d
```

## 激活环境

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
source .venv/bin/activate
export LIBERO_CONFIG_PATH=$PWD/home/.libero
export HF_HOME=/root/autodl-tmp/pi05-libero-reproduction/cache/huggingface
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl
```

## 验证

```bash
python scripts/smoke_libero.py \
  --suite libero_spatial \
  --task-id 0 \
  --seed 7 \
  --steps 80 \
  --action-mode demo
cat outputs/smoke/report.json
```

成功时会在 `outputs/smoke/` 保存：

- `image.png`：`agentview`，策略主视角
- `image2.png`：`robot0_eye_in_hand`，腕部策略相机
- `image3.png`：`galleryview`，展示广角
- `image4.png`：`birdview`，俯视
- `image5.png`：`frontview`，正面
- `image6.png`：`sideview`，侧面
- `image7.png`：`robot0_robotview`，机器人本体视角
- `progress.json`：运行阶段、当前步数、任务语言、reward 和 success
- `report.json`：GPU、依赖版本、观测形状和 reset/step 结果

当前验证结果为 `status: ok`，7 路图像形状均为 `[256, 256, 3]`，动作形状为 `[1, 7]`。

`idle` 模式使用零位移动动作，只验证接口；`demo` 模式让末端执行器进行小幅、零均值循环运动，方便观察各个视角。两者都不是任务策略，因此 `reward=0`、`success=false` 通常是正常结果。

## Web 可视化控制台

轻量控制台监听服务器 `0.0.0.0:6006`，通过 SeetaCloud 自定义服务映射访问。它展示场景的全部 7 路相机（策略主视角、腕部、展示广角、俯视、正面、侧面、机器人本体），并支持选择 suite/task/seed/步数、静止演示、可见运动演示或 π0.5 真实策略、启动/停止 episode、自然语言任务、实时进度和 GPU 遥测。

旧实例公网入口（迁移后已失效，仅作历史记录）：

```text
https://u580081-955c-15394eb1.westb.seetacloud.com:8443/?token=<TOKEN>
```

`<TOKEN>` 从项目根目录的 `.dashboard_token` 读取，不应提交到仓库或公开分享。页面提供紧凑、标准和大图三种相机卡片尺寸，浏览器会记住选择；桌面端自动多列，手机端自动单列。

后台启动：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
screen -dmS libero-web bash -lc './scripts/start_dashboard.sh >> logs/dashboard.log 2>&1'
```

查看状态和访问 token：

```bash
screen -list
cat .dashboard_token
tail -f logs/dashboard.log
```

停止服务：

```bash
screen -S libero-web -X quit
```

公网 API 和相机帧要求 `?token=<.dashboard_token 内容>`；根页面和 `/healthz` 不包含敏感信息。控制台仅能启动预定义仿真参数，不提供终端或任意命令执行。演示动作只用于观察机械臂运动，不是任务策略，`success=false` 属于正常结果。

### π0.5 真实策略模式

在控制台的动作模式中选择“π0.5 真实策略”并启动后，服务运行 `scripts/pi05_episode.py`。脚本会：

- 加载 `lerobot/pi05_libero_finetuned` 固定 checkpoint；
- 使用 LeRobot 官方 processor 和 `n_action_steps=10` 执行真实相对控制；
- 每步更新控制台七路 PNG；
- 将完整 episode 的七路画面写入 `outputs/pi05_dashboard/<run>/videos/*.mp4`；
- 在 `report.json` 中记录模型加载时间、首帧/均值/95 分位推理时间、动作轨迹、显存峰值和 success。

真实模式为每次运行加载一次模型，因此首次启动通常需要约两分钟冷启动；加载期间控制台显示 `loading_model` 状态。该模式不会改变 Pi0.5 的两路策略输入结构，另外五路仅用于观察和录像。

已验证 `libero_spatial` task 0、seed 7 的 280 步控制台 episode 再次成功：74 个动作步、`reward=1.0`、`success=true`，七路 H.264 256×256 MP4 均有效。

### 相机实现说明

LeRobot 的 Pi0.5/LIBERO 接口仍然只接收 `agentview` 和 `robot0_eye_in_hand` 两路策略观测，没有被 Web UI 改动。其余五路只用于人类观察，由脚本从同一个 MuJoCo 状态直接渲染，并将 OpenGL 底部原点翻转为正常的人类观看方向。因此增加监控视角不会改变未来 Pi0.5 的输入结构。

robosuite 输出的 `No private macro file found` 是可选用户宏配置提示，不影响仿真；网页已将技术日志折叠，通常无需处理。

### 已验证

- 本机和公网 `/healthz` 返回控制台 `version: 3`
- 公网首页、鉴权状态 API 和 7 个 PNG 接口均返回 HTTP 200
- 从公网按钮成功启动 12 步 `demo` episode
- 任务语言、实时进度、最终报告和全部相机画面成功更新
- 视觉检查确认五路额外相机无黑屏、无重复、方向正常

## Pi0.5 单任务评测

标准复现使用 `lerobot/pi05_libero_finetuned`，并保持 checkpoint 规定的两路图像、8 维状态和 7 维动作：

- `observation.images.image`：`agentview`，256×256 RGB
- `observation.images.image2`：`robot0_eye_in_hand`，256×256 RGB
- `observation.state`：8 维
- `action`：7 维相对控制

权重由服务器直接通过 `https://hf-mirror.com` 下载到：

```text
checkpoints/lerobot-pi05-libero-finetuned
```

下载日志和状态：

```bash
screen -list
tail -f logs/pi05-download.log
du -sh checkpoints/lerobot-pi05-libero-finetuned
```

π0.5 的 tokenizer 来自 gated 仓库 `google/paligemma-3b-pt-224`。首次运行前，需要先在 Hugging Face 页面接受许可，再在服务器登录；token 不应写入 README、脚本或聊天记录：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
export HF_HOME=$PWD/cache/huggingface
.venv/bin/hf auth login
```

登录后执行最小闭环评测：

```bash
./scripts/eval_pi05_single.sh
```

脚本默认只运行 `libero_spatial` task 0、seed 7、一个 episode，使用相对动作、256×256 两路策略观测、`n_action_steps=10`，并关闭首次测试不必要的 `torch.compile`。结果保存在 `outputs/eval/`，包括 `eval_info.json`、主视角 MP4 和运行日志。七路相机仍用于控制台观察；评测链路验证后再把七视角录制接入策略运行。

### 第一次真实闭环结果

2026-10-17 已执行：

```bash
./scripts/eval_pi05_single.sh
```

任务语言：

```text
pick up the black bowl between the plate and the ramekin and place it on the plate
```

结果：

| 指标 | 结果 |
| --- | --- |
| suite / task / seed | `libero_spatial` / `0` / `7` |
| episode | 1 |
| 成功 | 1/1，`success=true` |
| 完成步数 | 第 73 步，最大允许 280 步 |
| sum/max reward | 1.0 / 1.0 |
| evaluator rollout 时间 | 8.081 秒 |
| 首次冷启动 | 日志时间戳估计约 2 分 14 秒（含进程、环境和权重构建） |
| 观察到的运行显存 | 约 10,417 MiB |
| MP4 | H.264，256×256，74 帧，80 fps，0.925 秒回放 |
| 进程退出 | `EXIT_CODE=0` |

`1/1 = 100%` 只说明链路和该初始状态成功，不能当成模型总体成功率。单样本的 95% Wilson 区间为 20.7%–100%；后续必须增加任务、episode 和 seed 才能形成可信结论。

输出：

```text
outputs/eval/pi05-libero_spatial-task0-seed7/eval_info.json
outputs/eval/pi05-libero_spatial-task0-seed7/run.log
outputs/eval/pi05-libero_spatial-task0-seed7/videos/libero_spatial_0/eval_episode_0.mp4
```

本次 MP4 采用 LIBERO 的 80 fps 元数据，因此 74 个仿真帧被压缩为约 0.925 秒回放；日志中的 8.081 秒是 rollout wall time。第一次进程从 04:07:00 左右启动，04:09:14 结束，总冷启动约 2 分 14 秒，其中大部分发生在 CPU 侧构建模型和映射权重。视频时长、rollout 时间和首次冷启动总时间是三个不同概念。

## 正式 LIBERO 基线评测

`scripts/benchmark_libero.py` 使用官方 `lerobot-eval` 运行四套标准 LIBERO 基线：

- `libero_spatial`
- `libero_object`
- `libero_goal`
- `libero_10`

每个 suite 包含 10 个 task，每个 task 默认评测 10 episodes。固定协议为：

```text
policy=lerobot/pi05_libero_finetuned
seed=1000
batch_size=1
n_action_steps=10
compile_model=false
control_mode=relative
observation=2 x 256x256 RGB + 8D state
init_states=true
hard_reset=true
```

先跑最小 smoke：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
./.venv/bin/python scripts/benchmark_libero.py \
  --suites libero_spatial \
  --task-ids 0 \
  --n-episodes 1 \
  --seed 7 \
  --output-root outputs/benchmark/pi05-libero-smoke
```

运行单个 suite：

```bash
./.venv/bin/python scripts/benchmark_libero.py \
  --suites libero_spatial \
  --n-episodes 10 \
  --seed 1000 \
  --output-root outputs/benchmark/pi05-libero
```

运行全部四套标准 suite：

```bash
./.venv/bin/python scripts/benchmark_libero.py \
  --suites libero_spatial,libero_object,libero_goal,libero_10 \
  --n-episodes 10 \
  --seed 1000 \
  --output-root outputs/benchmark/pi05-libero
```

runner 会跳过已经存在 `eval_info.json` 的 suite。需要强制重跑时添加 `--force`。

输出结构：

```text
outputs/benchmark/pi05-libero/
├── status.json
├── summary.json
├── summary.csv
├── summary.md
└── <suite>/
    ├── command.txt
    ├── metadata.json
    ├── run.log
    ├── eval_info.json
    └── videos/
```

`summary.md` 是给人查看的结果表，`summary.csv` 用于后续统计或绘图，`summary.json` 保存完整结构化结果。正式评测结果应当同时记录 policy path、Git commit、seed 和评测协议，避免之后无法复现。

夜间自动续跑：

```bash
screen -dmS pi05-overnight bash scripts/run_overnight_benchmark.sh
```

该脚本会等待较短的 Spatial 前台任务结束后继续运行四套 suite，适合作为长时间无人值守任务。

### 2026-10-17 兼容性审计记录

本次没有直接下载最大的基础权重，而是先通过服务器端 Hugging Face API 读取两个候选仓库的 revision、文件列表和精确体积：

| checkpoint | revision | `model.safetensors` | 仓库总大小 | 用途 |
| --- | --- | ---: | ---: | --- |
| `lerobot/pi05_libero_finetuned` | `7152f13e34c6c115d808aea0e5d08aca74eac14b` | 7,473,096,344 B | 7,473,127,943 B（6.96 GiB） | 当前选择；直接做 LIBERO 基线评测 |
| `lerobot/pi05_libero_base` | `5fcf06fc42b6717e22ab885fd381a096574b12c7` | 14,467,165,872 B | 14,467,174,873 B（13.47 GiB） | 用于继续微调，不作为当前零样本评测入口 |

选择 `finetuned` 的原因：项目当前目标是先复现官方 LIBERO 成功率链路，而不是立刻从 base 开始训练；它体积更小，并且已经带有 LIBERO 的归一化状态。官方 LeRobot 文档给出的复现评测模型也是该 checkpoint。

checkpoint 自带 `config.json` 和 processor 状态，审计结果如下：

| 项目 | checkpoint 配置 | 当前 LIBERO 环境 | 结论 |
| --- | --- | --- | --- |
| 主相机 | `observation.images.image`，`3×256×256` | `agentview_image → image` | 匹配 |
| 腕部相机 | `observation.images.image2`，`3×256×256` | `robot0_eye_in_hand_image → image2` | 匹配 |
| 本体状态 | `observation.state`，8 维 | eef position + axis-angle + gripper qpos | 匹配 |
| 动作 | `action`，7 维 | 6D 末端增量 + 1D gripper | 匹配 |
| 控制方式 | 相对动作 | `control_mode=relative` | 匹配 |
| 数值精度 | `bfloat16` | RTX 4090D 支持 | 可推理 |
| 归一化 | STATE/ACTION `MEAN_STD`，VISUAL `IDENTITY` | checkpoint 自带 processor stats | 直接加载 |
| 额外图像槽 | 一个 `224×224` empty camera | processor 自动补齐 | 不需要第三个真实相机 |

模型内部 action chunk 长度为 50、flow-matching inference steps 为 10。checkpoint 文件中的 `n_action_steps` 是 50，但官方 LIBERO 复现协议明确使用 10，因此首轮评测脚本强制传入：

```text
--policy.n_action_steps=10
```

checkpoint 中 `compile_model=true`。第一次加载主要用于排查兼容性，编译会额外消耗启动时间和显存，所以脚本先使用：

```text
--policy.compile_model=false
```

链路稳定后可以另做开启/关闭编译的延迟对比，不能把两种配置的首次运行耗时直接比较。

### 权重下载与恢复

下载发生在 4090D 服务器，不经过本机。使用的环境变量是：

```bash
export HF_HOME=$PWD/cache/huggingface
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
```

后台会话名为 `pi05-download`。完整的可恢复下载方式为：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
mkdir -p checkpoints/lerobot-pi05-libero-finetuned logs
screen -dmS pi05-download bash -lc '\
  cd /root/autodl-tmp/pi05-libero-reproduction && \
  export HF_HOME=$PWD/cache/huggingface && \
  export HF_ENDPOINT=https://hf-mirror.com && \
  export HF_HUB_DISABLE_XET=1 && \
  .venv/bin/hf download lerobot/pi05_libero_finetuned \
    --local-dir checkpoints/lerobot-pi05-libero-finetuned \
    > logs/pi05-download.log 2>&1'
```

`hf download` 会在目标目录的 `.cache` 中保留 partial 文件；网络中断后重新执行相同命令即可续传。不要同时启动两个同名下载任务。检查方式：

```bash
screen -list
du -sh checkpoints/lerobot-pi05-libero-finetuned
tail -f logs/pi05-download.log
stat -c '%n %s bytes' checkpoints/lerobot-pi05-libero-finetuned/model.safetensors
```

完整权重文件应为 `7,473,096,344` bytes。下载开始前服务器持久盘 `/root/autodl-tmp` 总计 50GB、已用约 14GB、可用约 37GB，因此权重能够放入；暂未下载 1.9GB 训练数据，也未下载 13.47GiB base checkpoint，以免无目的占用空间。

旧实例上的本次下载于 2026-10-17 完成，耗时约 7 分 35 秒，日志结尾为 `Downloaded`、`EXIT_CODE=0`。这些权重和日志未随 Git 迁移，新实例需要重新下载。历史验证结果：

- `model.safetensors` 精确大小为 `7,473,096,344` bytes；
- safetensors header 可正常读取，共 812 个 tensor key；
- 下载后台会话已正常退出，没有残留第二个下载进程；
- 旧实例完成下载后持久盘约使用 21GB、剩余 30GB；新实例迁移代码后约有 50GB 可用；
- `scripts/eval_pi05_single.sh` preflight 正确通过权重检查，并以 exit code 3 停在预期的 Hugging Face 登录检查，没有错误启动评测或占用 GPU。

### Hugging Face 许可门槛

模型 processor 指向 `google/paligemma-3b-pt-224` tokenizer。服务器匿名访问镜像时已经实测返回：

```text
403 Forbidden: Please enable access to public gated repositories
```

因此“Pi0.5 权重下载完成”不代表“可以立刻推理”。需要使用者完成以下一次性操作：

1. 登录 Hugging Face，在 `google/paligemma-3b-pt-224` 页面接受 Gemma/PaliGemma 许可；
2. 创建至少具有 gated public repository read 权限的 token；
3. 在服务器运行 `.venv/bin/hf auth login`。

token 只应交给 Hugging Face CLI/OAuth，不写入 shell 脚本、README、Git、网页参数或聊天记录。2026-10-17 用户已通过 device OAuth 登录，镜像账户验证为 `yuhengchen`；PaliGemma revision `35e4f46485b4d07967e7e9935bc3786aad50687c` 的 tokenizer 已缓存并完成离线加载测试。

缓存文件包括 `config.json`、`tokenizer.json`、`tokenizer.model`、`tokenizer_config.json`、`special_tokens_map.json` 和 `added_tokens.json`。离线验证结果为 `GemmaTokenizer`、词表 257,152；任务句子编码为 12 个 token 并可正确还原。由于文件已经进入持久化 `HF_HOME`，即使以后执行 `hf auth logout`，评测脚本也会优先做离线缓存检查，不会强制长期保留账号 token。

### 最小评测脚本的保护措施

`scripts/eval_pi05_single.sh` 在调用模型前会依次检查：

1. `.venv/bin/lerobot-eval` 是否存在；
2. `model.safetensors` 是否存在；
3. 权重文件是否大于 7,000,000,000 bytes，避免拿 partial 文件启动；
4. PaliGemma tokenizer 能否完全离线加载；仅在缓存缺失时才要求 `hf auth whoami`；
5. 输出目录、环境变量和日志目录是否准备好。

默认评测等价于：

```text
suite=libero_spatial
task_id=0
seed=7
n_episodes=1
batch_size=1
observation=2 × 256×256 RGB + 8D state
action=7D relative control
n_action_steps=10
compile_model=false
```

可通过环境变量覆盖小范围测试参数，例如：

```bash
SUITE=libero_object TASK_ID=2 SEED=1000 N_EPISODES=1 \
  ./scripts/eval_pi05_single.sh
```

不要在首次验证时把 `N_EPISODES` 提高到 10，也不要去掉 `TASK_ID` 限制。一个 suite 包含 10 个 task，正式四套 benchmark 是 400 episodes；应先确认单 episode 的模型加载、动作方向、视频和成功判定完全正常。

### 当前边界

- 现有 Web 控制台同时支持 `idle`、`demo` 和真实 π0.5 模式。
- 官方 `lerobot-eval` 会输出主视角评测 MP4；现有七视角网页是独立的人类监控链路。
- 单任务策略评测和七视角 π0.5 控制已经通过；正式多任务基线评测使用独立的 benchmark runner。
- 官方全量训练示例按单张 80GB GPU 设计。RTX 4090D 24GB 已验证 batch size 1 推理，观察显存约 10.4GB；微调仍必须另行验证冻结范围、梯度检查点、batch size、累积步数和显存峰值。

## 安装或修复

完整脚本可以幂等重跑：

```bash
cd /root/autodl-tmp/pi05-libero-reproduction
./scripts/setup_remote.sh 2>&1 | tee -a logs/setup.log
```

脚本直接在服务器通过 `https://hf-mirror.com` 下载资产，不经过本机。镜像会对并发请求限流，因此下载固定为单 worker，并在请求报 429 后用 Hugging Face 本地清单复核 586 个文件及其大小。

`hf-libero==0.1.4` 的 `get_assets_path()` 不读取 `~/.libero/config.yaml` 中的 `assets` 字段。安装脚本会把包内预期目录软链接到持久化目录：

```text
.venv/lib/python3.12/site-packages/libero/libero/assets
  -> /root/autodl-tmp/pi05-libero-reproduction/assets
```

## 尚未执行

- 未下载 LIBERO 演示/训练数据
- 未运行 Pi0.5 微调或训练

Pi0.5 单任务真实推理和七视角 Web 控制已经在旧实例跑通。正式四套 LIBERO 基线在服务器迁移时中断；新实例完成环境和模型重建后需要从头执行。多 seed 平均和微调仍放在单 seed 基线之后。

## 工作记录

部署细节、当前状态和后续任务持续记录在 [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md)。新会话优先阅读该文件和 `outputs/smoke/report.json`。

