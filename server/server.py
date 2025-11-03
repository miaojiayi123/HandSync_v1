# server.py - 终极修复版（修复 landmarks 类型 + 调试日志）
import grpc
from concurrent import futures
import cv2
import numpy as np
import mediapipe as mp
import subprocess

# ==================== 1. 导入 ====================
import gesture_pb2
import gesture_pb2_grpc
print("协议文件加载成功")

# ==================== 2. MediaPipe 初始化 ====================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# ==================== 3. gRPC 服务 ====================
class GestureService(gesture_pb2_grpc.GestureServiceServicer):
    def DetectHand(self, request, context):
        try:
            # 解码图像
            nparr = np.frombuffer(request.image, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                print("警告: 图像解码失败")
                response = gesture_pb2.DetectionResponse()
                response.landmarks.extend([0.0] * 63)
                return response

            # 推理
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            response = gesture_pb2.DetectionResponse()

            if results.multi_hand_landmarks:
                print(f"检测到手！关键点数量: {len(results.multi_hand_landmarks[0].landmark)}")
                landmarks = []
                for lm in results.multi_hand_landmarks[0].landmark:
                    # 关键修复：强制转为 float
                    landmarks.extend([float(lm.x), float(lm.y), float(lm.z)])
                response.landmarks.extend(landmarks)
                print(f"发送 landmarks: {landmarks[:6]}...")  # 打印前6个
            else:
                print("未检测到手，返回全0")
                response.landmarks.extend([0.0] * 63)

            return response

        except Exception as e:
            print(f"推理异常: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("推理失败")
            response = gesture_pb2.DetectionResponse()
            response.landmarks.extend([0.0] * 63)
            return response

# ==================== 4. 启动服务器 ====================
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
gesture_pb2_grpc.add_GestureServiceServicer_to_server(GestureService(), server)
server.add_insecure_port('[::]:50051')
server.start()
print("gRPC 服务器启动成功")

# ==================== 5. Pinggy 隧道 ====================
print("启动 Pinggy 隧道...")
process = subprocess.Popen([
    "ssh", "-p", "443", "-R0:localhost:50051", "tcp@a.pinggy.io",
    "-o", "StrictHostKeyChecking=no"
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

for line in process.stdout:
    line = line.strip()
    if line and "tcp://" in line:
        import re
        m = re.search(r'tcp://([a-z0-9\.-]+:\d+)', line)
        if m:
            addr = m.group(1)
            print(f"\n云端地址: {addr}")
            print(f"复制到 client.py: CLOUD_ADDR = '{addr}'")
            print("客户端可以连接了！")

server.wait_for_termination()