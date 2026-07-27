# Use python base image
FROM python:3.12-slim

# Install system dependencies (ffmpeg and curl)
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8080

# Command to run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
