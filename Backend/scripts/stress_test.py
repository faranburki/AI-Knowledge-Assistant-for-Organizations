import asyncio
import aiohttp
import websockets
import json

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

# Note: You MUST paste a valid JWT token here that maps to your user and org.
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YTcyZjAzYzU4OGI5MDI2NjMwZWE2MmEiLCJyb2xlIjoib3JnX21lbWJlciIsIm9yZ19pZCI6IjZhNzJmMDNiNTg4YjkwMjY2MzBlYTYyOSIsImV4cCI6MTc4NjAwMzkwMH0.LSj7k3P9at2gdb41IO41kktCK7OTTgXaf3BFqj6xTkI"
ORG_ID = "6a72f03b588b9026630ea629"
CONCURRENCY = 50

async def spawn_session(session_idx: int):
    async with aiohttp.ClientSession() as client:
        # 1. Create Session
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        payload = {
            "organization_id": ORG_ID,
            "conversation_id": f"stress_test_{session_idx}",
            "session_type": "push_to_talk",
            "agent_id": None
        }
        
        print(f"[{session_idx}] Creating session...")
        async with client.post(f"{BASE_URL}/voice-sessions/", json=payload, headers=headers) as resp:
            data = await resp.json()
            session_id = data.get("session_id")
            if not session_id:
                print(f"[{session_idx}] Failed to spawn session! {data}")
                return
            
        print(f"[{session_idx}] Opening WebSocket for {session_id}...")
        try:
            ws_path = f"{WS_URL}/voice-sessions/{session_id}/webrtc?token={TOKEN}"
            async with websockets.connect(ws_path) as ws:
                print(f"[{session_idx}] Connected! Idling for 5 seconds...")
                await asyncio.sleep(5)
                print(f"[{session_idx}] Closing WebSocket...")
                await ws.close()
        except Exception as e:
            print(f"[{session_idx}] Error: {e}")

async def main():
    print(f"🚀 Spawning {CONCURRENCY} concurrent voice sessions for load/leak testing...")
    tasks = [spawn_session(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*tasks)
    print("✅ All sessions spawned and closed. Check Uvicorn logs for metrics (Active Sessions should drop to 0)!")

if __name__ == "__main__":
    asyncio.run(main())
