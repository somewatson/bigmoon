FROM ubuntu:22.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install prerequisites for adding the Intel repository
RUN apt-get update && apt-get install -y \
    wget \
    gpg \
    ca-certificates \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Add Intel GPU repositories
RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor | tee /usr/share/keyrings/intel-graphics.gpg >/dev/null
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list
RUN apt-get update && apt-get dist-upgrade -y

# Install system dependencies
# intel-media-va-driver-non-free and libvpl for Intel QSV GPU support
# vainfo for debugging GPU acceleration
RUN apt-get install -y \
    python3 \
    python3-pip \
    intel-media-va-driver-non-free \
    libvpl2 \
    vainfo \
    && rm -rf /var/lib/apt/lists/*

# Install modern static FFmpeg build (Version 7.x)
# This ensures we have libsvtav1 and av1_qsv support, as Ubuntu 22.04's default ffmpeg is too old.
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar xvf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-release-amd64-static.tar.xz ffmpeg-*-amd64-static

# Force use of the Intel iHD driver
ENV LIBVA_DRIVER_NAME=iHD

# Setup python symlink
RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install python dependencies
COPY app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Create directories for data and downloads
RUN mkdir -p /data /app/downloads

# Expose the Flask port
EXPOSE 5000

# Run the application
CMD ["env", "PYTHONUNBUFFERED=1", "python", "main.py", "--debug"]
