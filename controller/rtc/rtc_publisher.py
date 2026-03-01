import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import aiohttp
import ssl
import threading

class WebcamVideoStreamTrack(VideoStreamTrack):
    def __init__(self, capture):
        super().__init__()
        self.capture = capture
        self.running = True

    async def recv(self):
        if not self.running:
            return None

        pts, time_base = await self.next_timestamp()
        ret, frame = self.capture.read()
        if not ret:
            return None
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

    def stop(self):
        self.running = False

class RTCPublisher:
    # capture의 경우 cv2의 비디오 캡쳐인데 제어를 위한 로직 없이 단순히 영상 전송이므로
    # 일정 프레임이 아니라 capture을 그대로 사용해도 될듯, 레이스 컨디션 문제 없어보임, 쓰기 작업 없음
    # 주소는 서버 ip가 확정될 경우 수정 바람
    def __init__(self, capture, signaling_url="https://localhost:8443/offer"):
        self.capture = capture              # 외부에서 받은 capture
        self.signaling_url = signaling_url
        self.pc = None
        self.track = None
        self.loop = None
        self.thread = None

    async def _publish(self):
        self.pc = RTCPeerConnection()
        self.track = WebcamVideoStreamTrack(self.capture)
        self.pc.addTrack(self.track)

        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with aiohttp.ClientSession() as session:
            async with session.post(self.signaling_url, json={
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp
            }, ssl=ssl_context) as resp:
                answer = await resp.json()

        await self.pc.setRemoteDescription(RTCSessionDescription(
            sdp=answer["sdp"],
            type=answer["type"]
        ))

    def start(self):
        def runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._publish())
            self.loop.run_forever()

        self.thread = threading.Thread(target=runner)
        self.thread.start()
        print("[🎥] RTC publishing started.")

    def stop(self):
        if self.track:
            self.track.stop()
        if self.pc:
            asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join()
        print("[🛑] RTC publishing stopped.")
