FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY data_manager.py .

RUN mkdir -p /app/data
ENV AAC_DATA_DIR=/app/data

EXPOSE 8085

CMD ["python", "app.py"]
