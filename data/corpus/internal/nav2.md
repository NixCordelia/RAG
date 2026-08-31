---
doc_id: nav2
title: Nav2 导航栈要点
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.09
expires: null
---

# 组成

Nav2 含地图服务、AMCL 或 SLAM 定位、规划器、控制器、行为树。行为树决定 recovery：清代价地图、自旋、等待。不要在业务节点里另写一套绕障状态机与 Nav2 抢控制权。

# 定位与规划失败

规划器依赖全局代价地图，而代价地图依赖 TF 与传感器。若行为树报 `No valid path`，顺序排查：定位是否收敛、`map→odom` 是否存在、激光坐标系是否与 URDF 一致、局部地图 inflations 是否过大。

# 代价地图

障碍层订阅 scan 或 pointcloud。QoS 必须与驱动兼容。静态层来自 map_server。机器人足迹 footprint 过小会擦边，过大会在窄走廊判死。
