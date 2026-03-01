from edge_ai.ai_engine import AIEngine
from mqtt.mqtt_client import MQTTHandler
from evaluate.evaluator import Evaluator
from sensor.sensor import SensorReader
import time
import cv2
import os
from adafruit_servokit import ServoKit
import busio
import board

# 전역으로 한 번만 초기화 (필요 최소)
_i2c = busio.I2C(board.SCL, board.SDA)
_kit = ServoKit(channels=16, i2c=_i2c, address=0x60)

_kit.servo[0].actuation_range = 180
_kit.servo[0].set_pulse_width_range(1000, 2000)  # 필요하면 600~2400으로 확장

def move_servo(angle: float, channel: int = 0) -> None:
    """
    지정한 채널의 서보를 angle(도)로 즉시 이동시킨다.
    - angle: 0~180 범위를 권장(초과값은 클램프)
    - channel: PCA9685 서보 채널 번호 (0~15)
    """
    # 안전한 범위로 클램프
    if angle is None:
        raise ValueError("angle 값이 필요합니다.")
    angle = max(0, min(180, float(angle)))

    # 채널 범위 체크
    if not (0 <= channel <= 15):
        raise ValueError("channel은 0~15 사이여야 합니다.")

    _kit.servo[channel].angle = angle

# 구현 편의상 stop 호출 이후에 다시 접속할 경우 IoTController를 새로 할당받도록 한다
# qt에서 해당 부분 반영 바람
# 시간 되면 고침
# callback_from_ui에 콜백 등록 controller에서 집중도 하락시에 이벤트를 전달하기 위해 사용
class IoTController:
    def __init__(self, callback_from_ui=None):
        self.capture = cv2.VideoCapture(0)
        self.ai = AIEngine()
        self.eval = Evaluator()
        self.sensor = SensorReader(port='/dev/ttyUSB0')
        self.callback_ui = callback_from_ui
        
        self.running = False
        self.ready = False

        move_servo(180)
    
    # qt에서 호출 입력된 비밀번호와 함께 호출
    # qt에서는 만드시 init 이후에 set_mqtt를 호출하고 그 전까지는 main_loop가 실행되지 않도록 주의
    # 필요한 멤버 변수들 초기화 되지 않음
    def set_mqtt(self, passwd):
        # 환경변수로부터 디바이스 id 불러옴
        self.username = os.getenv("DEVICE_ID", "default_device")
        self.passwd = passwd
        self.mqtt = MQTTHandler(self.username, self.passwd, tls = False)
        # 실제 서비스 시에 tls는 무조건 true
        
        # mqtt 서버에서 기다림 동기적
        # 연결 완료될 때까지 대기 (최대 5초)
        for _ in range(50):  # 0.1s * 50 = 5초
            if self.mqtt.status is not None:
                break
            time.sleep(0.1)

        rc = self.mqtt.status
        if rc is None:
            return "MQTT connection timeout"
        elif rc == 4:
            return "Bad username or password"
        elif rc != 0:
            return "Connection failed"
        
        self.ready = True

    # qt에서 목표 시간 입력받도록 설정
    # target_time이 지나고 valid_time이 target_time의 90% 이상일 경우 종료
    # target_time은 실수인 초 단위로 입력, ui에서 입력과 출력 때 주의
    def main_loop(self, target_time):
        if self.ready != True:
            return "error"

        # elapsed_time은 경과한 시간
        self.elapsed_time = 0
        # valid_time은 집중한 시간
        self.valid_time = 0
        self.global_last_time = time.time()
        self.last_mqtt_time = time.time()
        self.last_smartthings_time = time.time()

        self.running = True
        cam_check = 0
        # 스터디 시작 메시지
        # decision이 on일 경우(시작할 경우)에는 target 시간, 그 외의 경우에는 -1
        self.mqtt.publish_decision({"device_id": self.username, "decision": "on", "target_time": int(target_time / 60)})
        move_servo(0)
        while self.running:
            ret, frame = self.capture.read()
            if not ret:
                cam_check += 1
                if cam_check > 100:
                    self.stop()
                    return "failed get image"
                continue
            else :
                cam_check = 0

            # cv2에서의 read는 스레드 세이프하지 않아 현재 루프의 프레임을 복사해 전달
            frame_copy = frame.copy()
            sensor_value = self.sensor.get_average()

            # AI 추론
            engagement_score = self.ai.predict_current_frame(frame_copy)
            features = self.ai.get_featrues(frame_copy)

            # 상태 업데이트
            self.eval.update(engagement_score, features)

            # MQTT 전송 조건 확인
            if time.time() - self.last_mqtt_time > 5.0:
                self.last_mqtt_time = time.time()
                self.mqtt.publish_data({
                    "device_id": self.username,
                    "concentration": formatted_float(self.eval.get_status()["engagement_average"]),
                    "sensor": {"tmp": f"{sensor_value['TEMP']:.2f}",
                               "humidity": f"{sensor_value['HUMID']:.2f}",
                               "illuminance": f"{sensor_value['LIGHT']:.2f}",
                               "co2": f"{sensor_value['CO2']:.2f}"},
                    "pure_study_time": int(self.valid_time / 60)}) #분 단위 정수
            
            # 5분마다 환경 제어 결정
            if time.time() - self.last_smartthings_time > 300.0:
                self.last_smartthings_time = time.time()

                context = self.eval.get_status()
                # 평균 집중도가 6.0 미만, 하품 혹은 눈깜빡임으로 감지된 프레임이 기준치 이상일 경우 콜백
                if context["engagement_long_average"] < 6.0 or context["yawn"] > self.eval.yawn_per_3min or context["eye_closed"] > self.eval.blink_per_3min:
                    # ui 구현시 중요, 콜백의 인자로 'CO2', 'NOISE', 'LIGHT', 'TEMP', 'HUMID'와 같이 딕셔너리 전달
                    self.callback_ui(sensor_value)
                    
                    # 서버와 웹 프론트에 집중도 하락을 현재 주변 환경 제어중이라는 메시지 전송, 5분마다 한번 전송하므로 프론트 입장에서는 2~3초 정도 띄우고 다시 돌아가게 설계할것
                    self.mqtt.publish_decision({"device_id": self.username, "decision": "control", "target_time": -1})
                    print("Low engagement!")

            time_gap = time.time() - self.global_last_time
            self.global_last_time = time.time()
            self.elapsed_time += time_gap
            # 집중도 6 이상일 경우 valid_time에 가산
            if engagement_score >= 6.0:
                self.valid_time += time_gap
            
            # 정지조건
            if self.elapsed_time >= target_time:
                if self.valid_time >= target_time * 0.9:
                    self.stop(legit=True)

    def stop(self, legit=False):
        #stop이 running인 상황에서 끝나면 메시지를 보낸다
        if self.running:
            if legit:
                self.mqtt.publish_decision({"device_id": self.username, "decision": "off", "target_time": -1})
            else:
                # 현재 프론트에서 강제 중단하는 것에 대한 구분을 하지 말라고 해서 동일하게 off로 해둠
                # self.mqtt.publish_decision({"device_id": self.username, "decision": "stop"})
                self.mqtt.publish_decision({"device_id": self.username, "decision": "off", "target_time": -1})
        
        move_servo(180)

        self.running = False
        self.capture.release()
        self.mqtt.client.loop_stop()
        self.mqtt.client.disconnect()
        self.sensor.stop()

    def mqtt_callback(self, message):
        # 메시지 파스, rtc 빠져서 현재 쓸데 없음
        if message == "start_something":
            pass
        elif message == "stop_something":
            pass

@staticmethod
def formatted_float(x):
    if x is None or x <= 0:
        return "0.00"
    return f"{x:.2f}"
        
if __name__ == "__main__":
    controller = IoTController()

    controller.set_mqtt("ssafy1357")

    controller.main_loop(30)


#메모
#ai
#mqtt
#evaluate
#sensor
#smartthings