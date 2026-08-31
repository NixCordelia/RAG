---
doc_id: ros2-doc-cross-compile
title: "ROS 2 docs · Cross compilation"
dept: engineering
acl: [engineer, ops, intern]
classification: public
version: humble
expires: null
license: CC-BY-4.0
upstream: https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Cross-Compilation.rst
---

> 摘自 ROS 2 Documentation（Humble），[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原文：<https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Cross-Compilation.rst>

Concepts/About-Cross-Compilation

# Cross-compilation

:local:

## Overview

Open Robotics provides pre-built ROS 2 packages for multiple platforms, but a number of developers still rely on `cross-compilation <https://en.wikipedia.org/wiki/Cross_compiler>`__ for different reasons such as:
 - The development machine does not match the target system.
 - Tuning the build for specific core architecture (e.g. setting -mcpu=cortex-a53 -mfpu=neon-fp-armv8 when building for Raspberry Pi3).
 - Targeting a file system other than the ones supported by the pre-built images released by Open Robotics.

## How does it work ?

Cross-compiling simple software (e.g. no dependencies on external libraries) is relatively simple and only requiring a cross-compiler toolchain to be used instead of the native toolchain.

There are a number of factors which make this process more complex:
 - The software being built must support the target architecture.
Architecture specific code must be properly isolated and enabled during the build according to the target architecture.
Examples include assembly code.
 - All dependencies (e.g. libraries) must be present, either as pre-built or cross-compiled packages, before the target software using them is cross-compiled.
 - When building software stacks (as opposed to standalone software) using build tools (e.g. colcon), it is expected that the build tool provides a mechanism to allow the developer to enable cross-compilation on the underlying build system used by each piece of software in the stack.

## Alternatives

An alternative to cross-compilation is to `build multi-platform Docker images <https://github.com/docker/buildx#building-multi-platform-images>`__ using `docker buildx`.
