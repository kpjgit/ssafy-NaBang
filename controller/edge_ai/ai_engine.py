import cv2
import mediapipe as mp
import numpy as np

# === 유틸 함수 ===
# 길이 계산
def distance(pt1, pt2, shape):
    h, w = shape
    x1, y1 = int(pt1[0] * w), int(pt1[1] * h)
    x2, y2 = int(pt2[0] * w), int(pt2[1] * h)
    return np.linalg.norm([x2 - x1, y2 - y1])

# 랜드마크 기반으로 면적 계산
def calculate_area(landmarks, indices, shape):
    h, w = shape
    points = [(int(landmarks[i][0] * w), int(landmarks[i][1] * h)) for i in indices]
    return cv2.contourArea(np.array(points))

# 1~10으로 점수 정규화
def normalize(value, min_val, max_val, inverse=False):
    norm = np.clip((value - min_val) / (max_val - min_val + 1e-6), 0, 1)
    score = int(norm * 9 + 1)  # 1 ~ 10
    return 10 - score + 1 if inverse else score

# face mesh가 정규화된 값을 내놓지만 인식된 얼굴 경계를 기준으로 정규화 된것이 아니라 전체 이미지를 기준으로 0~1 사이의 값
# 따라서 눈동자의 움직임은 전체 이미지에서 매우 한정적인 값이므로 얼굴 경계를 기준으로 다시 정규화 필요
def get_face_bbox(landmarks):
    xs = [pt[0] for pt in landmarks]
    ys = [pt[1] for pt in landmarks]
    return min(xs), min(ys), max(xs), max(ys)

# 얼굴 경계를 기준으로 찾은 박스를 기준으로 정규화된 눈동자 위치
def compute_iris_centering_normalized(landmarks, eye_indices, iris_idx, face_bbox):
    x_min, y_min, x_max, y_max = face_bbox
    box_w = x_max - x_min
    box_h = y_max - y_min

    # 눈 중심 계산
    eye_cx = (landmarks[eye_indices["inner"]][0] + landmarks[eye_indices["outer"]][0]) / 2
    eye_cy = (landmarks[eye_indices["top"]][1] + landmarks[eye_indices["bottom"]][1]) / 2

    # 동공 위치
    iris = landmarks[iris_idx]

    # 얼굴 기준 상대 좌표로 정규화
    rel_cx = (eye_cx - x_min) / (box_w + 1e-6)
    rel_cy = (eye_cy - y_min) / (box_h + 1e-6)
    rel_iris_x = (iris[0] - x_min) / (box_w + 1e-6)
    rel_iris_y = (iris[1] - y_min) / (box_h + 1e-6)

    # 중심으로부터의 거리
    dx = abs(rel_iris_x - rel_cx)
    dy = abs(rel_iris_y - rel_cy)

    # 중심에 가까울수록 점수 높음 (상한은 0.05 ~ 0.1 정도로 조정 가능)
    return normalize((dx + dy) / 2, 0.0, 0.025, inverse=True)

# === 주요 특징 추출 ===
def extract_features(landmarks, image_shape):
    features = {}

    # 눈 영역 정의
    # 눈의 경우 사람마다 크기 차이가 있을 수 있으므로 측정된 눈의 크기와 비교할 지표를 찾아야함
    # 눈두덩이(eye socket)이가 보편적으로 개개인의 원래 눈 크기를 대표한다 판단하여 눈두덩이와 눈의 비율로 계산
    left_eye_outline = [33, 133, 159, 158, 157, 173, 144, 145, 153, 154, 155, 35, 124, 46, 121, 188]
    right_eye_outline = [263, 362, 386, 385, 384, 398, 373, 374, 380, 381, 382, 265, 294, 276, 300, 417]
    left_eye_inner = [159, 158, 157, 173, 144, 145]
    right_eye_inner = [386, 385, 384, 398, 373, 374]

    left_outer_area = calculate_area(landmarks, left_eye_outline, image_shape)
    right_outer_area = calculate_area(landmarks, right_eye_outline, image_shape)
    left_inner_area = calculate_area(landmarks, left_eye_inner, image_shape)
    right_inner_area = calculate_area(landmarks, right_eye_inner, image_shape)

    left_ratio = left_inner_area / (left_outer_area + 1e-6)
    right_ratio = right_inner_area / (right_outer_area + 1e-6)

    features["Left Eye Open"] = normalize(left_ratio, 0.1, 0.45)
    features["Right Eye Open"] = normalize(right_ratio, 0.1, 0.45)

    # 입 닫힘 정도
    # 좌우 입꼬리를 기준값으로 비교
    # 좌우 입꼬리에 비례해 입이 벌어진 크기를 측정
    mouth_length = distance(landmarks[61], landmarks[291], image_shape)
    mouth_opening = distance(landmarks[13], landmarks[14], image_shape)
    mouth_ratio = mouth_opening / (mouth_length + 1e-6)
    features["Mouth Closed"] = normalize(mouth_ratio, 0.15, 0.6, inverse=True)

    # 고개 좌우 회전
    nose_tip = landmarks[1]
    horizontal_angle = abs(nose_tip[0] - 0.5)
    features["Head Rotation (LR)"] = normalize(horizontal_angle, 0.0, 0.25, inverse=True)

    # 고개 상하 회전
    # 현재 사용 안함, 캠의 각도를 고려할 수 있는 방법을 찾지 않는 이상 사용하지 말것
    z_diff = landmarks[10][2] - landmarks[152][2]  # 이마 - 턱 깊이차
    features["Head Tilt (Up/Down)"] = normalize(z_diff, -0.05, 0.05)

    # 얼굴 bounding box
    face_bbox = get_face_bbox(landmarks)

    # 동공 중심 정렬 (얼굴 박스 기준)
    left_eye_indices = {"inner": 133, "outer": 33, "top": 159, "bottom": 145}
    right_eye_indices = {"inner": 362, "outer": 263, "top": 386, "bottom": 374}
    iris_l_score = compute_iris_centering_normalized(landmarks, left_eye_indices, 468, face_bbox)
    iris_r_score = compute_iris_centering_normalized(landmarks, right_eye_indices, 473, face_bbox)
    features["Iris Centering"] = int((iris_l_score + iris_r_score) / 2)

    return features

# === AI 엔진 클래스 ===
class AIEngine:
    # 생성자에 face mesh 초기화 과정 포함됨
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.drawing = mp.solutions.drawing_utils

    # 랜드마크 추출 함수, 단독으로 호출 가능, 직접 호출하는 경우 디버깅 용도
    def process_frame(self, frame, draw=False):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if results.multi_face_landmarks:
            landmarks_obj = results.multi_face_landmarks[0]
            landmarks = [(pt.x, pt.y, pt.z) for pt in landmarks_obj.landmark]
            image_shape = frame.shape[:2]
            features = extract_features(landmarks, image_shape)

            if draw:
                self.drawing.draw_landmarks(
                    image=frame,
                    landmark_list=landmarks_obj,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.drawing.DrawingSpec(color=(0, 255, 0), thickness=1)
                )
            return features, frame
        return None, frame

    # 프레임의 랜드마크 기반으로 스코어 리턴
    def predict_current_frame(self, frame):
        features, _ = self.process_frame(frame)
        if features is None:
            features = {}
            features["Left Eye Open"] = 1
            features["Right Eye Open"] = 1
            features["Mouth Closed"] = 1
            features["Head Rotation (LR)"] = 1
            features["Head Tilt (Up/Down)"] = 1
            features["Iris Centering"] = 1

        w_eye = 0.35
        w_mouth = 0.175
        w_head_rot = 0.275
        w_iris = 0.20

        eye_score = (features["Left Eye Open"] + features["Right Eye Open"]) / 2.0
        mouth_score = features["Mouth Closed"]
        head_score_rot = features["Head Rotation (LR)"]
        head_score_tilt = features["Head Tilt (Up/Down)"]
        iris_score = features["Iris Centering"]

        if eye_score < 3.0:
            iris_score = -2

        if head_score_rot < 5.0:
            head_score_rot -= 7.5

        if mouth_score < 3.0:
            mouth_score -= 6.0

        engagement_score = (
            w_eye * eye_score +
            w_mouth * mouth_score +
            w_head_rot * head_score_rot +
            w_iris * iris_score
        )

        return engagement_score
    
    # 직접 feature 리턴, 좀 더 장기적인 evaluate를 위해 사용
    def get_featrues(self, frame):
        features, _ = self.process_frame(frame)
        if features is None:
            features = {}
            features["Left Eye Open"] = 1
            features["Right Eye Open"] = 1
            features["Mouth Closed"] = 1
            features["Head Rotation (LR)"] = 1
            features["Head Tilt (Up/Down)"] = 1
            features["Iris Centering"] = 1
        
        return features
    

if __name__ == '__main__':
    capture = cv2.VideoCapture(0)
    ai = AIEngine()

    cam_check = 0
    while True:
        ret, frame = capture.read()
        if not ret:
            cam_check += 1
            if cam_check > 100:
                break
            continue
        else :
            cam_check = 0

        features = ai.get_featrues(frame)
        print(features)
