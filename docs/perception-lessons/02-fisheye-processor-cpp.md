# 第 2 讲：同一套鱼眼算法的 C++ 版

这一讲逐段读 `pylon_ros2_camera_component/src/fisheye_processor.cpp`，一共 502 行。头文件 `include/fisheye_processor.hpp` 是它的目录。相机节点在 `pylon_ros2_camera_node.cpp` 里创建它、调用它。

先把第 1 讲的画面留着：像素变成单位球上的箭头，6 个平面各画一张 512×512，再拼成上面 3 张、下面 3 张。C++ 做的是同一件事，写在相机进程里面。开关是 `default.yaml` 里的 `enable_fisheye_stitch: true`。

## 这一讲要新学的 C++ 写法

只记这份文件里出现的。

| 写法 | 含义 |
| --- | --- |
| `#include "..."` | 把另一个文件的声明拿进来。引号表示先在自己的目录里找 |
| `//` 和 `/* */` | 注释。编译器当它们不存在。人要读，因为这里留着旧写法 |
| `namespace { ... }` | 匿名名字空间。里面的函数只在这个 `.cpp` 文件里看得见 |
| `inline` | 建议编译器把这个小函数直接嵌进去 |
| `类名::函数名` | 这个函数属于哪个类。对应 Python 里写在 `class` 里面的 `def` |
| 参数末尾的 `const` | 这个函数只读对象，不改标定和缓存 |
| `类型& 名字` | 引用。函数里改它，外面的那个变量也跟着变。用来交出结果 |
| `std::vector<T>` | 可变长度数组，对应 Python 的列表 |
| `cv::Mat` | OpenCV 的一张图 |
| `cv::Vec3f` | 3 个小数，这里用来装 x、y、z 或红、绿、蓝 |
| `cv::Vec3b` | 3 个 0 到 255 的字节，一个像素 |
| `static_cast<int>(x)` | 明确地把 x 变成 int |
| `auto` | 让编译器推断类型 |
| `for (const auto& p : coords)` | 把 coords 里的元素一个一个拿出来 |
| `return true / false` | C++ 里常用这个表示成功或失败，对应 Python 里有时返回 `None`、有时抛异常 |

`std::cerr` 是错误输出，会立刻出现在终端。ROS 自己的打印是 `RCLCPP_...`，这份算法文件里主要用 `std::cerr`。

## 头文件在说什么

`fisheye_processor.hpp` 是目录，`.cpp` 是正文。目录里先放一个结构体 `OcamModel`：多项式 `pol`、`invpol`、`ss`，中心 `xc`、`yc`，仿射系数 `c`、`d`、`e`，还有宽高。`{0}` 表示默认是 0。

类 `FisheyeProcessor` 公开三样东西：

- `loadCalibration`：读 `ocam.yaml` 和掩码图
- `process`：输入一张 BGR 鱼眼图，输出拼好的 BGR 大图。默认小图 512，平面窗口 1.5
- 头文件第 16 行写「3x2」。正文的实现是高 2 块、宽 3 块，也就是 2 行 3 列

私有部分外面不能直接碰：

- `points3d_` 存单位方向，z 已经取过相反数
- `colors_` 存对应颜色
- `cam2world` 把一个像素变成单位方向
- `definePlanes` 填 6 个平面
- `projectPatch` 画一张小图

成员名末尾的下划线是这个项目的习惯，表示「属于对象自己」，对应 Python 的 `self.xxx`。

## 第 1 到 26 行：两个小工具

```cpp
#include "fisheye_processor.hpp"
#include <opencv2/opencv.hpp>
#include <yaml-cpp/yaml.h>
```

第 1 行把自己的目录包括进来。第 2 行是 OpenCV。第 3 行是 yaml-cpp，用来读标定 yaml。后面的 `<cmath>`、`<random>`、`<algorithm>`、`<chrono>` 分别是数学、随机数、洗牌、秒表。`<rclcpp/rclcpp.hpp>` 被包含了，正文里真正的 ROS 打印是注释掉的。

第 9 到 26 行包在匿名名字空间里，所以 `normalizeVec3` 和 `clampf` 不会污染别的文件。

`normalizeVec3`：算长度 `sqrt(x^2+y^2+z^2)`。长度几乎是 0 时不能除，返回 `(0,0,0)`。否则每个分量除以长度。`1e-12f` 里的 `f` 表示这是单精度小数。

`clampf`：把一个数夹在 `lo` 和 `hi` 之间。小于下界就用下界，大于上界就用上界。注释写明是为了不依赖较新的 C++17 标准库。

## 第 28 到 45 行：被弃用的旧读法

整段都在 `//` 后面。编译器不理它。它曾经是短版本：直接 `y["pol"].as<vector>()`，文件打不开或字段类型不对就会抛出去。现在的正文把每种失败分开打印。读的时候知道「上面是旧的，下面才生效」即可。

## 第 47 到 163 行：读标定

函数签名：

```cpp
bool FisheyeProcessor::loadCalibration(const std::string& ocam_yaml,
                                       const std::string& mask_png)
```

两个参数是文件路径，用引用传入，避免复制整段字符串。`const` 表示函数里不会改这两段路径。返回 `bool`：成功是 `true`。

第 51 到 62 行先 `YAML::LoadFile`。文件不存在走 `YAML::BadFile`，其他错误走 `std::exception`。两种都打印路径或原因，然后 `return false`。`e.what()` 是错误自带的那句说明。

第 66 到 121 行把 `pol`、`invpol`、`ss` 各读一遍，结构完全一样：

1. `clear()` 先把向量清空
2. yaml 里没有这个键，就跳过
3. 有这个键但不是列表，打印一句然后忽略
4. 是列表，就逐个 `as<double>()` 放进向量
5. 中途某个元素不是数字，清空这一组并打印

`ss` 多一层：键不存在时额外警告。后面的 `cam2world` 优先用 `ss`，没有它才退回 `pol`。

你这份 `ocam.yaml` 的具体数字是：

- 图像 `width: 2448`，`height: 2048`
- 圆心大约在 `(1223.95, 1023.98)`，很接近画面中心
- `c` 接近 1，`d` 和 `e` 接近 0，说明像素几乎是正方形
- `ss` 有 5 个数，这是 `cam2world` 真正使用的多项式
- `pol` 有一长串，只在 `ss` 缺失时才用

第 123 到 138 行读标量。`xc` 到 `e` 用 `as<double>()`。宽高在 yaml 里写成 `2448.0` 这种小数，所以先按 `double` 读，再用 `static_cast<int>` 变成整数。任何一个字段缺失或类型不对，整段标定失败，返回 `false`。

第 140 到 146 行用 `cv::imread(mask_png, cv::IMREAD_GRAYSCALE)` 读掩码。灰度图每个像素一个字节。读出来是空的就失败返回。

第 148 到 153 行比较掩码宽高和标定宽高。对不上只打印，仍然继续。注释写了「可以 return false，这里先不强制」。所以掩码尺寸错了，函数依然返回成功，后面会按这张对不上的掩码去挑像素。

第 155 到 162 行打印各组系数有几个、图像有多大，然后 `return true`。

## 第 165 到 205 行：一个像素变成一根箭头

```cpp
cv::Vec3f FisheyeProcessor::cam2world(float u, float v) const
```

`u` 是列，`v` 是行，和 Python 里 `m` 的两行一致。末尾 `const` 表示不修改对象里的标定。

第 171 到 173 行手写了矩阵 `A = [[c, d], [e, 1]]` 的逆，不再调用一个「求逆」函数。行列式是 `c - d*e`。

```text
xp = ((u - xc) - d * (v - yc)) / (c - d*e)
yp = (-e * (u - xc) + c * (v - yc)) / (c - d*e)
```

这和 Python 里 `inv(A) @ (像素 - 中心)` 是同一套式子。

第 175 行：`r` 是离模型中心的距离。

第 178 到 184 行，`ss` 不为空时走和 Python 相同的多项式。Python 写的是 `np.polyval(ss[::-1], r)`，也就是把系数倒过来，高次项在前。C++ 用两行做同一件事：

```cpp
std::vector<double> coeff_desc(ocam_.ss.rbegin(), ocam_.ss.rend());
for (double c : coeff_desc) {
    z = z * r + c;
}
```

`rbegin()` 到 `rend()` 就是倒着复制。循环 `z = z * r + c` 叫霍纳算法，展开后就是高次在前的多项式。

第 185 到 193 行是退路：没有 `ss` 但有 `pol` 时，按低次在前累加，`pol[0] + pol[1]*r + pol[2]*r^2 ...`。这和 `ss` 的方向约定不一样，所以只是兼容旧文件。

第 194 到 197 行：两种多项式都没有，直接返回 `(0, 0, 1)`，也就是指向 z 轴的单位箭头。

第 199 到 204 行把 `xp, yp, z` 收成 `Vec3f`，再调用前面的 `normalizeVec3`，得到长度为 1 的方向。

## 第 207 到 228 行：反方向的函数，整段关闭

`world2cam` 是反过来的：给一根空间箭头，算它落在哪个像素。鱼眼展开用不到它，所以整段注释掉了。头文件里对应的声明也注释掉了。留下是为了对照 OCamCalib 的 `world2cam.m`。现在不要跟着这段写代码。

## 第 230 到 257 行：6 个平面

`definePlanes` 把结果写进调用者传来的 `planes`。开头 `clear()`，避免重复调用时越积越多。

每个平面是 `cv::Vec4f`，四个数。前三个是法线，第四个本来可以表示平面离原点的距离，这里一律写 `0`，后面也没有读它。`emplace_back(px, py, pz, 0)` 是直接在向量末尾造一个元素。

角度和 Python 相同：

- 北极 `(0, 0, 1)`
- 30 度层 2 个，经度 0 度和 180 度。循环 `j = 0, 1`，`phi = j * pi`
- 60 度层 3 个，经度 0 度、120 度、240 度。`phi = j * 2*pi / 3`

`const float pi = 3.14159265358979323846f` 是自己写下的圆周率。`std::sin`、`std::cos` 用弧度。

注释第 230 行写「立方体面」。6 个方向来自纬度和经度，并不是立方体的 6 个面。立方体六个面的法线应该是正负 x、y、z。这里以注释旁边的数字为准：北极加两个纬度层。

## 第 258 到 359 行：把箭头画成一张小图

```cpp
bool FisheyeProcessor::projectPatch(..., const cv::Vec4f& plane,
                                    cv::Mat& patch, ...)
```

`patch` 是引用，函数里面画好的图会留在调用者的那张 `cv::Mat` 里。

第 265 行 `(void)img_rgb;` 把没用到的参数「用一下」。颜色来自成员 `colors_`，这个图像参数是旧签名留下来的。这样写是为了让编译器不要报警。

第 267 行先把小图涂黑。`CV_8UC3` 是 8 位、3 通道。

第 269 到 271 行：点云是空的、颜色是空的、或者两者个数不同，返回 `false`。调用者会把这次处理当成失败。

第 274 到 283 行造平面上的两根轴，对应 Python 的 `null_space`：

- 取出法线并单位化
- 参考向量默认是 `(0,0,1)`。法线如果已经几乎朝 z（`|n.z| > 0.9`），就改用 `(1,0,0)`，免得两根向量平行
- `u_axis` 是参考向量减去它在法线上的投影，再单位化
- `v_axis` 是法线和 `u_axis` 的叉积

两套轴都和法线垂直，但具体哪根朝右、哪根朝上，可能和 Python 的 `null_space` 差一个旋转。所以 C++ 小图和 Python 小图的内容方向可能不一样，几何来源是同一批点。

第 285 到 312 行逐点筛选，对应 Python 里那几行向量化：

- `P·n < 0` 的点在背面，`continue` 跳过
- `proj = P - (P·n) * n` 去掉法向分量，点落到平面上
- `u`、`v` 是在两根轴上的坐标
- 超出 `patch_size / 2` 的点不要
- 留下的坐标和颜色放进三个向量

第 314 到 316 行：一个点都没留下，返回 `true`。小图保持全黑，这次仍算成功。这和「点云本身是空的就返回 false」不一样。

第 319 到 334 行找 `u`、`v` 的最小值和最大值。`calc_min_max` 是一个写在函数里面的小函数，叫 lambda。`[](...)` 是它的写法。跨度小到几乎为 0 时，把跨度改成 1，避免后面除以 0。

第 339 到 356 行把每个点画上去：

```text
u_norm = (u - u_min) / (u_max - u_min) * (边长 - 1)
```

这和 Python 的 `rescale` 一样，都是把当前这些点拉开，铺满整张小图，而不是按 `patch_size` 的绝对尺寸留白。Python 先缩到 `1..512` 再减 1；C++ 直接缩到 `0..511`。`std::round` 四舍五入后变成整数下标。

`patch.at<cv::Vec3b>(iy, ix)` 取出第 `iy` 行、第 `ix` 列的像素。三个通道各用 `clampf` 夹到 0 到 255，再变成字节。颜色在 `process` 里已经是 0 到 255，这里不再乘 255。Python 是先除以 255、写出时再乘回来。

画完返回 `true`。

## 第 361 到 502 行：处理一整张图

`process` 的输出参数是 `stitched_bgr`。调用者准备好一张空的 `cv::Mat`，函数负责把它填上。

第 367 行给秒表起一个短名字 `clock`。

第 368 行：图是空的，或者不是 8 位 3 通道，直接失败。鱼眼节点如果送来灰度图，会在这里被拒绝。

第 374 到 377 行：BGR 转 RGB，并记下这段时间。和 Python 第 1 步一样，是为了让颜色顺序一致。

第 379 到 405 行收集有效像素，对应 `np.where(valid_range_data == 1)`：

- `struct Pix { int x; int y; }` 是一个只在这个函数里用的小结构，装列号和行号
- `reserve(W * H)` 事先要一块够大的内存，减少中途反复扩容
- 有掩码时，按行拿指针 `ptr<uint8_t>(y)`，这一行里不等于 0 的像素都要
- Python 要求值正好等于 1。C++ 只要不是 0。掩码 png 常常是 0 和 255，这样写才能把 255 当成有效
- 没有掩码时，每个像素都要
- 一个点都没有就 `return false`

第 407 到 414 行降采样。`constexpr` 表示这个 500 万在编译时就定死了，不像 Python 那样还能从 ROS 参数改。个数超过 500 万时：

- `random_device` 取一个随机种子
- `mt19937` 是随机数发生器
- `shuffle` 把坐标打乱
- `resize(MAX_POINTS)` 只留前面 500 万个

打乱后再截断，效果是无放回地随机抽取，和 Python 的 `np.random.choice(..., replace=False)` 同一类做法。

第 417 到 446 行造点云：

- 先 `clear` 再 `reserve`
- 对每个像素调用 `cam2world`
- `dir[2] = -dir[2]`，和 Python 的 `-M[:, 2]` 一样，翻转 z
- 从 RGB 图取出该像素。`at<cv::Vec3b>(y, x)` 是先行后列
- 颜色按 0 到 255 的小数存进 `colors_`。注释写明了和 Python「除以 255」的差别：这里不再除，画小图时也不再乘
- 点云仍是空的就失败

第 448 到 462 行：`definePlanes`，然后一个平面接一个平面调用 `projectPatch`。Python 用 `joblib` 并行算 6 个面，C++ 在这一层是串行的。任何一个面返回 `false`，整张图失败。全黑的面返回的是 `true`，会继续。

第 465 到 480 行拼接。注释写「3x2」和 `[0 1 2; 3 4 5]`。循环说明摆法：

```text
i = 0,1,2 在第 0 行
i = 3,4,5 在第 1 行
每行 3 张
```

大图高 `2 * 512`，宽 `3 * 512`，先涂成白色 `(255,255,255)`。`cv::Rect(左, 上, 宽, 高)` 圈出一块。小图目前是 RGB，`cvtColor` 转回 BGR，再 `copyTo` 贴进这块。发出去的大图因此是 BGR，和 OpenCV、以及话题编码 `bgr8` 一致。

第 482 到 500 行把五段时间减出来：颜色转换、收集坐标、像素变射线、投影、拼接，以及总和。真正的 `cout` 和 `RCLCPP_INFO` 都被 `//` 注释掉了。所以这些时间算完就扔掉，终端上看不到。函数最后 `return true`。

## 相机节点在哪两处用它

算法文件自己不会启动。相机节点持有一个成员：

```cpp
FisheyeProcessor fisheye_proc_;
bool enable_fisheye_{true};
```

注释 `///xinjia` 是后来加进去的标记。

构造函数里，大约第 74 到 100 行：

1. `get_parameter("ocam_yaml_path", ...)` 读路径。yaml 里没有这个参数就打错误日志。注意它没有因为读失败就停下来，空路径会继续传给 `loadCalibration`，然后在那里失败。
2. 同样读取 `valid_mask_path`。
3. 读取 `enable_fisheye_stitch`。读不到就保持 `true`。
4. 开关开着就 `loadCalibration`。失败就把 `enable_fisheye_` 改成 `false`，后面退回发原图。
5. 成功那一句用的是 `RCLCPP_ERROR`。文字是 success，级别却是错误。终端里它会看起来像一条报错。

发布原图的地方在大约第 1116 到 1168 行，只有 `image_raw` 的订阅者数量大于 0 才做事。没人看，就不做鱼眼，省计算。

开关开着时：

```cpp
cv::Mat fisheye_bgr(height, width, CV_8UC3,
                    const_cast<unsigned char*>(img_raw_msg_.data.data()));
```

这行没有把像素复制出来。它让 OpenCV 直接看 ROS 消息里面的那块内存。`const_cast` 是把「只读指针」收成 OpenCV 要的「可写指针」。前提是这张消息真的是 8 位 3 通道，并且字节数等于宽乘高乘 3。

`process` 成功后，另造一条 `Image`：

- 头从原消息抄来。发布前时间戳会被改好几次，最后发出去的是鱼眼算完的时刻，不是曝光时刻。先后顺序见第 3 讲
- 宽高改成大图的宽高
- `encoding` 写成 `bgr8`
- `step` 是每一行占多少字节
- `data.assign(...)` 才把像素复制进新消息
- 仍然用 `img_raw_pub_` 发布

因此话题名字还叫 `image_raw`，里面的内容在开关打开时已经是拼好的大图。Python 节点如果同时订阅这条话题，会把大图再当成鱼眼原图处理一次。两套程序是同一算法的两种写法，应该开一套。

`process` 返回 `false` 时打一条警告，改发真正的原图。开关关着时也直接发原图。

`CMakeLists.txt` 第 101 行把 `fisheye_processor.cpp` 编进相机库，第 109 和 119 行加上 OpenCV 的头文件和库。`package.xml` 里没有单独写 yaml-cpp。机器上如果没有这个库，读标定的那几行会在编译时找不到头文件。

## 和 Python 对照

| 步骤 | Python `fisheye_tool_3.py` | C++ `fisheye_processor.cpp` |
| --- | --- | --- |
| 标定文件 | `.mat` 里的 `ocam` | `ocam.yaml` 的 `ss`、`pol`、圆心和 `c,d,e` |
| 有效像素 | 值正好等于 1 | 值不等于 0 |
| 最多点数 | ROS 参数，默认 500 万 | 写死 500 万 |
| 抽样 | `np.random.choice` | 打乱后截断 |
| 像素变射线 | `np.linalg.inv` 加 `np.polyval` | 手写逆矩阵，霍纳算法算多项式 |
| z | 取相反数 | 取相反数 |
| 颜色 | 先除以 255，写出时乘回 | 一直保持 0 到 255 |
| 6 个平面 | `joblib` 并行 | 一个接一个算 |
| 平面坐标轴 | `null_space` | 参考向量、投影、叉积 |
| 拼图 | 2 行 3 列，白底 | 2 行 3 列，白底，再转回 BGR |
| 谁来跑 | 单独的 Python 节点，订阅 `image_raw` | 相机节点自己，把结果仍发到 `image_raw` |

## 这一讲要能回答的三件事

1. `loadCalibration` 成功才返回 `true`。掩码尺寸不对时它只警告，仍然当成功。
2. `cam2world` 优先用 `ss`。没有 `ss` 才用 `pol`。两个都没有就返回朝向 z 轴的单位箭头。
3. 开关打开时，`image_raw` 上发布的是 2 行 3 列的大图。Python 节点不要再订这一条去做第二次展开。
