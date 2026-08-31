---
doc_id: ros2-services
title: 服务与动作
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.07
expires: null
---

# 服务

服务是一对一请求响应，适合模式切换、保存地图、触发标定。不要用服务传激光流。客户端应设置超时；服务端回调禁止执行超过数百毫秒的阻塞 IO，长任务改 Action。

# Action

Nav2 导航目标通过 Action 下发，可反馈进度与取消。取消后控制器必须进入刹车，而不是继续跟踪旧路径。
