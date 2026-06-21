FROM python:3.11-slim

# Install system dependencies
# ffmpeg for video processing
# intel-media-va-driver and va-driver-all for Intel QSV GPU support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    intel-media-va-driver \
    va-driver-all \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Create directories for data and downloads
RUN mkdir -p /data /app/downloads

# Expose the Flask port
EXPOSE 5000

# Run the application with PYTHONUNBUFFERED=1 and --debug flag to ensure logs are printed immediately
CMD ["env", "PYTHONUNBUFFERED=1", "python", "main.py", "--debug"]
