import paho.mqtt.client as mqtt
import ssl
import json

# === MQTTHandler 클래스 ===
class MQTTHandler:
    # 생성자, mqtt 초기화 포함, username은 device id이므로 반드시 환경변수로부터 controller.py에서 입력받아야함
    def __init__(self, username, password, on_command_callback=None, tls = True):
        self.username = username
        self.password = password
        self.status = None
        self.client = mqtt.Client()

        # 인증 정보
        self.client.username_pw_set(username, password)

        # TLS 설정
        if tls:
            self.client.tls_set(
                ca_certs="certs/ca.crt",  # 인증서 경로 필요시 인자로 전달 가능
                certfile=None,
                keyfile=None,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            self.client.tls_insecure_set(False)
            port = 8883
        else:    
            port = 1883

        # 토픽 구성
        self.pub_topic_deci = f"mqtt/{username}/decision"
        self.pub_topic_data = f"mqtt/{username}/data"
        self.sub_topic = f"mqtt/{username}/command"

        # 연결 및 메시지 콜백 등록
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # 외부에서 메시지를 처리할 콜백 함수, controller에서 등록
        self.on_command_callback = on_command_callback

        # 브로커 연결 및 루프 시작
        # ip 주소는 서버 ip 확정시 변경 필요
        self.client.connect("52.78.232.30", port, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        self.status = rc
        print(f"[✔] Connected with result code {rc}")
        client.subscribe(self.sub_topic)

    # 메시지 수신 시에 등록된 콜백 함수로 전달
    def _on_message(self, client, userdata, msg):
        print(f"[📩] Received message: {msg.topic} -> {msg.payload.decode()}")
        if self.on_command_callback:
            self.on_command_callback(msg.topic, msg.payload.decode())

    # === 외부에서 호출할 퍼블리시 함수 ==
    # 5초 주기로 데이터 전달, 집중도, 센서값, 목표한 시간, 경과 시간, 유효 시간 세트로 보내기
    def publish_data(self, payload: dict):
        self._publish(self.pub_topic_data, payload)

    # 학습 시작, IoT 제어 등 이벤트를 서버에 전달
    def publish_decision(self, payload: dict):
        self._publish(self.pub_topic_deci, payload)

    def _publish(self, topic: str, payload: dict):
        try:
            message = json.dumps(payload)
            self.client.publish(topic, message)
            print(f"[🚀] Published to {topic}: {message}")
        except Exception as e:
            print(f"[❌] Publish failed: {e}")
