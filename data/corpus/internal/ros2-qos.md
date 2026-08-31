---
doc_id: ros2-qos
title: ROS 2 QoS 可靠性策略
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.09
expires: null
---

# RELIABLE 与 BEST_EFFORT

RELIABLE 要求底层重传，适合地图、目标点、模式切换等“丢了必须补”的指令与状态。BEST_EFFORT 不重传，适合激光、相机、IMU 等高频传感器：过期帧重传只会加剧延迟。

# 传感器与控制

默认订阅多为 RELIABLE + VOLATILE。若驱动发布 BEST_EFFORT，订阅端必须改成兼容配置，否则匹配失败、话题看起来“没数据”。控制环路读传感器时，应接受 BEST_EFFORT，不要为了“可靠”把激光改成 RELIABLE。

# Deadline 与 Liveliness

Deadline 用于检测传感器超时（例如 100ms 未收到 scan）。Liveliness 用于检测对端节点是否还在。两者触发时应进入安全停机，而不是继续用最后一帧速度指令。
