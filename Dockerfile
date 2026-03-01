FROM python:3.11-slim

WORKDIR /app

COPY enclave/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY enclave/ .

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8080"]
