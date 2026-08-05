import asyncio
import aiohttp
import json
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YTcyZjAzYzU4OGI5MDI2NjMwZWE2MmEiLCJyb2xlIjoib3JnX21lbWJlciIsIm9yZ19pZCI6IjZhNzJmMDNiNTg4YjkwMjY2MzBlYTYyOSIsImV4cCI6MTc4NjAwMzkwMH0.LSj7k3P9at2gdb41IO41kktCK7OTTgXaf3BFqj6xTkI"
ORG_ID = "6a72f03b588b9026630ea629" # Standard test org
CLINIC_ORG_ID = "6a72f03b588b9026630ea629" # Forcing same org, but testing scope logic (we can manually adjust DB)

async def run_client(name, org_id, audio_file):
    async with aiohttp.ClientSession() as client:
        # Create session
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        payload = {
            "organization_id": org_id,
            "conversation_id": f"isolation_{name}",
            "session_type": "push_to_talk",
            "agent_id": None
        }
        async with client.post(f"{BASE_URL}/voice-sessions/", json=payload, headers=headers) as resp:
            data = await resp.json()
            session_id = data.get("session_id")
            if not session_id: return

        print(f"[{name}] Spawned {session_id} in org {org_id}")
        
        pc = RTCPeerConnection()
        player = MediaPlayer(audio_file)
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
                
                print(f"[{name}] Blasting Audio and waiting 20s for processing...")
                await asyncio.sleep(20)
                await pc.close()
        except Exception as e:
            print(f"[{name}] Error: {e}")

async def main():
    print(f"🚀 Running ISOLATION TEST...")
    
    t1 = run_client("Restaurant", ORG_ID, "Backend/scripts/test_audio/isolation_restaurant.wav")
    t2 = run_client("Clinic", CLINIC_ORG_ID, "Backend/scripts/test_audio/isolation_clinic.wav")
    
    await asyncio.gather(t1, t2)
    print("✅ Isolation tests finished. Please check Uvicorn logs to verify isolation boundaries.")

if __name__ == "__main__":
    asyncio.run(main())
