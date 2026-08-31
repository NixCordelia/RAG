---
doc_id: ros2-doc-actions
title: "ROS 2 docs · Actions"
dept: engineering
acl: [engineer, ops, intern]
classification: public
version: humble
expires: null
license: CC-BY-4.0
upstream: https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Basic/About-Actions.rst
---

> 摘自 ROS 2 Documentation（Humble），[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原文：<https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Basic/About-Actions.rst>
>
> 下列「中文要点」为入库时补充，便于中文检索；事实仍来自原文。

# 中文要点

Action 适合长时间任务：带反馈、可取消。服务是短请求响应，不要把长阻塞逻辑写在服务回调里。

# Actions

:local:

In ROS 2, an action refers to a long-running remote procedure call with feedback and the ability to cancel or preempt the goal.
For instance, the high-level state machine running a robot may call an action to tell the navigation subsystem to travel to a waypoint, which may take several seconds (or minutes) to do.
Along the way, the navigation subsystem can provide feedback on how far along it is, and the high-level state machine has the option to cancel or preempt the travel to that waypoint.

This structure is reflected in how an action message definition looks:

int32 request
---
int32 response
---
int32 feedback

In ROS 2, actions are expected to be long running procedures, as there is overhead in setting up and monitoring the connection.
If you need a short running remote procedure call, consider using a service <About-Services> instead.

Actions are identified by an action name, which looks much like a topic name (but is in a different namespace).

An action consists of two parts: the action server and the action client.

## Action server

The action server is the entity that will accept the remote procedure request and perform some procedure on it.
It is also responsible for sending out feedback as the action progresses and should react to cancellation/preemption requests.
For instance, consider an action to calculate the Fibonacci sequence with the following interface:

int32 order
---
int32[] sequence
---
int32[] sequence

The action server is the entity that receives this message, starts calculating the sequence up to `order` (providing feedback along the way), and finally returns a full result in `sequence`.

There should only ever be one action server per action name.
It is undefined which action server will receive client requests in the case of multiple action servers on the same action name.

## Action client

An action client is an entity that will request a remote action server to perform a procedure on its behalf.
Following the example above, the action client is the entity that creates the initial message containing the `order`, and waits for the action server to compute the sequence and return it (with feedback along the way).

Unlike the action server, there can be arbitrary numbers of action clients using the same action name.
