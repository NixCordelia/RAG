---
doc_id: sros2
title: SROS2 启用步骤（运维）
dept: ops
acl: [ops]
classification: confidential
version: 2025.06
expires: null
---

# 启用

生产镜像通过环境变量 `ROS_SECURITY_ENABLE=true` 与 `ROS_SECURITY_KEYSTORE=/opt/fleet/pki/prod` 启用。开发默认关闭。错误地在办公网打开安全强制会导致节点全部无法发现，表现为“空图”。

# 策略

权限治理文件由安全组签发，节点只能访问白名单话题。工程侧申请新话题需提交 `TOPIC-ACL` 工单，不得在 launch 里关闭 enforcement。
