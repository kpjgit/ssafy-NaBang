# server.py
from flask import Flask, request, jsonify
import requests
import time

JANUS_URL = "http://localhost:8088/janus"

app = Flask(__name__)

@app.route("/offer", methods=["POST"])
def handle_offer():
    client_offer = request.json["sdp"]

    # 1. Janus 세션 생성
    janus_resp = requests.post(JANUS_URL, json={"janus": "create", "transaction": "txn1"}).json()
    session_id = janus_resp["data"]["id"]

    # 2. 플러그인 attach
    attach_resp = requests.post(f"{JANUS_URL}/{session_id}", json={
        "janus": "attach",
        "plugin": "janus.plugin.echotest",
        "transaction": "txn2"
    }).json()
    handle_id = attach_resp["data"]["id"]

    # 3. Janus에 offer 전달
    requests.post(f"{JANUS_URL}/{session_id}/{handle_id}", json={
        "janus": "message",
        "body": {"video": True, "audio": False},
        "jsep": {"type": "offer", "sdp": client_offer},
        "transaction": "txn3"
    })

    # 4. Janus 이벤트 응답 polling
    for _ in range(10):
        event_resp = requests.get(f"{JANUS_URL}/{session_id}?rid={int(time.time()*1000)}&maxev=1").json()

        # 디버깅 출력
        print(">>> Janus Event Poll Response:", event_resp)

        if event_resp["janus"] == "event" and "jsep" in event_resp:
            return jsonify(event_resp["jsep"])

        time.sleep(0.5)

    # 실패 시
    return jsonify({"error": "Timeout waiting for Janus event with jsep"}), 504


if __name__ == "__main__":
    app.run(host="0.0.0.0", ssl_context=("certs/server.crt", "certs/server.key"), port=8443)
