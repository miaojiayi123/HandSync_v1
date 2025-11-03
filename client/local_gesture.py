import cv2
import mediapipe as mp
import time
import psutil
import os
import threading

# ==================== 初始化 ====================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("无法打开摄像头")

# 性能统计变量
frame_count = 0
total_time = 0
fps_list = []
cpu_list = []
memory_list = []

# 获取当前进程
process = psutil.Process(os.getpid())

print("全本地手势识别程序启动")
print("按 ESC 键退出")
print("-" * 50)

# ==================== 性能监控线程 ====================
def monitor_performance():
    while True:
        cpu = process.cpu_percent(interval=0.1)
        memory = process.memory_info().rss / 1024 / 1024  # MB
        cpu_list.append(cpu)
        memory_list.append(memory)
        time.sleep(0.1)

# 启动监控线程
monitor_thread = threading.Thread(target=monitor_performance, daemon=True)
monitor_thread.start()

# ==================== 主循环 ====================
while cap.isOpened():
    start_time = time.time()

    ret, frame = cap.read()
    if not ret:
        print("摄像头读取失败")
        break

    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    # 绘制关键点
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=4),
                mp_draw.DrawingSpec(color=(0, 255, 255), thickness=2)
            )

    # 计算实时 FPS
    end_time = time.time()
    frame_time = end_time - start_time
    fps = 1 / frame_time if frame_time > 0 else 0
    fps_list.append(fps)

    # 实时显示
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    cv2.putText(frame, "Mode: Local", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

    cv2.imshow("Hand Gesture Recognition - Local Mode", frame)

    # 统计
    frame_count += 1
    total_time += frame_time

    if cv2.waitKey(1) == 27:  # ESC
        break

# ==================== 释放资源 ====================
cap.release()
cv2.destroyAllWindows()
hands.close()

# ==================== 性能分析输出 ====================
avg_frame_time_ms = total_time / frame_count * 1000
avg_fps = sum(fps_list) / len(fps_list)
avg_cpu = sum(cpu_list) / len(cpu_list)
avg_memory = sum(memory_list) / len(memory_list)

# 估算能耗（经验公式：mAh = CPU% × 运行时间 × 系数）
# 系数 ≈ 0.12 mAh/%/min（MacBook M1 实测）
run_minutes = total_time / 60
estimated_power_mah = avg_cpu * run_minutes * 0.12

print("=" * 60)
print("性能测试报告")
print("=" * 60)
print(f"总运行时间     : {total_time:.2f} 秒")
print(f"总帧数         : {frame_count}")
print(f"平均帧时间     : {avg_frame_time_ms:.2f} ms")
print(f"平均 FPS       : {avg_fps:.1f}")
print(f"平均 CPU 占用  : {avg_cpu:.1f}%")
print(f"平均内存占用   : {avg_memory:.1f} MB")
print(f"估算能耗 (10min): {estimated_power_mah * (10/run_minutes):.1f} mAh")
print(f"峰值 FPS       : {max(fps_list):.1f}")
print(f"最低 FPS       : {min(fps_list):.1f}")
print("=" * 60)