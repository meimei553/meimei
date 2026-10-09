# 第 3 讲：相机节点怎么采一张图，再决定发不发

这一讲读 `pylon_ros2_camera_node.cpp` 里真正出图的循环。主函数是 `spin()`，从第 1040 行到第 1260 行。它每次被定时器叫起来，做三件事：相机还在不在、有没有人看图、看的话就抓一张并发出去。

抓图的具体动作在第 1262 行的 `grabImage()`。时间戳会在抓图时写上一次，在发布前被改掉。这一讲把这两次都讲清楚。

你的相机是普通彩色相机，走 `isBlaze()` 为假的那一支。Blaze 是 Basler 的 3D 深度相机，代码里有另一支，这一讲只说明它存在，不逐行展开。

## 谁来叫 spin

构造函数末尾，大约第 108 到 110 行：

```cpp
timer_ = this->create_wall_timer(
    std::chrono::duration<double>(1. / this->frameRate()),
    std::bind(&PylonROS2CameraNode::spin, this));
```

`frameRate()` 来自 `default.yaml` 的 `frame_rate: 10.0`。`1 / 10 = 0.1`，所以大约每 0.1 秒叫一次 `spin`。`create_wall_timer` 用的是墙上的真实时间。`std::bind(..., this)` 表示到点就调用这个对象自己的 `spin`。

相机节点的 `main` 用的是单线程执行器。上一次 `spin` 还没返回时，下一次不会插进来并行跑。鱼眼计算如果超过 0.1 秒，实际出图就会慢于设定的 10 Hz。

话题名在 `initPublishers()` 第 264 到 265 行：

```cpp
msg_name = "~/image_raw";
this->img_raw_pub_ = image_transport::create_camera_publisher(this, msg_name);
```

`~` 会展开成「命名空间 + 节点名」。启动文件里命名空间是 `my_camera`，节点名是 `pylon_ros2_camera_node`，所以完整话题是 `/my_camera/pylon_ros2_camera_node/image_raw`。这就是 Python 鱼眼节点默认订阅的那一条。`create_camera_publisher` 一次登记两个发布：图像，以及配套的 `camera_info`。

图像消息的宽高在初始化时写好，大约第 807 到 815 行。`frame_id` 用参数 `camera_frame`，你的 yaml 里是 `pylon_camera`。`encoding` 用相机当前的像素格式，yaml 里设的是 `bgr8`。`height`、`width` 来自相机。`step` 是一行占多少字节，等于宽度乘每个像素的字节数。这些字段抓图时不再重算，只有像素数据 `data` 和时间戳 `header.stamp` 每张图都会变。

## 第 1040 到 1050 行：校准只提醒一次

```cpp
void PylonROS2CameraNode::spin()
{
  if (this->camera_info_manager_->isCalibrated())
    RCLCPP_INFO_ONCE(LOGGER, "Camera is calibrated");
  else
    RCLCPP_INFO_ONCE(LOGGER, "Camera not calibrated");
```

`spin` 会被调用几千次。`RCLCPP_INFO_ONCE` 保证这句话只打印一次，避免刷屏。

`isCalibrated()` 问的是：有没有一份普通针孔相机的内参。那是另一套标定，用来把图像「拉直」，和鱼眼用的 `ocam.yaml` 不是同一个文件。你的 `default.yaml` 里 `camera_info_url` 是空的。初始化大约第 836 到 845 行发现这个地址无效，会警告：只能提供变形的 `/image_raw`。所以这里多半会打印 `Camera not calibrated`。鱼眼展开不依赖这句。

## 第 1052 到 1078 行：相机掉线就重来

```cpp
if (this->pylon_camera_->isCamRemoved())
{
  RCLCPP_ERROR(... "trying to reset");
  this->cm_status_.status_id = ...ERROR;
  if (enable_status_publisher_)
    this->component_status_pub_->publish(this->cm_status_);
  if (this->pylon_camera_ != nullptr)
    this->pylon_camera_.reset();
  this->set_user_output_srvs_.clear();
  rclcpp::Rate r(0.5);
  r.sleep();
  this->init();
  return;
}
```

`isCamRemoved()` 为真，表示 USB 线或网线意义上的相机已经不在了。

- 打一条错误日志。
- 把组件状态改成 ERROR。`enable_status_publisher_` 为真才把这条状态发出去。你的 yaml 里这个开关是 `true`。
- `reset()` 丢掉旧的相机对象。
- `set_user_output_srvs_.clear()` 清掉「设置相机输出引脚」的服务。注释说明：ROS 1 里可以关掉服务，ROS 2 里不能单独关掉，所以这里只是把 C++ 里的名单清空。
- `rclcpp::Rate r(0.5)` 再 `sleep()`，停大约 2 秒。频率 0.5 Hz 就是每秒半次，周期是 2 秒。给人重新插上相机留时间。
- `init()` 再找一次相机、再打开采集。
- `return` 结束这一轮 `spin`。这一轮不再抓图。下一轮定时器还会再进来。

## 第 1081 到 1114 行：有人看，才抓图

```cpp
if (!this->pylon_camera_->isBlaze())
{
  const bool any_subscriber =
      (this->img_raw_pub_.getNumSubscribers() != 0
       || this->getNumSubscribersRectImagePub() != 0);
  if (!this->isSleeping() && any_subscriber)
  {
    if (any_subscriber)
    {
      rclcpp::Time t_before_grab = this->now();
      if (!this->grabImage())
        return;
      ...
    }
```

`isBlaze()` 对这台普通相机是假，所以进入这一大支。

`getNumSubscribers()` 问现在有几个程序在听这个话题。没有人听，就不要抓图。抓一张图要占相机、网线和 CPU，没人看就是浪费。这是机器人程序里很常见的习惯。

`any_subscriber` 在两个数里有一个不是 0 就为真：

- 听 `image_raw` 的人数
- 听校正图的人数。`getNumSubscribersRectImagePub()` 在第 2412 行：相机还没做针孔标定就直接返回 0；标定过了才返回校正图发布者的订阅人数

`isSleeping()` 只是返回成员 `is_sleeping_`。为真表示节点被要求暂停，这一轮不抓。

外层已经要求 `any_subscriber` 为真，里面第 1087 行又判断了一次。两次结果一样，里面这次是重复的。

`this->now()` 是节点自己的时钟，记下「准备去相机拿图」的时刻。`grabImage()` 返回 `false` 就 `return`。注意这个 `return` 退出的是整个 `spin`，不是只跳过发布。这一轮末尾的状态发布、参数发布也不会执行。

第 1098 到 1113 行在抓图成功后算两个时间差，变量名是拼音：

- `diaoyong_qianhou`：从调用 `grabImage` 之前，到抓图返回。这是抓一张图花了多久。
- `publish_capture`：从消息里的采集时间戳，到抓图返回。

两句 `RCLCPP_INFO` 都被 `//` 注释掉了。数算了，终端上看不到。

文件里这几行的缩进是乱的。读的时候跟花括号走，不要跟空格对齐走。

## 第 1262 到 1304 行：grabImage 把像素和时间戳放进消息

`spin` 在这里调用它，所以插到这里讲。

```cpp
bool PylonROS2CameraNode::grabImage()
{
  std::lock_guard<std::recursive_mutex> lock(this->grab_mutex_);
  if (!this->pylon_camera_->isBlaze())
  {
    auto stamp = rclcpp::Node::now();
    if (!this->pylon_camera_->grab(this->img_raw_msg_.data, stamp))
      return false;
    this->img_raw_msg_.header.stamp = stamp;
  }
  ...
  return true;
}
```

`lock_guard` 一构造就锁上 `grab_mutex_`，函数结束自动解锁。同一时刻只有一处能跟相机要图。别的函数如果正在改曝光，会等这把锁。`recursive_mutex` 允许同一条线程重复加锁，避免自己把自己卡死。

普通相机这条支路：

1. 先记下当前时间，放进 `stamp`。注释说：在图像传上来之前记时间，估计的抓图时刻更接近真实曝光。
2. `grab` 的第二个参数是引用 `rclcpp::Time &stamp`。函数里面可以改掉调用者的 `stamp`。
3. 失败返回 `false`。成功就把 `stamp` 写进 `img_raw_msg_.header.stamp`。

底层 `grab` 在 `pylon_ros2_camera_base.hpp` 大约第 422 行。它向相机要一帧，把像素复制进 `image` 这个向量，也就是 `img_raw_msg_.data`。12 位的特殊格式会先把每个像素左移 4 位，凑成 ROS 常用的 16 位。你的 yaml 是 `bgr8`，走的是普通复制那一支：`image.assign(...)`。

同一函数后半段处理相机自带的 chunk 时间戳。相机如果打开了 chunk 模式，并且时间戳那一项可读，就把 `stamp` 改成：

```cpp
stamp = rclcpp::Time(static_cast<uint64_t>(chunk_raw));
```

`rclcpp::Time` 的这个构造把整数当成「从 1970 年起的纳秒」。Basler 的 chunk 时间常常是相机自己的计数器，不一定是 Unix 时间。所以一旦走到这里，`stamp` 会变成一个看起来很奇怪的秒数，并且会打一条 `ChunkTimestamp raw = ...` 的日志。chunk 没开，`stamp` 就保持抓图前那次 `now()`。

再往下最底层的 `grab`，大约第 555 行：相机如果处于触发模式，就等触发就绪，再发一次软件触发，然后 `RetrieveResult` 把这一帧拿回来。超时或掉线会抓异常并返回 `false`。这就是上一层 `grabImage()` 失败的原因。

Blaze 那一支把点云、强度图、深度图、彩色深度图、置信度图的时间戳都设成同一次 `now()`。你的鱼眼相机不走这里。

## 第 1116 到 1170 行：改掉时间戳，再发布

抓图成功之后，只有 `image_raw` 的订阅人数大于 0，才进入发布。只订阅校正图、没人订阅原图时，图已经抓了，但不会从这条发出去。

```cpp
rclcpp::Time capture_stamp(this->img_raw_msg_.header.stamp);
rclcpp::Time t_pub = this->now();
this->img_raw_msg_.header.stamp = t_pub;
```

先把抓图时写下的时间存进局部变量 `capture_stamp`，再把消息里的时间改成「现在」。从这一行起，消息头上不再是曝光时刻，也不再是 chunk 时间。后面那个时间差 `pub_capture` 同样算了但没有打印。

然后取一份 `CameraInfo`。注释说每帧都重新取，因为别的程序可能刚调用 `set_camera_info` 改过内参。原来有一行把 `cam_info` 的时间和图像时间对齐，被注释掉了。现在写的是又一次 `this->now()`。图像时间和相机信息时间因此是两个非常接近、但不是同一个时刻。

鱼眼开关开着时，后面和第 2 讲一样：用消息里的像素内存包一张 `cv::Mat`，调用 `fisheye_proc_.process`。成功就造一条新消息。这里又把时间改一次：

```cpp
rclcpp::Time t_pub_fisheye = this->now();
this->img_raw_msg_.header.stamp = t_pub_fisheye;
out_msg.header = this->img_raw_msg_.header;
```

所以发出去的大图，时间戳是鱼眼算完的时刻。`cam_info` 的时间还停在算鱼眼之前的那次 `now()`。两条消息的时间对不齐曝光，彼此也差了整段鱼眼计算。

新消息的其余字段：

- `height`、`width` 改成大图的行数和列数。512 的小图、2 行 3 列时，是 1024 乘 1536。
- `encoding` 固定写成 `bgr8`。
- `is_bigendian = false` 表示多字节数字按这台电脑常见的小端存放。8 位像素一个字节，这项几乎没影响。
- `step` 等于大图宽度乘 `elemSize()`。`CV_8UC3` 每个像素 3 字节，所以一行的字节数是宽度乘 3。
- `data.assign(datastart, dataend)` 才把大图像素复制进新消息。

`publish(out_msg, cam_info)` 把图像和相机信息一起发出去。话题名仍然是 `image_raw`。

`process` 失败时，警告一句，把 `img_raw_msg_` 原样发出去。此时它的时间戳已经是进入鱼眼之前的 `t_pub`，像素仍是相机原图。开关关着时同样发这张原图。

## 第 1172 到 1204 行：校正图要超过 10 个订阅者

```cpp
if (this->getNumSubscribersRectImagePub() > 10)
```

校正图是用针孔模型把镜头畸变拉直，话题一般叫 `image_rect`。条件有两层：

1. `getNumSubscribersRectImagePub()` 在没做针孔标定时直接是 0。
2. 就算标定了，订阅人数必须大于 10。

原图用的是大于 0：有 1 个人看就发。校正图写成大于 10：至少 11 个人同时订阅才发。平时你只用一个窗口看图，这条进不去。再叠加你的 `camera_info_url` 是空的，初始化时也没有建立校正。这条在当前配置下不会出图。

如果将来人数真的超过 10，它做的是：

- 把校正消息的时间设成 `img_raw_msg_` 此刻的时间。鱼眼已经成功的话，这个时间是鱼眼结束的时刻。
- `assert(pinhole_model_->initialized())` 要求针孔模型已经准备好，否则程序直接中止。
- 像素如果是 8 位 Bayer（相机原始的马赛克格式），先当成 `bgr8`；16 位 Bayer 当成 `bgr16`。
- `cv_bridge::toCvCopy` 把 `img_raw_msg_` 复制成 OpenCV 图。这里用的是相机原图像素，不是刚拼好的那张大图。大图在另一条消息 `out_msg` 里，已经发出去了。
- `rectifyImage` 拉直，再发布。

复制失败就打错误日志，这一帧的校正图不发。

## 第 1207 到 1259 行：3D 相机，以及每轮结尾

`else` 是 Blaze。只有没在睡眠，并且点云、强度、深度、彩色深度、置信度里至少有一个话题有订阅者，才抓取。抓到之后给每条消息写上同一个坐标系名字，再全部发布。鱼眼彩色相机不进这个 `else`。

两条支路汇合后，还有三件每次 `spin` 都会做的事。前面如果 `grabImage()` 失败已经 `return`，这三件就跳过了。

1. 第 1244 行：参数里的像素格式和相机实际格式不一样，就把参数改成实际格式，并停止再重新开始采集。注释说这是为了让 ROS 图像消息的类型和相机一致。
2. 第 1251 行：状态发布开关开着，就发一次组件状态。
3. 第 1256 行：当前参数发布开关开着，就发一次曝光、增益那些当前值。你的 yaml 里这两个开关都是 `true`，所以每个成功的周期都会发。

## 一张图实际走过的时间

把普通相机、有人订阅 `image_raw`、鱼眼开关打开、处理成功，连成一条：

1. 定时器进入 `spin`。
2. 相机还在，有订阅者，没在睡眠。
3. `grabImage` 把像素放进 `img_raw_msg_.data`，时间戳先写成抓图前的 `now()`。chunk 时间戳开着的话，会被改成相机计数器。
4. 发布前，这个时间戳被改成 `t_pub`。
5. `camera_info` 的时间再用另一次 `now()` 写上。
6. 鱼眼算完，图像时间戳再改成 `t_pub_fisheye`，大图发出去。
7. 校正图因为订阅人数不到 11，不发。
8. 状态和当前参数发出去。

下游如果想用时间戳把这张图和激光、关节对齐，对上的是「鱼眼算完的时刻」，不是快门时刻。抓图阶段就算拿到了 chunk 时间，发布前也被盖掉了。

## 这一讲要能回答的三件事

1. `spin` 大约每 `1 / frame_rate` 秒跑一次。没人订阅 `image_raw`，也没人订阅校正图，就不要图。
2. 抓图时写过一次时间戳。发出去之前会被改成鱼眼结束的时刻。`camera_info` 的时间还停在鱼眼开始之前。
3. 校正图的条件是订阅人数大于 10，而且先要有针孔标定。当前这份 yaml 两个条件都不满足，实际发出来的是名叫 `image_raw` 的鱼眼大图。
