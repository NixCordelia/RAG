---
doc_id: colcon
title: colcon 工作空间
dept: engineering
acl: [engineer, ops, intern]
classification: internal
version: 2024.04
expires: null
---

# 布局

工作空间为 `src/ build/ install/ log/`。源码只放 `src`。编译：`colcon build --symlink-install`。然后 `source install/setup.bash`。未 source 会出现 `Package not found`。

# 依赖

`package.xml` 声明依赖，`rosdep install --from-paths src --ignore-src -y` 补系统包。接口包变更后需先编译接口再编译使用方。

# 常见失败

混用 ROS 1 的 catkin 与 colcon、在错误的发行版下编译、忘记给自定义消息跑 `rosidl` 生成，都会导致类型不匹配。intern 上手只要求会 build 与 source。
