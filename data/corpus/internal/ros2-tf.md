---
doc_id: ros2-tf
title: TF2 坐标与外参
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.07
expires: null
---

# 树结构

TF2 维护有向树，不能有环。常见链：`map → odom → base_link → sensor_frame`。`map→odom` 由定位模块发布，`odom→base_link` 由里程计发布。两源抢同一个 parent-child 会导致树跳动。

# 时间戳

lookup 必须使用消息自带 stamp。用 `Time.now()` 查历史扫描会失败或插值错误。多机点云融合若时钟不同步，lookup 会超期或插值失败，应先对时再查树。外参标定结果写入 `base_link → lidar` 静态 TF，启动时用 `tf2_ros/static_transform_publisher` 或 URDF。

# 诊断

`ros2 run tf2_tools view_frames` 导出 PDF 检查断链。Nav2 规划失败时，先确认是否缺少 `map→odom` 或 `odom→base_link`，再查代价地图。
