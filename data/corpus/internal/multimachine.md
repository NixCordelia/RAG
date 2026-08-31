---
doc_id: multimachine
title: 多机 ROS 2 组网
dept: engineering
acl: [engineer, ops]
classification: internal
version: 2024.06
expires: null
---

# 域与发现

同一局域网内，只有 ROS_DOMAIN_ID 相同的节点能互相发现。多机器人同网段必须分配不同 DOMAIN_ID，否则 TF 与话题会串台。发现默认用组播；公司交换机禁用组播时应改 Fast DDS 或 Cyclone 的单播 peer 列表。

# 时间同步

多机 TF 与点云融合要求时钟偏差小于数毫秒。使用 chrony 对准 NTP。时间不同步时表现为点云抖动、TF lookup 超期，容易被误判为 QoS 问题。

# 带宽

多机传原始点云会打满 Wi-Fi。应在传感器机上降采样或抽特征后再发布。若必须传流，配合 BEST_EFFORT，不要对点云开 RELIABLE。
