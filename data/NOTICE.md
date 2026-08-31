# 语料来源

知识库分两层，不要混成「全部自己写」或「把 docs.ros.org 整站镜像进来」。

## `data/corpus/internal/`

平台内部 Wiki：权限、过期页、生产端口/密钥、入职流程。公开手册里没有这些字段，所以按内部规程结构撰写，用于检索过滤和评测，不是官方 ROS 文档的替代。

## `data/corpus/public/`

ROS 2 官方文档摘录（Humble），许可证 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。

- 上游仓库：https://github.com/ros2/ros2_documentation
- 每页 YAML 的 `upstream` 指向对应 `.rst`
- 未收录与内部 SOP 高度重叠的 Topics / Services / Nodes / Launch / QoS / TF / Domain ID / Executors / Security，避免评测题被官方同主题页挤出 Top-K

重新拉取（覆盖已有文件需先删 `data/corpus/public/*.md`）：

```powershell
python -m rag sync-public
```

与 `python -m rag.sync_public` 相同。当前摘录 12 篇（Actions、Parameters、Interfaces、Client libraries、CLI、Discovery、Composition、Cross compilation、RMW、Logging、RQt、Topic statistics）。

改编说明：入库时去掉了部分 Sphinx 指令，并加上 YAML 头（acl、license、upstream）。正文仍来自上述仓库。若干公开页另有中文要点（日志 `/rosout`、Action、Topic Statistics `/statistics`、composition 共享库），便于中文问句命中，事实仍对应原文。
