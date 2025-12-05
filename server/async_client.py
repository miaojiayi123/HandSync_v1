# async_client.py - 智能动态划分客户端
import cv2
import grpc
import mediapipe as mp
import time
import threading
import socket
import psutil  # 新增：用于系统性能监控
import os
import gesture_pb2
import gesture_pb2_grpc

# ================= 配置区 =================
# 如果是局域网，请填服务端的 IP，例如 '192.168.1.5'
SERVER_IP = 'localhost'
SERVER_PORT = '50051'

# 动态划分阈值
LATENCY_THRESHOLD = 0.1  # 100ms
CHECK_INTERVAL = 3.0  # 3秒


# =========================================

class SharedState:
    """线程共享数据区"""

    def __init__(self):
        self.lock = threading.Lock()
        self.latest_frame = None
        self.landmarks = []
        self.mode = "LOCAL"
        self.latency = 0.0
        self.running = True


class ResourceMonitor(threading.Thread):
    """【新增】后台资源监控线程，负责采样 CPU 和 内存"""

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.cpu_history = []
        self.mem_history = []
        self.process = psutil.Process(os.getpid())

    def run(self):
        # 第一次调用通常返回0，先调用一次
        self.process.cpu_percent()
        while self.running:
            try:
                # 采样 CPU 占用率
                cpu = self.process.cpu_percent(interval=None)
                # 采样 内存 占用 (MB)
                mem = self.process.memory_info().rss / 1024 / 1024

                self.cpu_history.append(cpu)
                self.mem_history.append(mem)

                time.sleep(0.5)  # 每0.5秒采样一次，避免消耗过多资源
            except:
                break

    def stop(self):
        self.running = False


class InferenceWorker(threading.Thread):
    """后台推理线程"""

    def __init__(self, shared_state):
        super().__init__()
        self.state = shared_state
        self.daemon = True

        # 初始化模型与连接
        self.mp_hands = mp.solutions.hands
        self.local_hands = self.mp_hands.Hands(max_num_hands=1)
        self.stub = None
        self.connect_server()

        # 决策状态
        self.use_cloud = True
        self.last_check_time = time.time()

    def connect_server(self):
        try:
            addr = f"{SERVER_IP}:{SERVER_PORT}"
            channel = grpc.insecure_channel(addr)
            self.stub = gesture_pb2_grpc.GestureServiceStub(channel)
        except:
            print("初始化连接失败，将使用本地模式")

    def run(self):
        while self.state.running:
            with self.state.lock:
                if self.state.latest_frame is None:
                    time.sleep(0.01)
                    continue
                frame = self.state.latest_frame.copy()

            start_t = time.time()
            result_landmarks = []
            current_mode = ""

            # === Part C: 动态决策逻辑 ===
            if self.use_cloud and self.state.latency > LATENCY_THRESHOLD:
                self.use_cloud = False  # 降级
            elif not self.use_cloud and (time.time() - self.last_check_time > CHECK_INTERVAL):
                self.use_cloud = True  # 尝试恢复
                self.last_check_time = time.time()

            # === 执行 ===
            if self.use_cloud:
                current_mode = "CLOUD"
                try:
                    img_small = cv2.resize(frame, (320, 240))
                    _, buf = cv2.imencode('.jpg', img_small, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    req = gesture_pb2.ImageRequest(image=buf.tobytes())
                    resp = self.stub.DetectHand(req)
                    result_landmarks = list(resp.landmarks)
                except:
                    self.use_cloud = False
                    current_mode = "LOCAL(Fallback)"

            if not self.use_cloud or not result_landmarks:
                if not result_landmarks: current_mode = "LOCAL"
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = self.local_hands.process(rgb)
                if res.multi_hand_landmarks:
                    for lm in res.multi_hand_landmarks[0].landmark:
                        result_landmarks.extend([lm.x, lm.y, lm.z])

            latency = time.time() - start_t

            with self.state.lock:
                self.state.landmarks = result_landmarks
                self.state.mode = current_mode
                self.state.latency = latency


import math


def classify_gesture(landmarks):
    """
    根据 landmarks (21个点) 识别手势
    返回: 手势名称 (str)
    """
    if not landmarks or len(landmarks) < 63:
        return "Unknown"

    # 将平铺的列表转换为 (x, y) 坐标列表，方便计算
    points = []
    for i in range(0, len(landmarks), 3):
        points.append((landmarks[i], landmarks[i + 1]))

    # 定义关键点索引
    # 0: Wrist
    # Tips: 4(Thumb), 8(Index), 12(Middle), 16(Ring), 20(Pinky)
    # PIPs (指关节): 2, 6, 10, 14, 18
    # MCPs (指根): 1, 5, 9, 13, 17

    fingers_up = [False, False, False, False, False]  # 拇指, 食指, 中指, 无名指, 小指

    # 1. 判断食指、中指、无名指、小指是否伸直
    # 逻辑：如果 指尖到手腕的距离 > 指关节到手腕的距离，则认为伸直
    # 使用欧几里得距离平方 (避免开根号，速度快)
    wrist = points[0]

    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]

    for i in range(4):
        tip = points[finger_tips[i]]
        pip = points[finger_pips[i]]

        dist_tip = (tip[0] - wrist[0]) ** 2 + (tip[1] - wrist[1]) ** 2
        dist_pip = (pip[0] - wrist[0]) ** 2 + (pip[1] - wrist[1]) ** 2

        if dist_tip > dist_pip:
            fingers_up[i + 1] = True

    # 2. 判断拇指是否伸直 (拇指比较特殊，主要看X轴偏移)
    # 简单逻辑：比较拇指尖和拇指关节相对于手掌的偏移
    # 这里用一个简化版：对比拇指尖(4)和食指根(5)的距离 vs 拇指关节(2)和食指根(5)
    thumb_tip = points[4]
    thumb_ip = points[3]
    index_mcp = points[5]  # 参考点

    dist_tip_ref = (thumb_tip[0] - index_mcp[0]) ** 2 + (thumb_tip[1] - index_mcp[1]) ** 2
    dist_ip_ref = (thumb_ip[0] - index_mcp[0]) ** 2 + (thumb_ip[1] - index_mcp[1]) ** 2

    if dist_tip_ref > dist_ip_ref:
        fingers_up[0] = True

    # 3. 统计伸直的手指数量并命名
    up_count = fingers_up.count(True)
    gesture_name = "Unknown"

    if up_count == 0:
        gesture_name = "Rock (Fist)"  # 石头
    elif up_count == 5:
        gesture_name = "Paper (Palm)"  # 布
    elif up_count == 2 and fingers_up[1] and fingers_up[2]:
        gesture_name = "Scissors"  # 剪刀
    elif up_count == 1 and fingers_up[1]:
        gesture_name = "One"  # 数字1
    elif up_count == 1 and fingers_up[0]:  # 仅拇指
        gesture_name = "Good / Like"
    elif up_count == 3 and fingers_up[1] and fingers_up[2] and fingers_up[3]:
        gesture_name = "Three"
    elif up_count == 2 and fingers_up[0] and fingers_up[4]:  # 拇指+小指
        gesture_name = "Call Me (6)"

    return gesture_name


def draw_ui(frame, landmarks, mode, latency, fps):
    h, w, c = frame.shape
    gesture_text = "Waiting..."

    # 1. 画手势骨架
    if landmarks:
        # === 新增：调用识别逻辑 ===
        gesture_text = classify_gesture(landmarks)

        # 画点
        for i in range(0, len(landmarks), 3):
            cx, cy = int(landmarks[i] * w), int(landmarks[i + 1] * h)
            cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)

    # 2. 画信息面板
    color = (0, 255, 0) if "LOCAL" in mode else (0, 165, 255)

    # 加宽背景框以容纳手势名称
    cv2.rectangle(frame, (0, 0), (350, 150), (0, 0, 0), -1)

    cv2.putText(frame, f"Mode: {mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(frame, f"Latency: {latency * 1000:.0f} ms", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
    cv2.putText(frame, f"UI FPS: {fps:.0f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

    # === 新增：显示手势名称 ===
    # 如果识别出石头剪刀布，用显眼的颜色
    gesture_color = (0, 255, 255)  # 黄色
    if "Rock" in gesture_text or "Paper" in gesture_text or "Scissors" in gesture_text:
        gesture_color = (0, 0, 255)  # 红色强调

    cv2.putText(frame, f"Gesture: {gesture_text}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, gesture_color, 2)


def print_performance_report(start_time, frame_count, fps_list, latency_list, monitor):
    """【新增】打印最终报告"""
    total_time = time.time() - start_time

    # 防止除以零
    if frame_count == 0 or not monitor.cpu_history:
        print("运行时间太短，无数据。")
        return

    avg_frame_time_ms = (total_time / frame_count) * 1000
    avg_fps = sum(fps_list) / len(fps_list)
    avg_latency = (sum(latency_list) / len(latency_list)) * 1000

    avg_cpu = sum(monitor.cpu_history) / len(monitor.cpu_history)
    avg_mem = sum(monitor.mem_history) / len(monitor.mem_history)

    # 能耗估算
    run_minutes = total_time / 60.0
    # 系数 0.12 是基于 MacBook M1 的经验值，你可以根据设备调整
    estimated_power_mah = avg_cpu * run_minutes * 0.12
    power_10min = estimated_power_mah * (10 / run_minutes) if run_minutes > 0 else 0

    print("\n" + "=" * 60)
    print("📢 软件体系结构 - 动态分区性能测试报告")
    print("=" * 60)
    print(f"总运行时间     : {total_time:.2f} 秒")
    print(f"总处理帧数     : {frame_count} 帧")
    print(f"平均处理延迟   : {avg_latency:.2f} ms (反映计算+网络耗时)")
    print(f"平均 UI FPS    : {avg_fps:.1f} (反映流畅度)")
    print("-" * 60)
    print(f"平均 CPU 占用  : {avg_cpu:.1f}%")
    print(f"平均 内存 占用 : {avg_mem:.1f} MB")
    print(f"估算能耗(10min): {power_10min:.1f} mAh (基于 CPU 负载估算)")
    print("-" * 60)
    print(f"峰值 FPS       : {max(fps_list):.1f}")
    print(f"最低 FPS       : {min(fps_list):.1f}")
    print("=" * 60 + "\n")


def main():
    # 1. 启动资源监控
    monitor = ResourceMonitor()
    monitor.start()

    # 2. 启动推理线程
    shared = SharedState()
    worker = InferenceWorker(shared)
    worker.start()

    cap = cv2.VideoCapture(0)
    print("系统启动成功。按 'q' 或 'Esc' 退出并生成报告。")

    # 统计数据容器
    fps_history = []
    latency_history = []
    frame_count = 0
    start_time = time.time()
    prev_time = start_time

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.flip(frame, 1)

            with shared.lock:
                shared.latest_frame = frame
                cur_landmarks = list(shared.landmarks)
                cur_mode = shared.mode
                cur_latency = shared.latency

            # 记录数据
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time + 1e-6)
            prev_time = curr_time

            # 只有当 FPS 稳定后才开始记录，避免启动时的抖动
            if frame_count > 10:
                fps_history.append(fps)
                latency_history.append(cur_latency)

            draw_ui(frame, cur_landmarks, cur_mode, cur_latency, fps)
            cv2.imshow('Smart Offloading System', frame)

            frame_count += 1

            key = cv2.waitKey(1) & 0xFF
            if key in [ord('q'), 27]:  # q 或 Esc
                shared.running = False
                break
    except KeyboardInterrupt:
        pass
    finally:
        # 停止并清理
        shared.running = False
        monitor.stop()
        cap.release()
        cv2.destroyAllWindows()

        # 打印报告
        print_performance_report(start_time, frame_count, fps_history, latency_history, monitor)


if __name__ == '__main__':
    main()