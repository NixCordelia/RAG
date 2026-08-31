---
doc_id: ros2-nodes
title: ROS 2 节点与生命周期
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.08
expires: null
---

# 节点

ROS 2 进程通过 Node 接入计算图。一个可执行文件可持有多个节点。节点名在同一 ROS_DOMAIN_ID 下应唯一，启动时可用 `ros2 run pkg exe --ros-args -r __node:=alias` 改名。

# 生命周期

Managed Node 使用生命周期状态机：Unconfigured → Inactive → Active → Finalized。传感器驱动建议在 Inactive 完成参数校验与硬件自检，收到 activate 后再打开设备，避免 launch 竞态导致 TF 迟到。

# 执行器

回调由 Executor 调度。单线程 SingleThreadedExecutor 适合逻辑简单的节点；激光与控制同进程时优先 MultiThreadedExecutor，并为订阅设置独立 Callback Group，防止控制定时器被重回调阻塞。
