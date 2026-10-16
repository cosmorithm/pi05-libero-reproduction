# 项目记忆：Pi0.5-LIBERO 复现

> 这份文件用于跨会话接续工作。每次部署、验证、训练或评测后都应更新它。

## 项目边界

- 目标：在单张 RTX 4090D 24GB 上搭建并复现 Pi0.5 + LIBERO。
- 这是一个独立项目，不与此前的 NLP、Agent/Infra、CoT 或 GPU Keeper 项目混合。
- 当前阶段：LeRobot/PyTorch/LIBERO 仿真、Pi0.5 权重与 tokenizer 缓存、第一次真实单任务闭环评测均已完成；尚未下载训练数据或微调。

## 服务器与目录

- SSH 别名：`pi05-4090d`
- 实际入口：`root@connect.westb.seetacloud.com:37629`
- 主机名：`autodl-container-470e41955c-15394eb1`
- GPU：NVIDIA GeForce RTX 4090 D，24 GB
- 远端项目根目录：`/root/autodl-tmp/pi05-libero-reproduction`
- Python 虚拟环境：`/root/autodl-tmp/pi05-libero-reproduction/.venv`
- Hugging Face 缓存：`/root/autodl-tmp/pi05-libero-reproduction/cache/huggingface`
- pip 缓存：`/root/autodl-tmp/pi05-libero-reproduction/cache/pip`
- LIBERO 资产：`/root/autodl-tmp/pi05-libero-reproduction/assets`
- 输出目录：`/root/autodl-tmp/pi05-libero-reproduction/outputs`

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

- 2026-10-17：仿真环境完成，真实 LIBERO 无头 reset/step 渲染通过。
- 实测版本：Python 3.12.3、LeRobot 0.6.2、PyTorch 2.11.0+cu128、torchvision 0.26.0+cu128、CUDA runtime 12.8。
- 仿真依赖：hf-libero 0.1.4、robosuite 1.4.0、robomimic 0.2.0、MuJoCo 3.8.1、Gymnasium 1.4.0、transformers 5.5.4。
- GPU 实测：`torch.cuda.is_available() == True`，识别 `NVIDIA GeForce RTX 4090 D`；2048×2048 CUDA 矩阵乘法成功。
- EGL 实测：64×64 MuJoCo 离屏渲染成功；随后 LIBERO Spatial task 0 的 reset/step 成功。
- smoke 结果：动作形状 `[1, 7]`，reward `[0.0]`，terminated/truncated 均为 `[false]`；7 路 RGB 图像均为 `[256, 256, 3]`。
- `pip check`：`No broken requirements found.`
- 资产校验：缓存仓库树包含 586 个文件，缺失 0、大小不符 0。
- 下载模型后 `autodl-tmp` 约使用 21 GB、剩余 30 GB（总盘 50 GB、使用 42%）。
- 当前没有安装、下载或训练进程；`screen` 会话 `libero-web` 正在提供 6006 Web 服务。关机不会丢失项目，但再次开机后需要重启该服务。
- 安装日志：`logs/setup.log`；smoke 日志：`logs/smoke.log`。
- 结构化结果：`outputs/smoke/report.json`、`outputs/smoke/progress.json`；图像：`outputs/smoke/image.png` 至 `image7.png`。
- Web 控制台 v2：`scripts/libero_dashboard.py`，监听 6006，使用项目根目录 `.dashboard_token` 鉴权；展示 LIBERO 场景全部 7 路相机、任务语言、实时步数、演示动作和 GPU 遥测。控制区位于相机上方，相机卡片可选紧凑/标准/大图并响应式排列。启动脚本为 `scripts/start_dashboard.sh`，运行日志为 `logs/dashboard.log`，单次仿真日志为 `logs/dashboard-run.log`。
- 公网入口基址：`https://u580081-955c-15394eb1.westb.seetacloud.com:8443/`，访问时追加 `.dashboard_token`，不要在文档内保存真实 token。
- LeRobot 保持两路策略输入不变；额外 `galleryview`、`birdview`、`frontview`、`sideview`、`robot0_robotview` 从底层 MuJoCo 状态直接渲染，仅用于人类观察。五路直渲染画面已按 OpenGL 坐标约定做垂直翻转。
- 2026-10-17 公网验证：控制台 v2 健康检查、首页、鉴权 API、7 个 PNG 端点均为 HTTP 200；从公网启动 12 步 demo episode 成功，7 路画面无黑屏、无重复且方向正常。
- 2026-10-17 Pi0.5 兼容性审计：标准 checkpoint 选择 `lerobot/pi05_libero_finetuned`，revision `7152f13e34c6c115d808aea0e5d08aca74eac14b`，约 6.96 GiB；checkpoint 明确要求两路 256×256 图像、8 维状态、7 维动作、一个 empty camera 和 mean/std 归一化，与当前 LIBERO 接口匹配。
- 权重已由服务器通过 `https://hf-mirror.com` 下载到 `checkpoints/lerobot-pi05-libero-finetuned`。下载耗时约 7 分 35 秒，日志 `logs/pi05-download.log` 记录 `EXIT_CODE=0`，后台会话已正常退出。
- 完整性验证：`model.safetensors` 精确大小 7,473,096,344 bytes；safetensors header 可读，共 812 个 tensor key；评测脚本 preflight 已通过文件检查。
- 用户已通过 Hugging Face device OAuth 登录，镜像账号为 `yuhengchen`。`google/paligemma-3b-pt-224` revision `35e4f46485b4d07967e7e9935bc3786aad50687c` 的 tokenizer 文件已缓存；离线加载验证为 `GemmaTokenizer`、词表 257,152，任务文本编码/还原正常。
- `scripts/eval_pi05_single.sh` 默认运行 `libero_spatial` task 0、seed 7、单 episode；固定 256×256 观测、相对控制、`n_action_steps=10`、关闭 `torch.compile`，结果写入 `outputs/eval/`。脚本已改为优先检查 tokenizer 离线缓存，只有缓存缺失才要求 HF 登录。
- 2026-10-17 第一次真实 Pi0.5 闭环成功：task 0 指令为“pick up the black bowl between the plate and the ramekin and place it on the plate”；模型在第 73/280 步完成，reward 1.0、success true、1/1 episode，rollout wall time 8.081 秒，进程 exit code 0。按日志时间戳，首次冷启动从进程启动到结束约 2 分 14 秒，大部分时间用于 CPU 侧模型构建和权重映射。
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

1. 将 Pi0.5 策略运行、真实成功状态和七视角录制接入现有 Web 控制台。
2. 增加 GPU 遥测和模型加载/推理延迟的结构化记录。
3. 扩展到 3 个任务、每任务多个 episode/seed，得到小规模可信基线。
4. 再决定是否下载训练数据并做 24GB 显存下的参数高效微调。

