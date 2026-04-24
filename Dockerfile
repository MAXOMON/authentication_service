FROM python:3.11-slim


ENV PYTHONBUFFERED=1
ENV UVICORN_WORKERS=1

COPY entrypoint.sh /app/entrypoint.sh

WORKDIR /app

RUN apt-get update && apt-get install -y

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
