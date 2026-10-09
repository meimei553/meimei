# 第 6 讲：剩下的文件，以及这两份代码到哪里为止

前五讲已经把「相机出图，再变成 6 张平面图」这条路走完。这一讲把其余文件归位。它们都在压缩包里，但不是一条新的感知算法。

## 服务：别人用名字来拧旋钮

`initServices()` 从第 282 行起，用同一个写法登记了几十个服务。每一行都是：

```text
名字 = "~/某个旋钮"
create_service(名字, 回调函数)
```

`~` 仍然展开成 `/my_camera/pylon_ros2_camera_node/`。别的程序用 `ros2 service call` 调用这些名字，就等于远程拧第 5 讲那些旋钮。回调函数几乎都是：取出请求里的数字，调用相机对象的同名函数，把成功与否和一句英文放进响应。

按作用分组，名字是这些。

统计和缓冲，用来查丢帧：

- `get_max_num_buffer`、`set_max_num_buffer`、`set_output_queue_size`
- `get_statistic_total_buffer_count`、`get_statistic_failed_buffer_count`
- `get_statistic_buffer_underrun_count`、`get_statistic_failed_packet_count`
- `get_statistic_resend_request_count`、`get_statistic_missed_frame_count`
- `get_statistic_resynchronization_count`

chunk 是相机塞进图像旁边的附加数据。第 3 讲的时间戳就来自这里：

- `get_chunk_mode_active`、`get_chunk_selector`、`set_chunk_selector`、`get_chunk_enable`
- `get_chunk_timestamp`、`get_chunk_exposure_time`、`set_chunk_exposure_time`
- `get_chunk_line_status_all`、`get_chunk_frame_counter`、`get_chunk_counter_value`

画面本身：

- `set_exposure`、`set_gain`、`set_gamma`、`set_gamma_selector`
- `set_brightness`、`set_binning`、`set_roi`
- `set_offset_x`、`set_offset_y`、`set_black_level`
- `set_white_balance`、`set_white_balance_auto`、`set_light_source_preset`
- `set_demosaicing_mode`、`set_noise_reduction`、`set_sharpness_enhancement`

触发和引脚。软件触发不够用、要接外部快门线时才动这些：

- `set_trigger_selector`、`set_trigger_source`、`set_trigger_activation`
- `set_trigger_delay`、`set_trigger_timeout`、`set_acquisition_frame_count`
- `set_line_selector`、`set_line_mode`、`set_line_source`、`set_line_debouncer_time`
- `set_user_output_0` 这类名字在 `startGrabbing` 里按引脚数量现造
- `activate_autoflash_output_0` 这一类负责闪光灯同步

网口和采集节奏：

- `set_device_link_throughput_limit`、`set_max_transfer_size`
- `set_grab_timeout`、`set_grabbing_strategy`
- `set_user_set_selector`、`set_user_set_default_selector`

PTP 是网口上多台相机对时的协议。名字都以 `set_ptp_` 或 `set_sync_free_run_` 开头。一台相机做鱼眼时用不到。多台相机要让快门发生在同一微秒时才用。

`set_sleeping` 把第 3 讲那个 `is_sleeping_` 设为真或假。为真时 `spin` 不再抓图，话题服务还在。

下面这些是 Blaze 深度相机的旋钮。这份代码的工厂已经不创建 Blaze 对象，所以正常鱼眼相机不会用到它们：

- `set_depth_min`、`set_depth_max`
- `set_temporal_filter_strength`、`set_outlier_removal_threshold`、`set_outlier_removal_tolerance`
- `set_ambiguity_filter_threshold`、`set_confidence_threshold`
- `set_intensity_calculation`、`set_exposure_time_selector`
- `set_operating_mode`、`set_multi_camera_channel`

每个 `.srv` 文件只是在声明请求和响应有哪些字段。`---` 上面是请求，下面是响应。例如设置曝光：请求里是目标曝光，响应里是是否成功、真正达到的曝光、一句说明。

## 动作：一次要回好多张图

服务是一问一答。动作适合「要做一会儿，并且中间想知道进度」。

`initActions()` 登记 `~/grab_images_raw`。有人发来目标就 `ACCEPT_AND_EXECUTE`。取消请求也接受。真正干活放到一条新线程，避免堵住 10 Hz 的 `spin`。`GrabImages.action` 允许一次给出一组曝光、一组增益，驱动按这组设置连拍若干张，再一起返回。

校正版动作要先通过针孔标定。没标定就返回失败。它内部还是先抓原图，再逐张做 `rectifyImage`。

`grab_blaze_data` 只在 `isBlaze()` 为真时登记。当前工厂不创建 Blaze，所以这条动作服务器不会出现。

`wrapper/test/` 里的三个 C++ 文件是这些动作的示例客户端：发一次目标，把返回的图用 OpenCV 弹窗显示。它们不是相机驱动本身。

## 诊断

`initDiagnostics()` 每 2 秒跑一次。它向 ROS 的诊断话题报告两件事：相机还在不在，针孔内参加载了没有。这是给操作人员看的健康状态，不参与鱼眼计算。

## 五种相机类，差别在接口，不在鱼眼

| 文件 | 什么时候用 |
| --- | --- |
| `pylon_ros2_camera_base.hpp` | 所有型号共用的寄存器读写，文件最长 |
| `pylon_ros2_camera_gige.hpp` | 网口 ace。启动时设置 MTU 和包间隔 |
| `pylon_ros2_camera_gige_ace2.hpp` | 网口 ace 2，启动设置同类，寄存器名字有差别 |
| `pylon_ros2_camera_usb.hpp` | USB 相机自己的启动设置 |
| `pylon_ros2_camera_dart.hpp` | dart。先调用 USB 的启动函数，再加自己的部分 |
| `pylon_ros2_camera_blaze.hpp` | 深度图、点云、置信度。工厂里被关掉了 |

`pylon_ros2_camera.hpp` 是纯虚基类，只列出「每种相机都必须会的函数」，函数体在上面这些文件里。`pylon_ros2_camera_parameter.hpp` 和 `.cpp` 负责把 yaml 的键读进 C++ 成员，并记住「这个键用户有没有写」。没写的键不会在启动时覆盖相机。

`visibility_control.hpp` 是 Windows 和 Linux 导出动态库符号用的宏。阅读算法时可以跳过。

`src/tools/set_device_user_id.cpp` 是一个单独的小程序，给相机起那个 `device_user_id`。USB 相机改完名字要重新插拔。`ip_auto_config.cpp` 能自动改网口相机的 IP，但 `CMakeLists.txt` 里编译它的几行被注释掉了，当前不会生成这个可执行文件。

`ip_configuration.launch.py` 和 `my_blaze.launch.py` 是另外两个启动文件。日常鱼眼用的是 `pylon_ros2_camera.launch.py`。

## fisheye_tool 里没有被启动的文件

`setup.py` 只登记了 `fisheye_stitching_node`。下面这些不在那条命令上。

| 文件 | 它是什么 |
| --- | --- |
| `fisheye_tools.py` | 最早的一版，从图片文件读入，函数名是 `process_fisheye_from_files` |
| `fisheye_tools_2.py` | 加上了 `rescale`，仍然从文件读 |
| `fisheye_tools_numba.py` | 把缩放函数交给 numba 加速，并保留从文件读的入口 |
| `fisheye_tool_3.py` | 当前被节点 import 的版本。输入改成内存里的一张图 |
| `fisheye_tool_3 copy.py` | `fisheye_tool_3.py` 的一份拷贝 |
| `fisheye_stitching_node_bk.py`、`fisheye_stitching_node20251204.py` | 节点的旧备份 |
| `test_fisheye.py` | 本地试算用的小脚本 |
| `test/test_flake8.py`、`test_pep257.py`、`test_copyright.py` | ROS 包生成时带的代码风格测试，不处理图像 |
| `ocam.mat`、`valid_range_list.mat` | 标定和有效区域。Python 读这两个 |
| `shipin.py` | 不连接 ROS。它从 `/home/unitree/fishimages` 按顺序读 tiff，16 位图先除以 256 变成 8 位，灰度图补成 3 通道，同样 `flip(-1)`，调用 `process_fisheye`，再写成 mp4 |

`shipin.py` 顶部还导入了 `natsort`。`package.xml` 没有列出这个库。只在那台已经装过它的机器人电脑上，这个脚本才能直接跑。

C++ 侧对应的标定是 `pylon_ros2_camera_wrapper/ocam.yaml` 和 `valid_mask.png`。两套数字应当来自同一次标定。一个改了，另一个没改，Python 节点和相机节点会给出不同的平面图。

## 这两份代码没有做的事

到这里，压缩包里的路径就齐了：

```text
找相机 → 软件触发 → 复制一帧 bgr8
    → 有人订阅才进入 spin
    → 鱼眼：像素变单位射线 → 6 个平面 → 2 行 3 列
    → 仍以 image_raw 的名字发出去
```

图里还没有「这是地面、这是人、这是障碍」这样的名字。那一步叫语义。语义构建通常接在这种几何图之后：拿这 6 张比较平整的图，或拿原始鱼眼图，送给一个分类或分割模型，再把类别写回机器人用地图。这两份 zip 的最后一帧停在几何图。

若只保留一条运行路径，相机进程里的 `enable_fisheye_stitch` 和单独的 Python 节点应只开一个。两个同时开，Python 会把已经拼好的大图再当成鱼眼原图处理一次。

## 六讲对照

| 讲 | 回答的问题 |
| --- | --- |
| 1 | Python 节点如何收图，`cam2world` 如何把像素变成射线 |
| 2 | 同一套几何的 C++ 版，以及它如何改写 `image_raw` |
| 3 | `spin` 何时抓图，时间戳在发布前如何被改掉 |
| 4 | 相机如何被找到，软件触发如何把一帧放进内存 |
| 5 | 曝光、增益、裁剪、编码如何改变像素，为什么会破坏旧标定 |
| 6 | 其余服务、动作、型号文件和草稿各自是什么；语义不在这里 |
