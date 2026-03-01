import paho.mqtt.client as mqtt
import ssl
import json

# === MQTTHandler 클래스 ===
class MQTTHandler:
    # 생성자, mqtt 초기화 포함, username은 device id이므로 반드시 환경변수로부터 controller.py에서 입력받아야함
    def __init__(self, username, password, on_command_callback=None):
        self.username = username
        self.password = password
        self.client = mqtt.Client()

        # 인증 정보
        self.client.username_pw_set(username, password)

        # TLS 설정
        self.client.tls_set(
            ca_certs="certs/ca.crt",  # 인증서 경로 필요시 인자로 전달 가능
            certfile=None,
            keyfile=None,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
        self.client.tls_insecure_set(False)

        # 토픽 구성
        self.pub_topic_deci = f"mqtt/{username}/decision"
        self.pub_topic_data = f"mqtt/{username}/data"
        self.sub_topic = f"mqtt/{username}/command"

        # 연결 및 메시지 콜백 등록
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # 외부에서 메시지를 처리할 콜백 함수 (예: controller에서 등록)
        self.on_command_callback = on_command_callback

        # 브로커 연결 및 루프 시작
        # ip 주소는 서버 ip 확정시 변경 필요
        self.client.connect("70.12.246.26", 8883, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[✔] Connected with result code {rc}")
        client.subscribe(self.sub_topic)

    # 메시지 수신 시에 등록된 콜백 함수로 전달
    def _on_message(self, client, userdata, msg):
        print(f"[📩] Received message: {msg.topic} -> {msg.payload.decode()}")
        if self.on_command_callback:
            self.on_command_callback(msg.topic, msg.payload.decode())

    # === 외부에서 호출할 퍼블리시 함수 ===
    def publish_data(self, payload: dict):
        """센싱 데이터 송신: 5초 주기 또는 on_demand"""
        self._publish(self.pub_topic_data, payload)

    def publish_decision(self, payload: dict):
        """집중도 등 판단 기반 제어 결과 송신"""
        self._publish(self.pub_topic_deci, payload)

    def _publish(self, topic: str, payload: dict):
        try:
            message = json.dumps(payload)
            self.client.publish(topic, message)
            print(f"[🚀] Published to {topic}: {message}")
        except Exception as e:
            print(f"[❌] Publish failed: {e}")
