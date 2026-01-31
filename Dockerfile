FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY data_manager.py .

# Create data directory (will be mounted as volume)
RUN mkdir -p /app/data

# Set environment variable for data directory
ENV AAC_DATA_DIR=/app/data

# Expose port
EXPOSE 8085

# Run the application
CMD ["python", "app.py"]
