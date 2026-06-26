# --- Stage 1: Build FFmpeg ---
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies and Intel GPU repos for libvpl
RUN apt-get update && apt-get install -y \
    build-essential cmake git pkg-config wget yasm nasm gpg ca-certificates libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor | tee /usr/share/keyrings/intel-graphics.gpg >/dev/null
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list

RUN apt-get update && apt-get install -y \
    libvpl-dev \
    libva-dev \
    libx264-dev \
    libx265-dev \
    libdav1d-dev \
    libnuma-dev \
    && rm -rf /var/lib/apt/lists/*

# Build SVT-AV1 from source to meet version requirement (>= 0.9.0)
RUN wget https://gitlab.com/AOMediaCodec/SVT-AV1/-/archive/master/SVT-AV1-master.tar.gz && \
    tar -xvf SVT-AV1-master.tar.gz && \
    cd SVT-AV1-master && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_C_FLAGS="-flto=auto" -DCMAKE_CXX_FLAGS="-flto=auto" && \
    make -j$(nproc) && \
    make install && \
    cd ../.. && rm -rf SVT-AV1-master SVT-AV1-master.tar.gz

# Build FFmpeg with SVT-AV1 support
RUN wget https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
    tar -xjf ffmpeg-snapshot.tar.bz2 && \
    cd $(tar -tf ffmpeg-snapshot.tar.bz2 | head -1 | cut -f1 -d'/') && \
    ./configure \
        --enable-gpl \
        --enable-nonfree \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libsvtav1 \
        --enable-libdav1d \
        --enable-libvpl \
        --enable-vaapi \
        --enable-openssl \
        --extra-cflags="-I/usr/local/include" \
        --extra-ldflags="-L/usr/local/lib" && \
        make -j$(nproc) && \
        make install && \
        cd .. && rm -rf ffmpeg-snapshot*

# --- Stage 2: Final Image ---
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install prerequisites for Intel GPU repository
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

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    intel-media-va-driver-non-free \
    libdav1d-dev \
    libvpl2 \
    vainfo \
    libnuma1 \
    libx264-dev \
    libx265-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy FFmpeg and libraries from builder stage
COPY --from=builder /usr/local/bin/ffmpeg /usr/local/bin/
COPY --from=builder /usr/local/bin/ffprobe /usr/local/bin/
COPY --from=builder /usr/local/lib /usr/local/lib

# Update linker cache
RUN ldconfig

# Force use of the Intel iHD driver
ENV LIBVA_DRIVER_NAME=iHD
ENV ONEVPL_DEVICE=GPU

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
