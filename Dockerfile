FROM python:3.10-slim

WORKDIR /app

# 1. 의존성 파일 복사
COPY requirements.txt .

# 2. 필요한 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 3. 소스 코드 복사
COPY . .

# 4. 실행 명령
CMD ["python", "app.py"]