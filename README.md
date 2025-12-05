
# HandSync: 智能动态分区手势识别系统

### (Smart Dynamic Partitioning Hand Gesture Recognition System)

   

## 📖 项目简介 (Introduction)

本项目是 **软件体系结构 (Software Architecture)** 课程关于移动云计算的研究实践。

项目针对计算密集型应用（手势识别）在移动端运行时的性能瓶颈，设计并实现了一个基于 **gRPC** 的 **计算卸载（Computation Offloading）** 系统。系统采用 **异步双缓冲（Asynchronous Double-Buffering）** 架构，能够根据网络状况（RTT 延迟）在 **本地 (Local)** 和 **边缘服务器 (Edge Server)** 之间动态迁移计算任务，实现“云边端”协同计算。

-----

## 📂 项目结构 (Directory Structure)

```text
HandSync_v1/
├── local/
│   └── local_gesture.py      # [基准] 纯本地全功能识别 (Baseline)
├── proto/
│   └── gesture.proto         # [协议] gRPC 通信协议定义文件
├── server/
│   ├── run_server.py         # [服务端] 边缘服务端入口 (gRPC Server)
│   ├── async_client.py       # [客户端] 动态分区客户端 (原 async_sever.py)
│   ├── gesture_pb2.py        # [自动生成] 协议代码
│   └── gesture_pb2_grpc.py   # [自动生成] gRPC 代码
├── web/
│   └── index.html            # [网页端] 纯网页版 (WebAssembly)
├── requirements.txt          # 依赖列表
└── README.md                 # 项目说明文档
```

> **注意**：`server/` 文件夹中同时包含了服务端代码 (`run_server.py`) 和客户端代码 (`async_client.py`)，这是为了方便两者共享生成的协议文件 (`_pb2.py`)。

-----

## 🛠️ 环境准备 (Prerequisites)

### 1\. 安装 Python 依赖

建议使用 Python 3.10 或更高版本。

```bash
pip install grpcio grpcio-tools protobuf opencv-python mediapipe numpy psutil -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 📦 安装命令

保存文件后，在终端运行：

```bash
pip install -r requirements.txt
```

建议使用国内镜像源以加快速度（如果你在中国）：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2\. 编译 gRPC 协议 (首次运行或协议修改后执行)

由于代码移动到了不同文件夹，请在 **项目根目录** 下执行以下命令，将 `proto/` 中的协议编译并输出到 `server/` 文件夹中：

```bash
# 在 HandSync_v1 根目录下执行
python -m grpc_tools.protoc -Iproto --python_out=server --grpc_python_out=server proto/gesture.proto
```

-----

## 🚀 部署模式指南

本项目支持三种运行模式，分别对应实验报告的三个部分。

### 🟢 模式一：纯本地部署 (Part A - Baseline)

> **场景**：完全离线，作为性能对比的基准线。

1.  **启动命令**：
    ```bash
    # 在根目录下执行
    python local/local_gesture.py
    ```
2.  **预期效果**：
      * 完全依赖本地 CPU，CPU 占用率较高。
      * 屏幕显示绿色 `Mode: PURE LOCAL`。

### 🔵 模式二：纯网页部署 (Part B - Web Demo)

> **场景**：无需安装环境，基于 MediaPipe WebAssembly 技术。

1.  **进入目录并启动服务器**：
    ```bash
    cd web
    python -m http.server 8000
    ```
2.  **访问地址**：
    打开 Chrome 浏览器访问 `http://localhost:8000`。
3.  **预期效果**：
      * 显示 `Mode: PURE WEB (JS)`。
      * 页面实时展示主线程负载率 (Load)。

### 🟠 模式三：gRPC 动态分区 (Part C - Core)

> **场景**：这是本项目的**核心**，展示移动端与服务器的协同工作。支持 **“单机模拟”** 和 **“双机局域网”** 两种拓扑结构。

#### 场景 A：单机闭环开发 (Single Machine)

> **适用**：开发调试、独自一人演示。

1.  **启动服务端**：
    打开终端 1，运行：
    ```bash
    python server/run_server.py
    ```
2.  **配置客户端**：
    打开 `server/async_client.py`，确保 IP 为 `localhost`：
    ```python
    SERVER_IP = 'localhost'
    SERVER_PORT = '50051'
    ```
3.  **启动客户端**：
    打开终端 2，运行：
    ```bash
    python server/async_client.py
    ```

-----

#### 场景 B：双机局域网演示 (Dual Machine LAN)

> **适用**：**最终答辩演示**。模拟真实的边缘计算环境（一台电脑做 Server，一台电脑做 Client）。

1.  **网络准备**：

      * 确保两台电脑连接到**同一个 WiFi** (或手机热点)。
      * 假设 **电脑 A** 是服务器，**电脑 B** 是客户端。

2.  **启动服务端 (电脑 A)**：
    运行 `python server/run_server.py`。
    *终端会显示局域网 IP，例如 `192.168.1.105`，请记下它。*

3.  **配置客户端 (电脑 B)**：
    打开电脑 B 上的 `server/async_client.py`，修改 IP：

    ```python
    SERVER_IP = '192.168.1.105'  # 填入电脑 A 的 IP
    SERVER_PORT = '50051'
    ```

4.  **启动客户端 (电脑 B)**：
    运行 `python server/async_client.py`。

5.  **验证动态切换 (Demo 环节)**：

      * **正常状态**：客户端显示橙色 `Mode: CLOUD (Remote)`。
      * **故障模拟**：断开电脑 A 的网络或关闭 Server。
      * **自适应切换**：客户端瞬间切换为绿色 `Mode: LOCAL (Fallback)`，系统不崩溃。
      * **恢复**：重启 Server，客户端自动切回 `CLOUD` 模式。

-----

## 📊 性能量化报告

所有 Python 脚本在按下 `ESC` 或 `q` 退出时，都会自动计算并打印详细的性能报告。

**示例输出：**

```text
======================================================================
📢 软件体系结构 - 动态分区性能测试报告
======================================================================
总运行时间     : 65.40 秒
总处理帧数     : 1850 帧
平均处理延迟   : 42.15 ms  (含网络传输+云端推理)
平均 UI FPS    : 29.5      (异步架构保证流畅度)
----------------------------------------------------------------------
平均 CPU 占用  : 12.5%     (云端卸载后显著降低本地负载)
平均 内存 占用 : 110.2 MB
估算能耗(10min): 45.2 mAh  (相比纯本地节省约 40% 电量)
======================================================================
```

-----

## 📧 联系与反馈

  * **Author**: 缪家逸 (Miaojiayi)
  * **Course**: 软件体系结构 2025 Fall
  * **Date**: 2025-12-04
  * **Github**: [https://github.com/miaojiayi123/HandSync\_v1](https://github.com/miaojiayi123/HandSync_v1)

-----

*Developed for Software Architecture Course Assignment.*


### 📦 安装命令

保存文件后，在终端运行：

```bash
pip install -r requirements.txt
```

建议使用国内镜像源以加快速度（如果你在中国）：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
