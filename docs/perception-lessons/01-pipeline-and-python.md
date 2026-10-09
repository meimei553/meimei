# 第 1 讲：相机出图，Python 把鱼眼圆摊开

这一讲对应两个正在被启动的文件：

- `fisheye_tool/fisheye_tool/fisheye_stitching_node.py`
- `fisheye_tool/fisheye_tool/fisheye_tool_3.py`

同目录里的 `fisheye_tools.py`、`fisheye_tools_2.py`、`fisheye_tools_numba.py`，以及文件名带日期、`_bk`、`copy` 的文件，都是旧草稿。`setup.py` 里登记的命令只调用 `fisheye_stitching_node.py` 的 `main`。

## 更正

6 张小图的网格是 **2 行 3 列**，6 个格子都用上。上一版口误说成 3 行 3 列、空出 3 格。算法是：

```text
列数 = ceil(sqrt(6)) = 3
行数 = ceil(6 / 3) = 2
```

C++ 版用同样的摆法：上面 3 张，下面 3 张。

## 这条流水线在干什么

机器人上的工业相机拍出一张圆形鱼眼图。`pylon_ros2_camera` 把图放到一条叫话题的通道上。`fisheye_tool` 把图拿走，用标定算出每个像素对应空间里的哪一条射线，再投到 6 个平面上，拼成一张大图发出去。

这是几何感知。语义构建是后面的步骤，要给图里的东西起名字。这两份代码停在「把图变好用」。

配置路径写成 `/home/unitree/...`。Unitree 是四足机器人的牌子，这套程序准备跑在机器人电脑上。

真正的入口在 `setup.py`：

```python
'fisheye_stitching_node = fisheye_tool.fisheye_stitching_node:main'
```

命令 `fisheye_stitching_node` 会去调用 `main`。

## 先记住这几个词

- 程序从上往下读。行首空格叫缩进，用来表示「这几行属于上面那一句」。
- `import` 把别人写好的工具拿进来。`from A import B` 只拿 A 里面的 B。
- `def 名字():` 给一组动作起名字。写 `名字()` 就是把这组动作做一遍。
- `class 名字:` 是一份设计图。`名字()` 按设计图做出一个具体对象。
- `self` 是这个对象自己。`self.bridge` 是「我自己的那只转换工具」。
- 括号里的输入叫参数。`max_points=5000000` 表示不填时就用 500 万。
- 引号包住的是字符串。`f'话题: {self.input_topic}'` 会把花括号里的变量换成它的值。
- `None` 表示还没有值。
- `if / else`：条件成立走这边，否则走那边。
- `try / except`：先尝试；出错就跳到 except，程序不要整段崩掉。
- `[]` 是列表。`{"n": 向量, "name": "north"}` 是字典，用名字取值。
- 话题是 ROS 2 里程序之间传数据的通道。发布者往里放，订阅者从里面拿。图像类型叫 `sensor_msgs/Image`。
- 节点是 ROS 2 里一个正在运行的程序。
- 标定是事先量好的镜头弯曲方式。`ocam.mat` 来自一套叫 OCamCalib 的鱼眼标定。

## 鱼眼节点：收图、交给算法、再发出去

文件开头把工具拿进来：

| 行 | 代码在做什么 |
| --- | --- |
| 1 | `rclpy` 是 ROS 2 的 Python 库 |
| 2 | `Node` 是节点的设计图，自己的类要继承它 |
| 3 | `Image` 是图像消息，里面有宽、高、像素和拍摄时间 |
| 4 | `CvBridge` 在 ROS 图像和 OpenCV 图像之间转换 |
| 5 | `cv2` 是 OpenCV，做翻转和颜色转换 |
| 6 | `numpy` 把一张图当成一个大数组 |
| 7 | `os` 用来问「这个文件在不在」 |
| 8 | `scipy.io` 读 MATLAB 的 `.mat` |
| 9 | `#` 开头是注释，程序跳过 |
| 10 | 从同包的 `fisheye_tool_3.py` 拿出 `process_fisheye`。点号表示同一个包 |
| 11 | `time` 用来掐秒表 |
| 12 | `MultiThreadedExecutor` 被导入了，后面的 `main` 没有用它 |
| 13–14 | `threading` 开一条额外工作线；`queue` 是两条工作线之间的传送带 |

`class FisheyeStitchingNode(Node)` 表示这个类是一种节点。`__init__` 是构造函数，对象一诞生就自动做准备工作。`super().__init__('fisheye_stitching_node')` 先做父类的准备，并把节点命名为 `fisheye_stitching_node`。

接着用同一种句子登记 7 个参数。`declare_parameter('名字', 默认值)` 向 ROS 登记一个可调参数：

- `ocam_path`：镜头标定文件
- `valid_range_path`：掩码，标出鱼眼圆里哪些像素有效
- `max_points`：最多拿 500 万个像素去算
- `img_res`：每一小块是 512×512
- `patch_size`：每一小块在平面上的边长，默认 1.5
- `input_topic`：默认 `/my_camera/pylon_ros2_camera_node/image_raw`。三段分别是命名空间、相机节点名、原图话题
- `output_topic`：默认 `stitched_image`

`get_parameter(...).value` 把登记的值读进 `self`。然后造一个 `CvBridge`，把两份标定先设成 `None`，再调用 `load_calibration_data()`。标定只在启动时读一次。

`queue.Queue(maxsize=1)` 是只能放 1 张图的传送带。鱼眼计算慢，算不过来就丢图，避免越积越慢。

`create_subscription(Image, 话题, image_callback, 1)` 表示：每来一张图就调用 `image_callback`。`create_publisher` 负责把结果发出去。`get_logger().info(...)` 打一条带时间的启动日志。

`threading.Thread(target=self.process_queue)` 再开一条线程。收图的函数必须很快返回，重计算放到旁边这条线上。

`process_queue` 里 `while rclpy.ok()` 表示只要 ROS 还没退出就一直循环。`get(timeout=0.1)` 最多等 0.1 秒。队列空会抛出 `queue.Empty`，抓住之后 `continue`，回到循环开头。

`load_calibration_data`：`os.path.exists` 先问文件在不在。`sio.loadmat(路径)['ocam']` 读出 MATLAB 结构。文件不在就 `return`，这时数据仍是 `None`，后面每张图都会被拒绝。`except Exception as e` 抓住读文件时的其他错误，`str(e)` 把错误变成能读的句子。

`process_image(msg)` 处理一张图：

- 第 109 行 `print` 是 Python 自己的打印。
- 紧跟着的三引号字符串不是函数说明。说明必须是函数里的第一句。这里只是造了一个字符串然后扔掉。
- `msg.header.stamp` 是相机拍摄时刻。`header` 是每条 ROS 消息头上的公共信息。
- 两个 ROS 时间相减得到纳秒，除以 `1e9` 变成秒，这是图在路上走了多久。
- `ocam_data is None or valid_range_data is None` 时警告并返回。`or` 表示有一个成立即可。
- `imgmsg_to_cv2(..., 'bgr8')` 把 ROS 图变成 OpenCV 图。`bgr8` 是蓝、绿、红，各 8 位。
- `cv2.flip(cv_image, -1)` 同时上下、左右翻转，也就是旋转 180 度。
- `patches, big_img = process_fisheye(...)` 拿到 6 张小图和一张大图。

时间日志和变量名对不上，看终端时以第一次那句为准：

- `process_time` 量的是 ROS 图转 OpenCV
- `convert_time` 量的是 `process_fisheye`
- `fish_eye_time` 量的是大图再转回 ROS 消息

后面又把这三个数印成「总时间、转换时间、鱼眼处理时间」。中间那个数才是鱼眼算法本身的时间。

`cv2.COLOR_RGB2BGR` 把算法用的红绿蓝转回 OpenCV 的蓝绿红。`cv2_to_imgmsg` 包回 ROS 图像。`stitched_msg.header = msg.header` 抄来原图的时间和坐标系。`publish` 把大图发出去。`len(patches)` 是小图张数，这里是 6。

`image_callback` 只做一件事：`put(msg, block=False)`。传送带满了就立刻失败，变成 `queue.Full`，于是丢掉这一张新图。传送带里原来那张还在。丢掉的是新来的，留下的是还没算完的那张。

`main`：

- `rclpy.init` 让程序加入机器人系统
- `FisheyeStitchingNode()` 一造出来，订阅、发布、读标定、开线程全部发生
- `rclpy.spin` 让主线程一直等消息
- Ctrl+C 之后 `destroy_node` 和 `shutdown`
- `if __name__ == "__main__"` 表示这个文件被直接运行时才进入 `main`。被别人 `import` 时不启动节点

## 几何：像素变成射线，再画到 6 个平面上

画面是这样的。鱼眼镜头把周围很大范围的光线挤进一张圆形图。标定回答：图上某个像素，对应空间中哪一个方向。方向用一根长度为 1 的箭头表示，箭头尖端落在单位球面上。

然后选 6 个和这个球相切的平面。每个平面只收朝向自己这半边的箭头，画成 512×512 的小图。6 张再拼成 2 行 3 列的大图。

`cam2world(m, ocam_model)`：

- `m` 是 2 行很多列。第 0 行是列坐标，第 1 行是行坐标。`.shape[1]` 是点的个数。
- `ss` 是多项式系数，描述离圆心越远、光线弯得越厉害。
- `xc, yc` 是鱼眼圆的中心，单位是像素。
- `c, d, e` 组成 2×2 矩阵 `A = [[c, d], [e, 1]]`，修正像素不是完美正方形的情况。
- `np.linalg.inv(A)` 求逆。`@` 是矩阵乘法。
- `astype(np.float32)` 改成 32 位小数。
- 最后每个箭头除以自己的长度，变成长度为 1 的方向。

`getpoint`：`r` 是像素离模型中心的距离。`ss[::-1]` 把系数倒过来，为了和 MATLAB 的多项式顺序对齐。`np.polyval` 用这个距离算出 z。`vstack` 把 x、y、z 叠成 3 行。

`define_planes` 造 6 个平面：

- 北极，法线 `(0, 0, 1)`
- 纬度 30 度一层 2 个。`linspace(0, 2*pi, 3)[:-1]` 取一圈上的位置并丢掉最后一个，因为 0 度和 360 度是同一个方向，所以剩下 0 度和 180 度
- 纬度 60 度一层 3 个，经度是 0 度、120 度、240 度
- `pi/180` 把角度换成弧度

`project_patch`：

- 法线也变成长度 1
- 点和法线的点积大于等于 0，说明在前半球。背面的点这张小图不要
- 一个点都没有，就返回全黑图
- 减去沿着法线的那一段，点就贴到平面上
- `null_space` 找出两个和法线垂直的方向，于是平面上的点可以写成二维坐标 `(u, v)`
- 只留落在边长 `patch_size` 的正方形里的点
- `rescale` 把坐标缩放到 `1` 到 `512`。从 1 开始是因为这段从 MATLAB 移植过来，MATLAB 下标从 1 数
- 写进图像时再减 1，因为 NumPy 下标从 0 数。颜色写在 `[行, 列]`，所以 `v` 在前、`u` 在后
- 颜色先换成 0 到 1，写出图像时乘回 255

`process_fisheye` 把上面串起来：

1. BGR 换成 RGB
2. `np.where(valid_range_data == 1)` 找出有效像素
3. 点太多就无放回随机抽 500 万个。`replace=False` 表示不重复
4. `cam2world` 得到单位箭头，再把 z 取相反数，让北极平面对准要展开的方向
5. 取出对应颜色并除以 255
6. `Parallel(n_jobs=-1)` 把 6 个平面分给多个 CPU 核一起算
7. 拼成 2 行 3 列。先造一张白布，空格子会保持白色；这里 6 个格子都贴满，没有空格
8. 返回 6 张小图和这张大图

四行 `print` 只是打印四段耗时：颜色转换、像素变射线、6 个平面、拼大图。

## 相机节点怎样把图送出来

启动文件 `pylon_ros2_camera.launch.py` 里：

- `camera_id` 默认 `my_camera`，用作命名空间
- `node_name` 默认 `pylon_ros2_camera_node`
- 两者接上驱动内部的 `image_raw`，就是鱼眼节点默认订阅的那条话题
- `parameters` 读入 `default.yaml`

你这份 `default.yaml` 多了三行：

```yaml
ocam_yaml_path: "/home/unitree/ros_ws/src/pylon_ros2_camera/pylon_ros2_camera_wrapper/ocam.yaml"
valid_mask_path: "/home/unitree/ros_ws/src/pylon_ros2_camera/pylon_ros2_camera_wrapper/valid_mask.png"
enable_fisheye_stitch: true
```

这三行打开 C++ 版的同一套处理。Python 读 `.mat`，C++ 读 `ocam.yaml` 和 `valid_mask.png`。

`pylon_ros2_camera_wrapper.cpp` 的 `main` 做五件事：让打印立刻出现、`rclcpp::init`、允许 yaml 参数直接进来、造出相机节点、`spin` 停在那里收图。`rclcpp` 是 ROS 2 的 C++ 库，对应 Python 的 `rclpy`。

`default.yaml` 里其余内容是相机旋钮：坐标系 `camera_frame`、像素格式 `bgr8`、帧率 `10.0`，以及被 `#` 注释掉的曝光、增益、伽马。注释掉表示先用相机自己的默认值。

## 这一讲要能回答的三件事

1. 话题名字由命名空间、节点名、`image_raw` 拼出来。鱼眼节点默认订的就是这条。
2. `image_callback` 只把图放上传送带，`process_queue` 才调用 `process_fisheye`。
3. `cam2world` 把像素变成单位球上的方向，`define_planes` 造出 6 个平面，`project_patch` 画成小图，再按 2 行 3 列拼起来。
