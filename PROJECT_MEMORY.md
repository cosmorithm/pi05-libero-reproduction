# 项目记忆：Pi0.5-LIBERO 复现

> 这份文件用于跨会话接续工作。每次部署、验证、训练或评测后都应更新它。

## 项目边界

- 目标：在单张 RTX 4090D 24GB 上搭建并复现 Pi0.5 + LIBERO。
- 这是一个独立项目，不与此前的 NLP、Agent/Infra、CoT 或 GPU Keeper 项目混合。
- 当前阶段：2026-10-17 迁移到新实例后，代码、Git 历史、运行环境、LIBERO assets、Pi0.5 checkpoint、PaliGemma tokenizer、真实闭环评测和本地 Dashboard 均已恢复并复验；新服务器 benchmark smoke 为 1/1 成功，准备重新执行四套正式 baseline。

## 服务器与目录

- SSH 别名：`pi05-4090d`
- 实际入口：`root@connect.westb.seetacloud.com:23741`
- 主机名：`autodl-container-c85144bc1a-c9f2625b`
- GPU：NVIDIA GeForce RTX 4090 D，24 GB
- 远端项目根目录：`/root/autodl-tmp/pi05-libero-reproduction`
- Python 虚拟环境：`/root/autodl-tmp/pi05-libero-reproduction/.venv`
- Hugging Face 缓存：`/root/autodl-tmp/pi05-libero-reproduction/cache/huggingface`
- pip 缓存：`/root/autodl-tmp/pi05-libero-reproduction/cache/pip`
- LIBERO 资产：`/root/autodl-tmp/pi05-libero-reproduction/assets`
- 输出目录：`/root/autodl-tmp/pi05-libero-reproduction/outputs`
- 项目根目录已初始化服务器本地 Git（分支 `main`）。仓库只跟踪 README、PROJECT_MEMORY、固定 LeRobot commit 和 `scripts/`；`.venv`、权重、资产、缓存、日志、输出和 `.dashboard_token` 均被忽略。每次代码或文档改动都应先验证再在服务器提交。

## 已执行事项

- 在本机 `~/.ssh/config` 添加了 `pi05-4090d` 别名，并验证免交互登录成功。
- 将 LeRobot 源码固定到提交 `146d8474932c8b566717eb2738ba459337ab71c4`。
- 在 `autodl-tmp` 下建立独立项目、虚拟环境、缓存、资产和输出目录。
- 安装 Ubuntu 无头渲染依赖：EGL、OpenGL、GLEW、GLFW、OSMesa、FFmpeg 等。
- 从 PyTorch 官方 CUDA 12.8 wheel 源安装 GPU 版 PyTorch/torchvision。
- 已安装 LeRobot 的 `pi`、`libero`、`evaluation` extras。
- Hugging Face 下载配置为在服务器直接使用 `https://hf-mirror.com`，不经本机中转。
- 已运行 `scripts/smoke_libero.py`：创建 LIBERO Spatial task 0，reset、执行多步 7 维动作，并保存全部 7 路相机图像、实时进度和 JSON 报告。
- `hf-libero==0.1.4` 的 `get_assets_path()` 不读取配置文件中的资产路径，因此安装脚本会建立包内 `assets` 到项目持久化 `assets/` 的软链接。
- Hugging Face 镜像曾在下载后复核阶段返回 HTTP 429。最终已按缓存仓库清单逐项检查文件存在性与大小：586/586 通过，缺失 0。

## 当前状态

### 新服务器迁移状态（2026-10-17）

- 本机 SSH 别名 `pi05-4090d` 已改到端口 `23741`，免交互登录验证通过。
- Git 仓库及完整提交历史已恢复到 `/root/autodl-tmp/pi05-libero-reproduction`；当前为干净的 `main`，迁移前 HEAD 为 `263e28c`。
- 新实例的 `/root/autodl-tmp` 为 50 GB 持久盘；恢复环境、assets 和 checkpoint 后使用约 21 GB、剩余约 30 GB。
- `.venv`、`lerobot/`、`assets/`、`checkpoints/`、`cache/`、`outputs/` 和 `logs/` 被 `.gitignore` 排除，没有随 Git 迁移；其中环境、LeRobot、assets、checkpoint、smoke 输出和日志已在新实例重建。
- 旧端口 `37629` 已拒绝连接，旧实例约 73/100 的 Spatial benchmark 中间输出、视频和缓存目前不可取回；正式四套 benchmark 已中断，不应继续描述为正在运行。
- 旧公网 Dashboard 域名绑定旧容器，不能代表新服务器状态。新实例完成验证后需要重新启动 6006 服务并使用新的 SeetaCloud 映射。
- GitHub API 与仓库归档下载在新服务器可用，但 Git Smart HTTP 的 fetch/push 当前会超时；仓库历史通过本机临时中转完整恢复。后续提交可在服务器本地进行，推送前需修复 GitHub SSH/HTTPS 通道或继续使用本机中转。
- 新实例 setup 已通过：Python 3.12.3、PyTorch 2.11.0+cu128、transformers 5.5.4、LeRobot 0.6.2，`pip check` 无冲突，CUDA 2048×2048 矩阵乘法成功。
- LIBERO assets 经镜像断点续传后 586/586 校验通过；新实例 smoke 成功生成 7 路 256×256 图像，`outputs/smoke/report.json` 为 `status: ok`。
- `lerobot/pi05_libero_finetuned` 固定 revision 已通过服务器端镜像 + `hf-xet` 高性能通道恢复；`model.safetensors` 为 7,473,096,344 bytes，812 个 tensor key 校验通过。
- 新实例已通过 Hugging Face device OAuth 登录账号 `yuhengchen`；固定 PaliGemma revision 的 tokenizer 已缓存并通过完全离线加载，基础词表 257,152，含 added token 总长度 257,153。
- 新实例真实 `lerobot-eval` 复验成功：`libero_spatial` task 0、seed 7 在第 73 步完成，reward 1.0、success 1/1，rollout 约 8.06 秒，退出码 0。
- Dashboard v3 已在新实例的 `screen` 会话 `libero-web` 启动，本机 `http://127.0.0.1:6006/healthz` 返回 version 3，首页 HTTP 200；12 步 demo 成功。真实 Pi0.5 Dashboard episode 在第 74 步成功，模型加载 122.98 秒、首帧推理 0.448 秒、峰值 CUDA 显存约 9.08 GB，7 路 H.264 256×256 视频均为 75 帧。公网仍需为新容器重新映射 6006。
- 新实例 benchmark smoke 使用 runner 完成 task 0、seed 7、1 episode：1/1 成功，eval 约 8.11 秒，`summary.json/csv/md` 全部生成，观察显存约 10.4 GB。

### 旧服务器已验证基线（历史记录）

- 2026-10-17：仿真环境完成，真实 LIBERO 无头 reset/step 渲染通过。
- 实测版本：Python 3.12.3、LeRobot 0.6.2、PyTorch 2.11.0+cu128、torchvision 0.26.0+cu128、CUDA runtime 12.8。
- 仿真依赖：hf-libero 0.1.4、robosuite 1.4.0、robomimic 0.2.0、MuJoCo 3.8.1、Gymnasium 1.4.0、transformers 5.5.4。
- GPU 实测：`torch.cuda.is_available() == True`，识别 `NVIDIA GeForce RTX 4090 D`；2048×2048 CUDA 矩阵乘法成功。
- EGL 实测：64×64 MuJoCo 离屏渲染成功；随后 LIBERO Spatial task 0 的 reset/step 成功。
- smoke 结果：动作形状 `[1, 7]`，reward `[0.0]`，terminated/truncated 均为 `[false]`；7 路 RGB 图像均为 `[256, 256, 3]`。
- `pip check`：`No broken requirements found.`
- 资产校验：缓存仓库树包含 586 个文件，缺失 0、大小不符 0。
- 下载模型后 `autodl-tmp` 约使用 21 GB、剩余 30 GB（总盘 50 GB、使用 42%）。
- 旧实例曾以 `screen` 会话 `libero-web` 提供 6006 Web 服务；该服务未迁移到新实例。
- 安装日志：`logs/setup.log`；smoke 日志：`logs/smoke.log`。
- 结构化结果：`outputs/smoke/report.json`、`outputs/smoke/progress.json`；图像：`outputs/smoke/image.png` 至 `image7.png`。
- Web 控制台 v3：`scripts/libero_dashboard.py`，监听 6006，使用项目根目录 `.dashboard_token` 鉴权；展示 LIBERO 场景全部 7 路相机、任务语言、实时步数、动作模式和 GPU 遥测。控制区位于相机上方，相机卡片可选紧凑/标准/大图并响应式排列。启动脚本为 `scripts/start_dashboard.sh`，运行日志为 `logs/dashboard.log`，单次仿真日志为 `logs/dashboard-run.log`。
- 旧公网入口基址为 `https://u580081-955c-15394eb1.westb.seetacloud.com:8443/`；它绑定旧实例，仅作为历史记录，真实 token 不写入文档。
- LeRobot 保持两路策略输入不变；额外 `galleryview`、`birdview`、`frontview`、`sideview`、`robot0_robotview` 从底层 MuJoCo 状态直接渲染，仅用于人类观察。五路直渲染画面已按 OpenGL 坐标约定做垂直翻转。
- 2026-10-17 公网验证：控制台 v2 健康检查、首页、鉴权 API、7 个 PNG 端点均为 HTTP 200；从公网启动 12 步 demo episode 成功，7 路画面无黑屏、无重复且方向正常。
- 2026-10-17 Pi0.5 兼容性审计：标准 checkpoint 选择 `lerobot/pi05_libero_finetuned`，revision `7152f13e34c6c115d808aea0e5d08aca74eac14b`，约 6.96 GiB；checkpoint 明确要求两路 256×256 图像、8 维状态、7 维动作、一个 empty camera 和 mean/std 归一化，与当前 LIBERO 接口匹配。
- 权重已由服务器通过 `https://hf-mirror.com` 下载到 `checkpoints/lerobot-pi05-libero-finetuned`。下载耗时约 7 分 35 秒，日志 `logs/pi05-download.log` 记录 `EXIT_CODE=0`，后台会话已正常退出。
- 完整性验证：`model.safetensors` 精确大小 7,473,096,344 bytes；safetensors header 可读，共 812 个 tensor key；评测脚本 preflight 已通过文件检查。
- 用户已通过 Hugging Face device OAuth 登录，镜像账号为 `yuhengchen`。`google/paligemma-3b-pt-224` revision `35e4f46485b4d07967e7e9935bc3786aad50687c` 的 tokenizer 文件已缓存；离线加载验证为 `GemmaTokenizer`、词表 257,152，任务文本编码/还原正常。
- `scripts/eval_pi05_single.sh` 默认运行 `libero_spatial` task 0、seed 7、单 episode；固定 256×256 观测、相对控制、`n_action_steps=10`、关闭 `torch.compile`，结果写入 `outputs/eval/`。脚本已改为优先检查 tokenizer 离线缓存，只有缓存缺失才要求 HF 登录。
- 2026-10-17 第一次真实 Pi0.5 闭环成功：task 0 指令为“pick up the black bowl between the plate and the ramekin and place it on the plate”；模型在第 73/280 步完成，reward 1.0、success true、1/1 episode，rollout wall time 8.081 秒，进程 exit code 0。按日志时间戳，首次冷启动从进程启动到结束约 2 分 14 秒，大部分时间用于 CPU 侧模型构建和权重映射。
- 2026-10-17 Web 控制台 π0.5 模式完成：`scripts/pi05_episode.py` 使用 LeRobot `PI05Policy` 执行真实动作，同时采集两路策略相机和五路 MuJoCo 观察相机，逐帧写入 7 个 H.264 256×256 MP4。通过 `/api/run` 的 `action_mode=pi05` 启动完整 `libero_spatial` task 0、seed 7、280 步 episode 后再次成功，74 个动作步、reward 1.0、success true、7/7 路视频有效。本次模型加载 117.95 秒，首帧推理 0.446 秒，动作队列后续步约 0.006 秒。
- 2026-10-17 控制台日志中的访问 token 已脱敏；新版日志记录为 `[REDACTED]`，启动信息不再打印完整 token。
- 2026-10-17 正式基线 runner：`scripts/benchmark_libero.py` 使用 `lerobot-eval` 固定 seed 1000、batch size 1、`n_action_steps=10`、`compile_model=false`、硬重置和 256×256 观测。支持 suite 级断点续跑、`--task-ids` smoke、`--dry-run`、`--force`，结果汇总到 `outputs/benchmark/pi05-libero/summary.{json,csv,md}`。旧实例 smoke `libero_spatial` task 0、seed 7、1 episode 已通过；完整四套 400 episode 基线在迁移时中断。
- 2026-10-17 夜间编排脚本：`scripts/run_overnight_benchmark.sh` 等待短 Spatial 前台任务结束后自动运行全部四套 suite，日志写入 `logs/benchmark-overnight.log`。
- 评测期间观察到 GPU 显存约 10,417 MiB。输出位于 `outputs/eval/pi05-libero_spatial-task0-seed7/`：`eval_info.json`、`run.log` 和 H.264 256×256 主视角视频。视频 74 帧、80 fps、0.925 秒回放。

## 环境使用

```bash
ssh pi05-4090d
cd /root/autodl-tmp/pi05-libero-reproduction
source .venv/bin/activate
export LIBERO_CONFIG_PATH=$PWD/home/.libero
export HF_HOME=$PWD/cache/huggingface
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl
```

运行仿真自检：

```bash
python scripts/smoke_libero.py --suite libero_spatial --task-id 0 --seed 7 --steps 80 --action-mode demo
cat outputs/smoke/report.json
```

## 下一步

1. 从头执行四套 LIBERO baseline，完成后对照官方平均 97.5%。
2. 为已启动的 Dashboard 配置新公网映射。
3. 基线稳定后再增加多 seed、常驻模型 worker 和 24GB 显存下的参数高效微调。

