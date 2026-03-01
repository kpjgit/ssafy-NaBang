import paho.mqtt.client as mqtt
import time
import json

HOST_ADDRESS = "70.12.246.26" # 127.0.0.1는 NIC를 거치지 않음
HOST_PORT = 1883

PUB_TOPIC = "test/yay"
SUB_TOPIC = "test/yay"

# 연결되었을 때 호출되는 콜백
def on_connect(client, userdata, flags, rc):
    print(f"[✔] Connected with result code {rc}")
    client.subscribe(SUB_TOPIC)

# 메시지 수신 콜백
def on_message(client, userdata, msg):
    json_format = json.loads(msg.payload.decode())
    print(f"[📩] Received: {msg.topic}")
    print(f"-> {json_format}")

# MQTT 클라이언트 생성
client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

# 브로커 연결
client.connect(HOST_ADDRESS, HOST_PORT, keepalive=60)

# 별도 스레드에서 루프 시작 (비동기)
client.loop_start()

# 주기적으로 메시지 발행
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