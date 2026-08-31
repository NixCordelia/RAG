"""ROS 领域中英同义词，给检索多路 RRF 用。按主题组织，不是按某道评测题写的正则。"""

from __future__ import annotations

import re

# (问句里出现这些词 → 追加这一路检索词)
ENTRIES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"QoS|qos|BEST_EFFORT|RELIABLE|可靠性|通信策略|通信质量"), "QoS reliability BEST_EFFORT RELIABLE deadline"),
    (re.compile(r"Action|action|长任务|长时间任务|可取消"), "Action goal feedback cancel"),
    (re.compile(r"服务回调|service callback|Service"), "service callback 阻塞 超时"),
    (re.compile(r"代价地图|costmap|障碍层"), "costmap scan lidar"),
    (re.compile(r"日志|logging|/rosout|rosout"), "/rosout logging"),
    (re.compile(r"统计|statistics|/statistics", re.I), "/statistics topic statistics"),
    (re.compile(r"\bTF\b|tf2|坐标|lookup|时钟|chrony|时间戳|点云融合"), "TF lookup chrony odom map"),
    (re.compile(r"composition|组件容器|共享库"), "composition component_container shared library"),
    (re.compile(r"命名空间|namespace|PushRosNamespace"), "namespace 话题名前缀"),
    (re.compile(r"DOMAIN_ID|组网|发现"), "ROS_DOMAIN_ID discovery multicast"),
]


def extra_queries(question: str) -> list[str]:
    q = question or ""
    out: list[str] = []
    for pat, extra in ENTRIES:
        if pat.search(q) and extra not in out:
            out.append(extra)
    return out
