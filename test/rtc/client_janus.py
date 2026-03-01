# client.py
import asyncio
import ssl
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import cv2
import sys
from aiortc import RTCConfiguration, RTCIceServer

class WebcamStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
    
        if not self.cap.isOpened():
            print("❌ 카메라를 찾을 수 없습니다. 프로그램을 종료합니다.")
            sys.exit(1)  # 비정상 종료

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret:
            return None
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def run():
    ice_servers = [
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ]
    config = RTCConfiguration(ice_servers)

    pc = RTCPeerConnection(configuration=config)

    # 수신 영상 프레임 출력용 큐
    frame_queue = asyncio.Queue()

    @pc.on("track")
    def on_track(track):
        print("✅ 수신 트랙 도착:", track.kind)

        if track.kind == "video":
            async def display_video():
                while True:
                    frame = await track.recv()
                    img = frame.to_ndarray(format="bgr24")
                    cv2.imshow("Received Video", img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cv2.destroyAllWindows()
            
            asyncio.ensure_future(display_video())

    # 송신 트랙 등록
    pc.addTrack(WebcamStreamTrack())

    #offer 생성
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    #시그널링
    ssl_context = ssl.create_default_context(cafile="certs/ca.crt")
    async with aiohttp.ClientSession() as session:
        async with session.post("https://70.12.246.26:8443/offer", json={
            "sdp": pc.localDescription.sdp
        }, ssl=ssl_context) as resp:
            if resp.status != 200:
                print("서버 에러 발생:", await resp.text())
                return

            answer = await resp.json()


    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    print("📡 연결 완료, 영상 수신 중...")

    await asyncio.sleep(30)
    await pc.close()

asyncio.run(run())
