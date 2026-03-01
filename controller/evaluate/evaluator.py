from collections import deque

# 프레임 별 판단이 아닌 좀 더 장기적인 판단을 위한 클래스
class Evaluator:
    # 생성자
    def __init__(self, window_sec: float = 5.0, fps: int = 30):
        self.window_size = int(window_sec * fps)          # 5초 기준 (단기)
        self.long_window_size = self.window_size * 36     # 3분 기준 (장기)

        # 유틸리티 상수
        # 하품은 평균적으로 5초로 보고됨
        self.yawn_timer = 5 * fps
        self.yawn_per_3min = 3 * self.yawn_timer
        # 눈 깜빡임은 평균 0.25초로 보고됨
        self.blink_timer = fps / 4
        self.blink_per_3min = 60 * self.blink_timer

        self.eye_window = deque(maxlen=self.long_window_size)
        self.mouth_window = deque(maxlen=self.long_window_size) # 3분 슬라이딩 윈도우
        self.engagement_window = deque(maxlen=self.window_size)
        self.engagement_long_window = deque(maxlen=self.long_window_size)

        # 상태 누적용
        self.eye_closure_count = 0
        self.yawn_count = 0
        self.engagement_sum = 0
        self.engagement_sum_long = 0

    def update(self, engagement_score, features):
        eye = (features["Left Eye Open"] + features["Right Eye Open"]) / 2.0
        mouth = features["Mouth Closed"]

        # --- 단기 윈도우(5초) 관리 ---
        if len(self.engagement_window) == self.window_size:
            self.engagement_sum -= self.engagement_window[0]
        self.engagement_sum += engagement_score
        self.engagement_window.append(engagement_score)

        # --- 장기 윈도우(3분) 관리 ---
        if len(self.engagement_long_window) == self.long_window_size:
            self.engagement_sum_long -= self.engagement_long_window[0]
        self.engagement_sum_long += engagement_score
        self.engagement_long_window.append(engagement_score)

        if len(self.eye_window) == self.long_window_size:
            if self.eye_window[0] < 3.0:
                self.eye_closure_count -= 1
            if self.mouth_window[0] < 3.0:
                self.yawn_count -= 1

        if eye < 3.0:
            self.eye_closure_count += 1
        if mouth < 3.0:
            self.yawn_count += 1

        self.eye_window.append(eye)
        self.mouth_window.append(mouth)

    def get_status(self):
        short_avg = self.engagement_sum / float(len(self.engagement_window)) if self.engagement_window else 0.0
        long_avg = self.engagement_sum_long / float(len(self.engagement_long_window)) if self.engagement_long_window else 0.0
        return {
            "eye_closed": self.eye_closure_count,
            "yawn": self.yawn_count,
            "engagement_average": short_avg,           # 5초 평균
            "engagement_long_average": long_avg        # 3분 평균 ✅
        }