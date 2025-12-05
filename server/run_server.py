# run_server.py - 局域网高性能服务端
import grpc
from concurrent import futures
import cv2
import numpy as np
import mediapipe as mp
import gesture_pb2
import gesture_pb2_grpc
import socket

# ================= 配置区 =================
PORT = '50051'
MAX_WORKERS = 10
# ==========================================

# 预加载 MediaPipe 模型，避免每次请求都重新加载（大幅提升速度）
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


def get_host_ip():
    """获取本机局域网 IP，方便你查看"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class GestureService(gesture_pb2_grpc.GestureServiceServicer):
    def DetectHand(self, request, context):
        response = gesture_pb2.DetectionResponse()
        try:
            # 1. 解码图片 (从字节流变回图片)
            nparr = np.frombuffer(request.image, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return response

            # 2. 推理 (核心计算任务)
            # MediaPipe 需要 RGB 格式
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            # 3. 封装结果
            if results.multi_hand_landmarks:
                # 将 21 个点的 x,y,z 展平成一个列表
                landmarks = []
                for lm in results.multi_hand_landmarks[0].landmark:
                    landmarks.extend([lm.x, lm.y, lm.z])
                response.landmarks.extend(landmarks)

        except Exception as e:
            print(f"Server Error: {e}")

        return response


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    gesture_pb2_grpc.add_GestureServiceServicer_to_server(GestureService(), server)

    # 监听所有网卡接口
    server.add_insecure_port(f'[::]:{PORT}')

    local_ip = get_host_ip()
    print("=" * 40)
    print(f" gRPC 服务器已启动")
    print(f" 监听端口: {PORT}")
    print(f" 局域网 IP: {local_ip}  <-- 请把这个 IP 填入 client 代码")
    print("=" * 40)

    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()