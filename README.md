# 动态分区手势识别系统

---

## 项目概述

本项目实现了一个 **智能动态分区手势识别系统**，支持以下三种部署模式：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **纯本地部署** | 全部在本地运行，无网络依赖 | 离线环境、隐私保护 |
| **纯网页部署** | 浏览器访问，无需安装 Python | 教学演示、远程展示 |
| **gRPC 动态分区** | 云端推理 + 本地 fallback | 边缘设备、弱网环境 |

---

## 环境准备

### 1. 安装依赖

```bash
pip install opencv-python mediapipe grpcio grpcio-tools numpy psutil
```

### 2. 生成协议文件（只需一次）

```bash
# 在 proto/ 目录下执行
python -m grpc_tools.protoc -I. --python_out=../server --grpc_python_out=../server gesture.proto
```

---

# 部署模式一：**纯本地部署**（零网络）

### 步骤

1. **运行本地识别程序**

```bash
python client/local_only.py
```

2. **效果**
   - 摄像头实时识别手势
   - 无网络依赖
   - FPS较高

---

# 部署模式二：**纯网页部署**（浏览器访问）

### 步骤

1. **启动本地 Web 服务器**

```bash
# 方法1：Python 简单服务器
python -m http.server 8000

# 方法2：VSCode Live Server
```

2. **浏览器访问**

```
http://localhost:8000
```

3. **效果**
   - 浏览器摄像头实时识别
   - 无需安装 Python

---

# 部署模式三：**gRPC 动态分区**（云端 + 本地 fallback）

### 步骤 1：启动云端服务（Colab）

1. 打开 [Google Colab](https://colab.research.google.com/)
2. 上传 `server/` 目录下（`gesture_pb2.py`、`gesture_pb2_grpc.py`）
3. 单元格输入并执行
```bash
!pip install mediapipe opencv-python grpcio grpcio-tools numpy
````
3. 新的一个单元格粘贴并运行 `server.py`

输出：
```text
协议文件加载成功
gRPC 服务器启动成功
tcp://abcd-34-41-38-3.a.free.pinggy.link:12345
复制到 client.py: CLOUD_ADDR = 'abcd-34-41-38-3.a.free.pinggy.link:12345'
```

### 步骤 2：运行本地客户端

1. **修改 `client.py` 中的地址（启动server脚本后输出的地址）**

```python
CLOUD_ADDR = "abcd-34-41-38-3.a.free.pinggy.link:12345"  # 替换为你的地址
```

2. **运行客户端**

```bash
python client/client.py
```

3. **效果**
   - 正常网络：`Mode: 云端 gRPC`（黄色文字）
   - 网络延迟 >100ms：自动切 `本地模式`（绿色文字）
   - 断网：强制本地，丝滑运行

---

## 性能报告（按 ESC 退出后自动打印）

```text
======================================================================
                    动态分区性能报告
======================================================================
总运行时间     : 45.23 秒
总帧数         : 1120
平均延迟       : 40.38 ms
平均 FPS       : 24.8
平均 CPU 占用  : 32.1%
平均内存占用   : 185.4 MB
估算能耗 (10min): 128.4 mAh
峰值 FPS       : 31.2
最低 FPS       : 18.5
最终模式       : 云端 gRPC
======================================================================
```

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `ModuleNotFoundError: No module named 'gesture_pb2'` | 重新生成 `.py` 文件 |
| `UNAVAILABLE: Socket closed` | 重启 `server.py` 获取新地址 |
| 手上无关键点 | 确保 `landmarks` 是 `float`，JPEG 质量 ≥80 |
| 网页摄像头无权限 | 允许浏览器访问摄像头 |
| `Descriptor object is not callable` | 使用 `DetectionResponse()` 而非 `_DETECTIONRESPONSE()` |

---

## 贡献与反馈

- **Star 本项目**
- **提交 Issue**
- **PR 欢迎优化**

---

**项目地址：** [https://github.com/miaojiayi123/HandSync_v1](https://github.com/miaojiayi123/HandSync_v1) 

**作者：** 缪家逸

**日期：** 2025-11-03

---
