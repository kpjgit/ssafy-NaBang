import paho.mqtt.client as mqtt
import ssl
import time
import json

# 설정
HOST_ADDRESS = "70.12.246.26" # 127.0.0.1는 NIC를 거치지 않음
HOST_PORT = 8883

CLIENT_ID = "device123"
USERNAME = "device123"
PASSWORD = "secret123"

PUB_TOPIC = "test/yay"
SUB_TOPIC = "test/yay"

# 콜백 함수 정의
def on_connect(client, userdata, flags, rc):
    print(f"[✔] Connected with result code {rc}")
    client.subscribe(SUB_TOPIC)
    client.publish(PUB_TOPIC, payload="online", qos=1)

def on_message(client, userdata, msg):
    print(f"[📩] Received message: {msg.topic} -> {msg.payload.decode()}")
    # 여기서 받은 명령(msg.payload)에 따라 장치 동작 수행

# MQTT 클라이언트 초기화
client = mqtt.Client()
#client.username_pw_set(USERNAME, PASSWORD)

# TLS 설정 (MQTT over TLS)
client.tls_set(
    ca_certs="certs/ca.crt",  # 서버 인증서 서명한 루트 CA
    certfile=None,
    keyfile=None,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(False)

# 콜백 등록
client.on_connect = on_connect
client.on_message = on_message

# 브로커에 연결
client.connect(HOST_ADDRESS, HOST_PORT, keepalive=60)

# 메시지 처리 루프 시작
client.loop_start()

try:
    count = 0
    while True:
        message= json.dumps({"deviceId":1234567, "body":f"Hello MQTT! {count}", "sensor":{"temperature":32, "humidity":50}})
        client.publish(PUB_TOPIC, message)
        print(f"[🚀] Published: json message")
        count += 1
        time.sleep(5)
except KeyboardInterrupt:
    print("🔚 종료 요청됨")
    client.loop_stop()
    client.disconnect()