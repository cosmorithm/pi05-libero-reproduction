# 开放问题与风险

## 高优先级

1. **JAX checkpoint 下载时间**：服务器 IPv4 可用，但 12.4GB 大 shard 的下载吞吐约
   2.5MB/s，可能需要较长时间。需要确认下载完整性和最终 `restore_params`。
2. **JAX 探针是否只调用 VLM 流**：代码必须保持 action expert 为 `None`，
   不触发 `action_out_proj` 或 flow matching。
3. **JAX 预处理选择**：同一张 smoke 图像采用同像素 resize，还是采用 OpenPI LIBERO
   官方 180 度翻转。先做 pilot，避免把方向差异误判为语言退化。
4. **seed=2000 的 `libero_10`**：目前没有结果，不能把三 suite 多 seed 说成完整多 seed。

## 中优先级

- Dashboard 的 token 通过 URL 查询参数传递；不要把它写进 Git 或公开文档。
- 当前公网映射只确认了 `8443 → 6006`，历史回放和实时控制台共用同一入口。
- `pi05_libero` JAX 模型加载与 Torch 的 7GB checkpoint 不是同一实现，不能逐权重等同。
- 失败回放尚未逐帧复核，目前的失败 task 只是计数证据。
