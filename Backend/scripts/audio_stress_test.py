import asyncio
import aiohttp
import json
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YTcyZjAzYzU4OGI5MDI2NjMwZWE2MmEiLCJyb2xlIjoib3JnX21lbWJlciIsIm9yZ19pZCI6IjZhNzJmMDNiNTg4YjkwMjY2MzBlYTYyOSIsImV4cCI6MTc4NjAwMzkwMH0.LSj7k3P9at2gdb41IO41kktCK7OTTgXaf3BFqj6xTkI"
ORG_ID = "6a72f03b588b9026630ea629"

CONCURRENCY = 10
AUDIO_FILE = "Backend/scripts/test_audio/5s_menu_query.wav"

async def run_client(session_idx: int):
    async with aiohttp.ClientSession() as client:
        # Create session
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        payload = {
            "organization_id": ORG_ID,
            "conversation_id": f"audio_stress_{session_idx}",
            "session_type": "push_to_talk",
            "agent_id": None
        }
        async with client.post(f"{BASE_URL}/voice-sessions/", json=payload, headers=headers) as resp:
            data = await resp.json()
            session_id = data.get("session_id")
            if not session_id: return

        print(f"[{session_idx}] Spawned {session_id}")
        
        pc = RTCPeerConnection()
        player = MediaPlayer(AUDIO_FILE)
        pc.addTrack(player.audio)
        
        @pc.on("track")
        def on_track(track):
            print(f"[{session_idx}] Receiving AI Response Audio Track!")
        
        ws_path = f"{WS_URL}/voice-sessions/{session_id}/webrtc?token={TOKEN}"
        
        try:
            async with websockets.connect(ws_path) as ws:
                # We need a small queue to pass ICE candidates to WS properly
                async def signaling_loop():
                    async for msg in ws:
                        data = json.loads(msg)
                        if data["type"] == "answer":
                            await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type=data["type"]))
                        elif data["type"] == "candidate":
                            candidate_info = data["candidate"]
                            await pc.addIceCandidate(RTCIceCandidate(
                                candidate=candidate_info["candidate"],
                                sdpMid=candidate_info["sdpMid"],
                                sdpMLineIndex=candidate_info["sdpMLineIndex"]
                            ))
                asyncio.create_task(signaling_loop())

                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                await ws.send(json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}))
                
                print(f"[{session_idx}] Blasting Audio and waiting 25s for processing...")
                await asyncio.sleep(25)
                await pc.close()
        except Exception as e:
            print(f"[{session_idx}] Error: {e}")

async def main():
    print(f"🚀 Spawning {CONCURRENCY} full audio processing sessions...")
    tasks = [run_client(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*tasks)
    print("✅ All audio stress tests finished.")

if __name__ == "__main__":
    asyncio.run(main())
