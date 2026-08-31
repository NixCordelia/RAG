---
doc_id: ros2-launch
title: Launch 与参数
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.05
expires: null
---

# Python launch

ROS 2 推荐 Python launch。用 `OpaqueFunction` 做运行时分支。传感器与 Nav2 分两个 launch，顶层 include，便于仿真只起导航。

# 参数

节点参数来自 YAML，键必须挂在节点名下。改 QoS 深度或坐标系时走参数而不是重编译。`use_sim_time` 在仿真为 true，实车必须 false，混用会导致 TF 外推失败。

# 组合

一组机器人用同一个 launch、不同 namespace 与 DOMAIN_ID。不要复制多份 launch 文件只改话题名。
