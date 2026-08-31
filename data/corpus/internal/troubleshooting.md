---
doc_id: troubleshooting
title: 现场排障清单
dept: engineering
acl: [engineer, ops, intern]
classification: internal
version: 2024.08
expires: null
---

# 看不到话题

依次检查：是否 source 对应 workspace、ROS_DOMAIN_ID 是否一致、防火墙是否丢组播、发布/订阅 QoS 是否兼容、话题名是否被 namespace 改写。

# TF 报错

`Could not transform` 通常是时间戳为零、use_sim_time 不一致，或静态外参未发布。用 `ros2 topic echo /tf_static` 确认。

# 导航画龙

先降最大速度，再看局部代价地图是否把机器人自身轮廓当成障碍（footprint 未减去内缩）。不要先改规划器插件。
