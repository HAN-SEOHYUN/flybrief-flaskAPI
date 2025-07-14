FROM python:3.10-slim

WORKDIR /app

# Flask 직접 설치
RUN pip install flask

COPY app.py .

CMD ["python", "app.py"]