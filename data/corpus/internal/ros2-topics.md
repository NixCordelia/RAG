---
doc_id: ros2-topics
title: ROS 2 话题通信
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.08
expires: null
---

# 发布订阅

话题是匿名的多对多通道。发布者与订阅者通过话题名与消息类型匹配。类型必须完全一致，包括接口包版本。调试用 `ros2 topic echo /name` 与 `ros2 topic hz /name`。

# 命名

全局名以 `/` 开头。相对名受命名空间影响，launch 中常用 `PushRosNamespace` 给机器人加前缀，例如 `/robot_a/scan`。重映射写在 `--ros-args -r scan:=front_scan`。

# 队列

订阅队列过小会在回调耗时抖动时丢消息。激光默认 depth 建议 5–10；控制指令 depth=1 并配合 BEST_EFFORT 以外的可靠策略时，应明确“只要最新值”的语义，避免堆积过期速度指令。
