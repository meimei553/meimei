# 第 4 讲：相机怎么被找到，一帧怎么进内存

第 3 讲停在 `spin()` 调用 `grabImage()`。这一讲往下走两层：节点启动时如何找到相机，以及最里面那次 `grab()` 如何向相机要到像素。

对应文件：

- `pylon_ros2_camera_component/src/pylon_ros2_camera_node.cpp` 的 `init()`、`initAndRegister()`、`startGrabbing()`
- `pylon_ros2_camera_component/src/pylon_ros2_camera.cpp` 的 `create()`
- `include/internal/impl/pylon_ros2_camera_base.hpp` 的 `startGrabbing()`、`grab()`、`grabbingStarting()`

## 启动顺序

节点构造函数里先 `initInterfaces()`，把话题和服务登记好。然后调用 `init()`。`init()` 只有三步，任何一步失败都会 `rclcpp::shutdown()`，整个进程退出：

1. `readFromRosParameterServer`：把 yaml 里的参数读进 `pylon_camera_parameter_set_`。
2. `initAndRegister()`：找到相机、注册软件触发、打开设备、套上这一种接口自己的启动设置。
3. `startGrabbing()`：按参数设定像素格式，开始采集，并试抓一帧确认通信是通的。

成功之后，构造函数才创建第 3 讲那个 10 Hz 的定时器。

## 找到哪一台相机

`PylonROS2Camera::create` 在 `pylon_ros2_camera.cpp`。

`PylonInitialize()` 先启动 Basler 的 pylon 运行库。没有这一句，后面的枚举都不能用。`CTlFactory` 是「传输层工厂」，负责列出网口上的 GigE 相机和 USB 相机。

`EnumerateDevices` 得到一份设备名单。名单是空的就打印 `No available camera device` 并返回空指针。节点那边看到空指针，会每 2 秒再试一次，每 15 秒再报一次「还是没有相机」。它不会立刻放弃。你的 `device_user_id` 是空字符串，所以走「谁先被认出来就用谁」：

- 打印型号和用户起的名字
- `detectPylonCamType` 看设备类别和型号前三个字母
  - 网口 `BaslerGigE` 加型号 `acA`：第一代 ace
  - 网口加 `a2A`：ace 2
  - USB 加 `acA` 或 `a2A`：USB 相机
  - USB 加 `daA`：dart
  - 型号对上 Blaze：类型记成 BLAZE
- `createFromDevice` 按类型造出对应的 C++ 类

这份压缩包把 Blaze 那一支改成了直接 `return nullptr`，注释写着鱼眼相机不需要 Blaze。名单里如果第一台就是 Blaze，后面立刻使用这个空指针，程序会崩。普通 GigE 或 USB 彩色相机不会走到那里。

`device_user_id` 不是空的时候，要在名单里找到名字相符的那一台。比较时还允许「相机全名的末尾等于你给的短名字」。找不到就返回空指针，并说明名字错了或者线还没插上。

## 打开，并改成软件触发

`registerCameraConfiguration()` 向相机注册 `CSoftwareTriggerConfiguration`，模式是 `RegistrationMode_ReplaceAll`。意思是：用 pylon 准备好的一套「软件触发」配置换掉相机上原有的触发配置。软件触发就是程序说一声「拍」，相机才拍。不是快门线，也不是一直自由连拍。

`openCamera()` 就是 `cam_->Open()`。打不开就把 pylon 的英文错误打出来。

`applyCamSpecificStartupSettings` 由具体型号实现。网口相机在 `pylon_ros2_camera_gige.hpp`。启动用户集是 `Default` 时，会先加载相机出厂设置，再把触发源设回软件、触发模式设回打开。因为出厂设置会把刚才注册的软件触发盖掉。你的 launch 文件把 `startup_user_set` 默认设成 `CurrentSetting`，所以走的是「保留相机里现在这套设置」的分支，不会强制重载出厂设置。

同一段还会写网口参数。`GevSCPSPacketSize` 是每个网络包多大，对应 yaml 和 launch 里的 `mtu_size`，默认 1500。`GevSCPD` 是包和包之间的间隔，用来减轻「图像缓冲区没抓全」。单板电脑上网卡常常只能用 1500，所以默认没有开成巨型帧。

## startGrabbing：先选定像素格式，再试抓一帧

底层 `startGrabbing` 在 `pylon_ros2_camera_base.hpp` 第 347 行：

1. 快门模式这个寄存器存在，就按参数设置。滚动快门和全局快门是两种曝光方式。全局快门整张图同时曝光，运动物体不容易拉斜。
2. `detectAvailableImageEncodings` 问相机支持哪些像素格式。
3. `setImageEncoding` 尝试设成 yaml 里的格式。你的是 `bgr8`，三个通道、蓝绿红、各 8 位。设失败就在相机支持的格式里换一个能设上的，并打印 `Falling back to encoding`。一个都设不上就返回失败，节点退出。
4. 第 385 到 386 行把抓图策略写死成 `1`。参数里的 `grab_strategy` 那一行被注释掉了。yaml 里也是 1，所以结果一致，但以后改 yaml 不会生效。
5. `grabbingStarting()` 真正调用 `cam_->StartGrabbing(...)`。
6. 记下图像高、宽，以及一帧的字节数：宽乘高乘每像素字节数。
7. 抓图超时和触发超时来自参数。注释里写抓图超时默认按 500 毫秒理解。
8. 立刻试抓一帧。结果对象有效，才把 `is_ready_` 设为真。这一帧用来确认通信，不会发到话题上。

`grabbingStarting()` 第 3295 行按策略选三种队列：

| 值 | pylon 的名字 | 含义 |
| --- | --- | --- |
| 1 | `GrabStrategy_LatestImageOnly` | 缓冲区里只留最新一帧。计算机来不及处理时，旧帧被丢掉 |
| 2 | `GrabStrategy_LatestImages` | 留最新的若干帧 |
| 其他 | `GrabStrategy_OneByOne` | 按到来顺序一帧不丢地排队，处理慢就会积压 |

现在写死的是 1。这和 Python 节点那个只能放 1 张图的队列是同一个想法：算不过来就丢旧图，不要越积越慢。

`grabbingStopping()` 是 `cam_->StopGrabbing()`。改像素格式这类必须停采集才能改的寄存器，会先停、改完、再调用 `grabbingStarting()`。

## 最里面的 grab：软件触发，然后取回一帧

第 3 讲的 `grab(向量, 时间戳)` 自己不跟相机说话。它调用第 555 行这个最里面的 `grab(grab_result)`。

1. `cam_->IsGrabbing()` 为假就直接失败。采集没开始，没有帧可取。
2. 触发模式是开的时候，先等相机准备好接受下一次触发。`WaitForFrameTriggerReady` 成功，就 `ExecuteSoftwareTrigger()`，程序发出「拍」这一声。
3. 相机不支持「等待就绪」时，不等，直接触发，并打一条警告。
4. 等待超时：打警告，把触发源再写成软件、触发模式再写成开，然后仍然触发一次。这里不返回失败，继续往下取结果。所以偶发的等待超时会被再试一次。
5. `RetrieveResult(grab_timeout_, ...)` 在超时时间内把这一帧的结果对象拿回来。超时、掉线、异常都进 `catch`，返回 `false`。掉线时的英文是 `Lost connection to the camera`。如果触发源不是软件、又开着触发，它会打印正在等外部触发信号。那表示快门线或别的设备还没给信号。
6. `GrabSucceeded()` 为假，打印错误码和英文描述，返回 `false`。成功才返回 `true`。

回到外面那层 `grab(向量, 时间戳)`：

- 从结果里拿出像素首地址。
- 12 位特殊格式先把每个像素左移 4 位，变成 ROS 能用的 16 位。`bgr8` 不走这里，直接 `assign` 复制整帧字节。
- chunk 时间戳的处理已经在第 3 讲讲过。没开 chunk，时间戳保持调用前的 `now()`。

节点的 `startGrabbing()` 在底层成功之后，还做这些和「消息长什么样」有关的事：

- 按相机实际输出引脚的数量，动态创建 `~/set_user_output_0` 这类服务，以及自动闪光服务。
- 把 `img_raw_msg_` 的坐标系、编码、高、宽、`step` 写好。
- 相机用户名如果含有字母、数字、下划线以外的字符，`camera_info_manager` 会拒绝这个名字。
- `camera_info_url` 为空时警告：只会提供带畸变的 `image_raw`。你的 yaml 就是空的。
- 曝光、增益、伽马、亮度、binning 这些参数，只有 yaml 里真的写了并且没有被 `#` 注释掉，才会在这里下发。你的文件里它们是注释，所以用相机当前值。
- 期望帧率高于相机最大帧率时，把参数降到最大帧率。`frame_rate` 为 -1 时，直接用最大帧率。你写的是 10。

第 996 到 1036 行整段被注释掉。它曾经想把采集区域设成 2448×2048 并居中。你的 yaml 末尾另有 `image_width: 2448` 和 `image_height: 2048`，但这段 C++ 没有读它们。实际宽高以相机当前寄存器为准。

另外，第 174 到 241 行的 `saveImageToDisk` 也整段注释掉了。它曾经把每张图存到 `/home/unitree/saved_images/`。现在运行时不会存盘。离线把一叠 tiff 做成视频的是 `fisheye_tool` 里的 `shipin.py`，第 6 讲再说。

## 这一讲要能回答的三件事

1. 空的 `device_user_id` 表示使用第一台认得出型号的相机。找不到就每 2 秒再试。
2. 默认是软件触发：程序叫一次 `ExecuteSoftwareTrigger`，相机才曝光一帧。
3. 抓图策略被写死成「只留最新一帧」。计算机慢的时候，旧帧在相机驱动里就被丢掉。
