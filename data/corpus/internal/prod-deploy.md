---
doc_id: prod-deploy
title: 生产 DDS 与密钥落盘
dept: ops
acl: [ops]
classification: confidential
version: 2025.11
expires: null
---

# 发现端口

生产集群 Fast DDS 单播发现固定使用 10.8.0.12:7412 与 10.8.0.13:7412，禁止改回组播。变更必须走变更单 OPS-441。

# 密钥

SROS 身份文件存放于 `/opt/fleet/pki/prod/`，权限 0750，属主 `dds:dds`。私钥不得进入工程仓库或 Wiki 附件。轮换周期 90 天，由 ops 值班脚本 `rotate-pki.sh` 执行。

# 日志

生产节点禁止 `ros2 topic echo` 到开发笔记本。抓包仅允许在跳板机 `ops-jump-03` 上、工单号写入 `/var/log/fleet/capture.log`。
