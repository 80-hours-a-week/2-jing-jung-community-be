from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.routers.routes import router
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # TODO: "http://your-alb-address.com"와 같이 실제 ALB 주소를 추가해주세요. HTTPS를 사용한다면 https로 시작해야 합니다.
    "http://your-alb-address.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_INPUT",
            "message": "입력값이 잘못되었습니다.",
            "detail": exc.errors()
        },
    )

os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return {"message": "Community Backend Server is Running!"}
