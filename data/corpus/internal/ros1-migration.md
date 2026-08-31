---
doc_id: ros1-migration
title: ROS 1 过渡方案（已废止）
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2022.03
expires: 2023-12-31
---

# 过渡桥

2022 年允许在工控机上同时运行 ROS 1 Noetic 与 `ros1_bridge`，用桥接 `/tf` 与 `/cmd_vel` 完成过渡。该方案在 2023 年底全部下线。

# 现状（过期描述）

若现场仍看到 `ros_bridge` 进程，应视为故障：现行标准是纯 ROS 2 Humble/Jazzy，禁止再启用桥接。本文仅作事故回溯，不能作为现行架构依据。
