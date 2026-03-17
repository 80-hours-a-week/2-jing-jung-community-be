from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.routers.routes import router
from fastapi.staticfiles import StaticFiles
import os
import json
import asyncio
from typing import Dict
from datetime import datetime
import aioredis

from app.db import SessionLocal
from sqlalchemy import text

app = FastAPI()

# --- Redis 및 WebSocket 설정 ---
# 환경 변수에서 Redis URL을 가져오고, 없으면 기본값으로 "redis://localhost"를 사용합니다.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


class ConnectionManager:
    def __init__(self):
        # 특정 서버 인스턴스에 접속된 소켓들만 관리
        self.active_connections: Dict[int, list[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: int, websocket: WebSocket):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_to_local(self, room_id: int, message: str):
        """현재 서버에 접속 중인 유저들에게만 발송 (Redis로부터 받은 메시지 전파용)"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)


manager = ConnectionManager()

# --- CORS 설정 ---
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://k8s-default-mainingr-ffc4d92d4c-1904231776.ap-southeast-2.elb.amazonaws.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


# --- WebSocket Endpoint (Redis Pub/Sub 통합) ---
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str = ""):
    db = SessionLocal()
    sender_id = None

    try:
        # 1. 인증 로직
        if not token:
            await websocket.close(code=1008)
            return

        sql = text("SELECT data FROM sessions WHERE session_id = :session_id")
        result = db.execute(sql, {"session_id": token}).fetchone()
        if not result:
            await websocket.close(code=1008)
            return
        sender_id = int(result.data)

        # 2. 참여 권한 확인
        sql_check = text("SELECT id FROM chat_participants WHERE room_id = :room_id AND user_id = :user_id")
        if not db.execute(sql_check, {"room_id": room_id, "user_id": sender_id}).fetchone():
            await websocket.close(code=1008)
            return

        # 3. 매니저 등록 및 Redis 구독 시작
        await manager.connect(room_id, websocket)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"chat_room_{room_id}")

        # Redis 메시지를 감시하다가 현재 서버 접속자들에게 뿌려주는 Task
        async def redis_listener():
            try:
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        # Redis에서 받은 메시지를 현재 서버의 해당 방 사람들에게 브로드캐스트
                        await manager.broadcast_to_local(room_id, message['data'])
            except Exception as e:
                print(f"Redis Listener Error: {e}")

        listener_task = asyncio.create_task(redis_listener())

        # 4. 메시지 수신 대기 루프
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                content = message_data.get("content")

                if content:
                    # DB 저장
                    insert_sql = text("""
                        INSERT INTO messages (room_id, sender_id, content, created_at, is_read)
                        VALUES (:room_id, :sender_id, :content, NOW(), 0)
                    """)
                    db.execute(insert_sql, {
                        "room_id": room_id,
                        "sender_id": sender_id,
                        "content": content
                    })
                    db.commit()

                    # Redis Publish (이게 핵심! 다른 서버 인스턴스에도 메시지가 전달됨)
                    response_message = {
                        "room_id": room_id,
                        "sender_id": sender_id,
                        "content": content,
                        "created_at": datetime.now().isoformat()  # Send actual server time
                    }
                    await redis_client.publish(f"chat_room_{room_id}", json.dumps(response_message))

        except WebSocketDisconnect:
            listener_task.cancel()
            await pubsub.unsubscribe(f"chat_room_{room_id}")
            manager.disconnect(room_id, websocket)

    finally:
        db.close()


# --- 나머지 설정 ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"code": "INVALID_INPUT", "message": "입력값이 잘못되었습니다.", "detail": exc.errors()})


os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    return {"message": "Community Backend Server is Running!"}