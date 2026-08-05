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
AUDIO_FILE = "Backend/scripts/test_audio/10s_long_query.wav"

async def run_failure_client(name: str, wait_time: int):
    async with aiohttp.ClientSession() as client:
        # Create session
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        payload = {
            "organization_id": ORG_ID,
            "conversation_id": f"failure_{name}",
            "session_type": "push_to_talk",
            "agent_id": None
        }
        async with client.post(f"{BASE_URL}/voice-sessions/", json=payload, headers=headers) as resp:
            data = await resp.json()
            session_id = data.get("session_id")
            if not session_id: return

        print(f"[{name}] Spawned {session_id}")
        
        pc = RTCPeerConnection()
        player = MediaPlayer(AUDIO_FILE)
        pc.addTrack(player.audio)
        
        ws_path = f"{WS_URL}/voice-sessions/{session_id}/webrtc?token={TOKEN}"
        
        try:
            async with websockets.connect(ws_path) as ws:
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
                
                print(f"[{name}] Deliberately dropping connection after {wait_time}s...")
                await asyncio.sleep(wait_time)
                await ws.close()
                await pc.close()
                print(f"[{name}] Connection explicitly killed mid-flight.")
        except Exception as e:
            print(f"[{name}] Error: {e}")

async def main():
    print(f"🚀 Running FAILURE RECOVERY TESTS...")
    
    tasks = [
        run_failure_client("disconnect_during_VAD", 3),
        run_failure_client("disconnect_during_STT", 12),
        run_failure_client("disconnect_during_LLM", 18),
        run_failure_client("disconnect_during_Playback", 25)
    ]
    
    await asyncio.gather(*tasks)
    print("✅ Chaos/Failure tests finished. Verify in logs that queues flush cleanly and runtimes are destroyed immediately.")

if __name__ == "__main__":
    asyncio.run(main())
