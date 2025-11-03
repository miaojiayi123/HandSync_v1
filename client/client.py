# client.py - 动态分区手势识别（本地 + gRPC 云端，修复关键点显示）
# 功能：云端/本地手势识别，动态切换，性能报告
# 使用最新 Pinggy 地址：从 server.py 获取

import cv2
import grpc
import mediapipe as mp
from server import gesture_pb2, gesture_pb2_grpc
import time
import psutil
import os
import threading
import socket
from mediapipe.framework.formats import landmark_pb2

# ==================== 云端地址（从 server.py 获取） ====================
CLOUD_ADDR = "uqvjh-34-41-38-3.a.free.pinggy.link:37145"  # 替换为新地址
# ================================================================

# 初始化本地 MediaPipe
mp_hands = mp.solutions.hands
local_hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,  # 降低阈值
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils


# gRPC 通道（支持重连）
def create_channel():
    return grpc.insecure_channel(
        CLOUD_ADDR,
        options=[
            ('grpc.keepalive_time_ms', 10000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),
        ]
    )


channel = create_channel()
stub = gesture_pb2_grpc.GestureServiceStub(channel)

# 性能统计
frame_count = 0
total_time = 0
fps_list = []
cpu_list = []
memory_list = []
use_local = False
process = psutil.Process(os.getpid())
last_network_check = 0

# 打开摄像头
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("无法打开摄像头")

print("动态分区手势识别启动")
print("按 ESC 退出")
print("-" * 60)


# ==================== 性能监控线程 ====================
def monitor_performance():
    while True:
        cpu_list.append(process.cpu_percent(interval=0.1))
        memory_list.append(process.memory_info().rss / 1024 / 1024)
        time.sleep(0.1)


threading.Thread(target=monitor_performance, daemon=True).start()


# ==================== 网络检测 + 动态切换 ====================
def check_and_switch():
    global use_local, last_network_check, channel, stub
    while True:
        now = time.time()
        if now - last_network_check < 3:
            time.sleep(1)
            continue
        last_network_check = now

        start = time.time()
        try:
            s = socket.create_connection(("8.8.8.8", 53), timeout=2)
            s.close()
            ping = (time.time() - start) * 1000
            if ping > 100 and not use_local:
                use_local = True
                print(f"网络延迟 {ping:.0f}ms > 100ms，切换本地模式")
            elif ping < 50 and use_local:
                use_local = False
                print(f"网络恢复 {ping:.0f}ms < 50ms，切换云端模式")
                channel = create_channel()
                stub = gesture_pb2_grpc.GestureServiceStub(channel)
        except:
            if not use_local:
                use_local = True
                print("网络断开，强制切换本地模式")
        time.sleep(1)


threading.Thread(target=check_and_switch, daemon=True).start()

# ==================== 主循环 ====================
while cap.isOpened():
    start_time = time.time()

    ret, frame = cap.read()
    if not ret:
        print("摄像头读取失败")
        break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (640, 480))

    landmarks = None
    hand_landmarks_obj = None

    if use_local:
        # 本地推理
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = local_hands.process(rgb_frame)
        if results.multi_hand_landmarks:
            hand_landmarks_obj = results.multi_hand_landmarks[0]
            landmarks = [(lm.x, lm.y) for lm in hand_landmarks_obj.landmark]
            print(f"本地检测到手: {landmarks[:3]}...")  # 调试
        else:
            print("本地未检测到手")

    else:
        # 云端推理
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        request = gesture_pb2.ImageRequest(image=buffer.tobytes())
        try:
            response = stub.DetectHand(request, timeout=3.0)
            print(f"收到 landmarks 长度: {len(response.landmarks)}")
            if len(response.landmarks) == 63:
                if all(x == 0.0 for x in response.landmarks):
                    print("警告: 云端返回全0关键点")
                else:
                    print(f"云端关键点: {response.landmarks[:6]}...")
                landmark_list = landmark_pb2.NormalizedLandmarkList()
                for i in range(21):
                    lm = landmark_list.landmark.add()
                    lm.x = response.landmarks[i * 3]
                    lm.y = response.landmarks[i * 3 + 1]
                    lm.z = response.landmarks[i * 3 + 2]
                hand_landmarks_obj = type('obj', (object,), {
                    'landmark': landmark_list.landmark
                })()
                landmarks = [(lm.x, lm.y) for lm in landmark_list.landmark]
            else:
                print(f"警告: landmarks 长度异常: {len(response.landmarks)}")
        except Exception as e:
            print(f"云端超时: {e}，切换本地")
            use_local = True

    # 绘制关键点和连线
    if landmarks and hand_landmarks_obj:
        h, w = frame.shape[:2]
        for x, y in landmarks:
            cv2.circle(frame, (int(x * w), int(y * h)), 6, (0, 255, 0), -1)

        mp_draw.draw_landmarks(
            frame, hand_landmarks_obj, mp_hands.HAND_CONNECTIONS,
            mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=4),
            mp_draw.DrawingSpec(color=(0, 255, 255), thickness=2)
        )

    # 计算性能
    frame_time = time.time() - start_time
    fps = 1 / frame_time if frame_time > 0 else 0
    fps_list.append(fps)
    total_time += frame_time
    frame_count += 1

    # 显示信息
    mode_text = "本地模式" if use_local else "云端 gRPC"
    mode_color = (0, 255, 0) if use_local else (255, 255, 0)
    cv2.putText(frame, f"Mode: {mode_text}", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, mode_color, 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    cv2.putText(frame, f"Delay: {frame_time * 1000:.1f}ms", (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)
    cv2.putText(frame, f"Frames: {frame_count}", (10, 160),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    cv2.imshow("Dynamic Partitioning - Hand Gesture Recognition", frame)

    if cv2.waitKey(1) == 27:  # ESC
        break

# ==================== 资源释放 ====================
cap.release()
cv2.destroyAllWindows()
local_hands.close()

# ==================== 性能报告 ====================
if frame_count > 0:
    avg_frame_time_ms = total_time / frame_count * 1000
    avg_fps = sum(fps_list) / len(fps_list)
    avg_cpu = sum(cpu_list) / len(cpu_list) if cpu_list else 0
    avg_memory = sum(memory_list) / len(memory_list) if memory_list else 0
    run_minutes = total_time / 60
    estimated_power_mah = avg_cpu * run_minutes * 0.12

    print("=" * 70)
    print("                    动态分区性能报告")
    print("=" * 70)
    print(f"总运行时间     : {total_time:.2f} 秒")
    print(f"总帧数         : {frame_count}")
    print(f"平均延迟       : {avg_frame_time_ms:.2f} ms")
    print(f"平均 FPS       : {avg_fps:.1f}")
    print(f"平均 CPU 占用  : {avg_cpu:.1f}%")
    print(f"平均内存占用   : {avg_memory:.1f} MB")
    print(f"估算能耗 (10min): {estimated_power_mah * (10 / run_minutes):.1f} mAh")
    print(f"峰值 FPS       : {max(fps_list):.1f}")
    print(f"最低 FPS       : {min(fps_list):.1f}")
    print(f"最终模式       : {'本地' if use_local else '云端 gRPC'}")
    print("=" * 70)