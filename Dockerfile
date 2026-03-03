# 1. Python 이미지 선택
FROM python:3.11-slim

# 2. 컨테이너 내부 작업 디렉토리 설정
WORKDIR /app

# 3. 패키지 설정 파일 복사 및 설치
# pyproject.toml이 있으면 최신 pip는 이를 인식하여 종속성을 설치할 수 있습니다.
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 4. 소스 코드 전체 복사 (app.py, route.py 등)
COPY . .

# 5. 앱 실행 (포트는 5000번 가정)
EXPOSE 5000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]

# Dockerfile에 추가
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.7.0 /lambda-adapter /opt/extensions/lambda-adapter
ENV PORT=5000