# 环境感知讲义

给零基础读 `fisheye_tool` 和 `pylon_ros2_camera` 用。这两份代码做的是几何感知：把鱼眼图变成 6 张平面小图，再拼成一张大图。语义构建（给路、人、障碍物起名字）还没出现在这两份代码里。

| 讲次 | 文件 | 内容 |
| --- | --- | --- |
| 第 1 讲 | [01-pipeline-and-python.md](01-pipeline-and-python.md) | 整条流水线、Python 语法、鱼眼节点、`fisheye_tool_3.py` |
| 第 2 讲 | [02-fisheye-processor-cpp.md](02-fisheye-processor-cpp.md) | 同一套算法的 C++ 版 `fisheye_processor.cpp`，以及相机节点在哪里调用它 |

第 1 讲里有一处已更正：6 张小图排成 2 行 3 列，格子是满的。
