# local_gesture.py
import cv2
import mediapipe as mp
import time
import psutil
import os
import threading
import math

# ==================== 配置区 ====================
# 纯本地模式不需要服务器地址
# ===============================================

# 初始化 MediaPipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# 性能统计全局变量
frame_count = 0
fps_history = []
cpu_history = []
mem_history = []
running = True

# 获取当前进程用于监控
process = psutil.Process(os.getpid())


def monitor_performance():
    """后台监控线程：每0.5秒采样一次系统资源"""
    # 首次调用通常为0，先消耗掉
    process.cpu_percent()
    while running:
        try:
            # 采样 CPU (%)
            cpu = process.cpu_percent(interval=None)
            # 采样 内存 (MB)
            mem = process.memory_info().rss / 1024 / 1024

            cpu_history.append(cpu)
            mem_history.append(mem)
            time.sleep(0.5)
        except:
            break


def classify_gesture(landmarks):
    """
    几何规则分类器 (与客户端逻辑保持完全一致)
    输入: [x0, y0, z0, x1, y1, z1, ...] (63个浮点数的列表)
    返回: 手势名称
    """
    if not landmarks or len(landmarks) < 63:
        return "Unknown"

    points = []
    for i in range(0, len(landmarks), 3):
        points.append((landmarks[i], landmarks[i + 1]))

    # 指尖与指关节索引
    # 0: Wrist
    # Tips: 4, 8, 12, 16, 20
    # PIPs: 2, 6, 10, 14, 18
    fingers_up = [False, False, False, False, False]

    wrist = points[0]

    # 1. 判断除拇指外的四指
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]

    for i in range(4):
        tip = points[finger_tips[i]]
        pip = points[finger_pips[i]]
        # 距离比较
        dist_tip = (tip[0] - wrist[0]) ** 2 + (tip[1] - wrist[1]) ** 2
        dist_pip = (pip[0] - wrist[0]) ** 2 + (pip[1] - wrist[1]) ** 2
        if dist_tip > dist_pip:
            fingers_up[i + 1] = True

    # 2. 判断拇指
    thumb_tip = points[4]
    thumb_ip = points[3]
    index_mcp = points[5]

    dist_tip_ref = (thumb_tip[0] - index_mcp[0]) ** 2 + (thumb_tip[1] - index_mcp[1]) ** 2
    dist_ip_ref = (thumb_ip[0] - index_mcp[0]) ** 2 + (thumb_ip[1] - index_mcp[1]) ** 2

    if dist_tip_ref > dist_ip_ref:
        fingers_up[0] = True

    # 3. 命名
    up_count = fingers_up.count(True)
    gesture_name = "Unknown"

    if up_count == 0:
        gesture_name = "Rock (Fist)"
    elif up_count == 5:
        gesture_name = "Paper (Palm)"
    elif up_count == 2 and fingers_up[1] and fingers_up[2]:
        gesture_name = "Scissors"
    elif up_count == 1 and fingers_up[1]:
        gesture_name = "One"
    elif up_count == 1 and fingers_up[0]:
        gesture_name = "Good / Like"
    elif up_count == 3 and fingers_up[1] and fingers_up[2] and fingers_up[3]:
        gesture_name = "Three"
    elif up_count == 2 and fingers_up[0] and fingers_up[4]:
        gesture_name = "Call Me (6)"

    return gesture_name


def main():
    global frame_count, running

    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_performance, daemon=True)
    monitor_thread.start()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return

    print("=" * 50)
    print("全本地手势识别 (Pure Local Mode) 已启动")
    print("按 'ESC' 或 'q' 退出并查看性能报告")
    print("=" * 50)

    start_time_all = time.time()
    prev_time = start_time_all

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape

            # === 核心处理流水线 ===
            start_process = time.time()

            # 1. 转换颜色
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 2. MediaPipe 推理
            results = hands.process(rgb)

            latency = time.time() - start_process

            gesture_name = "Waiting..."

            # 3. 绘制与分类
            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    # 绘制骨架
                    mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                    # 提取坐标列表供分类器使用
                    landmarks_list = []
                    for lm in hand_lms.landmark:
                        landmarks_list.extend([lm.x, lm.y, lm.z])

                    # 识别手势
                    gesture_name = classify_gesture(landmarks_list)

            # 4. 计算 UI FPS
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time + 1e-6)
            prev_time = curr_time

            if frame_count > 10:  # 略过启动时的波动
                fps_history.append(fps)

            frame_count += 1

            # === UI 绘制 ===
            # 信息板背景
            cv2.rectangle(frame, (0, 0), (350, 160), (0, 0, 0), -1)

            # 绿色表示本地模式
            cv2.putText(frame, "Mode: PURE LOCAL", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Latency: {latency * 1000:.1f} ms", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (255, 255, 255), 1)
            cv2.putText(frame, f"FPS: {fps:.0f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

            # 手势结果 (高亮显示)
            g_color = (0, 255, 255)
            if "Rock" in gesture_name or "Paper" in gesture_name or "Scissors" in gesture_name:
                g_color = (0, 0, 255)  # 红色高亮
            cv2.putText(frame, f"Gesture: {gesture_name}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, g_color, 2)

            cv2.imshow('Pure Local Gesture Recognition', frame)

            if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
                break

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        cap.release()
        cv2.destroyAllWindows()
        hands.close()

        # === 打印专业性能报告 ===
        total_time = time.time() - start_time_all

        # 避免除以零
        avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
        avg_cpu = sum(cpu_history) / len(cpu_history) if cpu_history else 0
        avg_mem = sum(mem_history) / len(mem_history) if mem_history else 0

        # 能耗估算 (基于 CPU 负载)
        run_minutes = total_time / 60
        estimated_power_mah = avg_cpu * run_minutes * 0.12
        power_10min = estimated_power_mah * (10 / run_minutes) if run_minutes > 0 else 0

        print("\n" + "=" * 60)
        print("📊 软件体系结构 - 纯本地模式性能报告")
        print("=" * 60)
        print(f"总运行时间     : {total_time:.2f} 秒")
        print(f"总处理帧数     : {frame_count} 帧")
        print(f"平均 FPS       : {avg_fps:.1f}")
        print("-" * 60)
        print(f"平均 CPU 占用  : {avg_cpu:.1f}%")
        print(f"平均 内存 占用 : {avg_mem:.1f} MB")
        print(f"估算能耗(10min): {power_10min:.1f} mAh (本地计算负载较高)")
        print("-" * 60)
        if fps_history:
            print(f"峰值 FPS       : {max(fps_history):.1f}")
            print(f"最低 FPS       : {min(fps_history):.1f}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()