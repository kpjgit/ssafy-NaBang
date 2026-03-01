import serial
import threading
import time
from collections import deque, defaultdict
from typing import Dict, Optional

class SensorReader:
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, timeout: int = 1, window_size: int = 10):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.window_size = window_size

        # 센서 이름과 순서 매핑
        self.sensor_keys = ['CO2', 'NOISE', 'LIGHT', 'TEMP', 'HUMID']

        # 센서별 deque 저장소
        self.sensor_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))

        # 스레드 동기화용 Lock
        self.lock = threading.Lock()

        # 시리얼 객체 및 수신 스레드
        self.running = True
        self.thread = threading.Thread(target=self._serial_loop, daemon=True)
        self.thread.start()

    def _serial_loop(self):
        try:
            with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as ser:
                print(f"[INFO] ESP32에 연결됨 - 포트: {self.port}, 속도: {self.baudrate}")
                while self.running:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        self._parse_and_store(line)
                    else:
                        time.sleep(0.05)
        except serial.SerialException as e:
            print(f"[ERROR] 시리얼 포트 연결 실패: {e}")
            self.running = False

    def _parse_and_store(self, line: str):
        try:
            values = line.split(',')
            if len(values) != len(self.sensor_keys):
                print(f"[WARN] 센서 데이터 수 mismatch: {line}")
                return

            with self.lock:
                for i, raw_value in enumerate(values):
                    try:
                        value = float(raw_value.strip())
                        key = self.sensor_keys[i]
                        self.sensor_data[key].append(value)
                    except ValueError:
                        print(f"[WARN] 파싱 실패: '{raw_value}'")
        except Exception as e:
            print(f"[WARN] 파싱 오류: {line} ({e})")

    def get_average(self) -> Dict[str, Optional[float]]:
        with self.lock:
            averages = {}
            for key, values in self.sensor_data.items():
                if values:
                    averages[key] = sum(values) / len(values)
                else:
                    averages[key] = None
            return averages

    def stop(self):
        self.running = False
        self.thread.join()


# 테스트용 예시
if __name__ == '__main__':
    reader = SensorReader(port='COM4')  # 윈도우 포트 명시
    try:
        while True:
            print(reader.get_average())
            time.sleep(1)
    except KeyboardInterrupt:
        reader.stop()
