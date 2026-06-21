FROM python:3.11-slim

# Install system dependencies
# ffmpeg for video processing
# intel-media-va-driver-non-free and libvpl for Intel QSV GPU support (AV1 requires non-free and VPL)
# vainfo for debugging GPU acceleration
RUN apt-get update && apt-get install -y \
    ffmpeg \
    intel-media-va-driver-non-free \
    libvpl2 \
    vainfo \
    && rm -rf /var/lib/apt/lists/*

# Force use of the Intel iHD driver
ENV LIBVA_DRIVER_NAME=iHD

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
