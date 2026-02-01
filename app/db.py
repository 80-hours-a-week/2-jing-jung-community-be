from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# 1. .env 파일 로드
load_dotenv()


# 2. 환경 변수에서 값 꺼내기
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# 3. URL 조합하기
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

def get_db():
    with engine.connect() as connection:
        yield connection