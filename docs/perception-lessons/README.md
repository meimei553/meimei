# 环境感知讲义

给零基础读 `fisheye_tool` 和 `pylon_ros2_camera` 用。这两份代码做的是几何感知：把鱼眼图变成 6 张平面小图，再拼成一张大图。语义构建（给路、人、障碍物起名字）还没出现在这两份代码里。

| 讲次 | 文件 | 内容 |
| --- | --- | --- |
| 第 1 讲 | [01-pipeline-and-python.md](01-pipeline-and-python.md) | 整条流水线、Python 语法、鱼眼节点、`fisheye_tool_3.py` |
| 第 2 讲 | [02-fisheye-processor-cpp.md](02-fisheye-processor-cpp.md) | 同一套算法的 C++ 版 `fisheye_processor.cpp`，以及相机节点在哪里调用它 |
| 第 3 讲 | [03-camera-spin.md](03-camera-spin.md) | `spin()` 怎么按帧率采图、改时间戳，以及有人订阅才发布 |
| 第 4 讲 | [04-open-and-grab.md](04-open-and-grab.md) | 找到相机、软件触发、只留最新一帧 |
| 第 5 讲 | [05-image-knobs.md](05-image-knobs.md) | 曝光、增益、裁剪、编码，以及它们为什么会影响标定 |
| 第 6 讲 | [06-the-rest-and-finish.md](06-the-rest-and-finish.md) | 其余服务、动作、型号文件和草稿；这两份代码到此为止 |

第 1 讲里有一处已更正：6 张小图排成 2 行 3 列，格子是满的。

`pylon_ros2_camera_base.hpp` 和节点里大量设置函数是同一个句型，第 5、6 讲按旋钮分组讲完，不再把同一句型抄 5000 遍。语义构建不在这两份压缩包里。
