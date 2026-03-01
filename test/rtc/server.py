# server.py
import asyncio
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRecorder

pcs = set()

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    recorder = MediaRecorder("output.mp4")  # 저장할 파일명

    @pc.on("track")
    def on_track(track):
        print("Receiving %s track" % track.kind)
        if track.kind == "video":
            recorder.addTrack(track)
            asyncio.ensure_future(recorder.start())

        @track.on("ended")
        async def on_ended():
            print("Track ended")
            await recorder.stop()

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

app = web.Application()
app.router.add_post("/offer", offer)

if __name__ == "__main__":
    web.run_app(app, port=8080)
    #실 사용시 여기에 ssl 적용 필요, webRTC는 암호화가 적용되지만 키(핑거프린트) 교환 중에 탈취 가능
