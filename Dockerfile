# --- Stage 1: Build FFmpeg ---
FROM ubuntu:22.04 AS builder

ARG TARGETPLATFORM
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake git pkg-config wget yasm nasm gpg ca-certificates libssl-dev \
    meson ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Conditional Intel GPU setup for amd64
RUN if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor | tee /usr/share/keyrings/intel-graphics.gpg >/dev/null && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list && \
        apt-get update && apt-get install -y libvpl-dev libva-dev && \
        rm -rf /var/lib/apt/lists/*; \
    fi

RUN apt-get update && apt-get install -y \
    libx264-dev \
    libx265-dev \
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

# Build dav1d from source to ensure version >= 1.0.0 and pkg-config compatibility
RUN git clone https://code.videolan.org/videolan/dav1d && \
    cd dav1d && \
    mkdir build && cd build && \
    meson setup .. && \
    ninja -C . && \
    ninja -C . install && \
    cd ../.. && rm -rf dav1d

# Build FFmpeg with conditional Intel support
RUN wget https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
    tar -xjf ffmpeg-snapshot.tar.bz2 && \
    cd $(tar -tf ffmpeg-snapshot.tar.bz2 | head -1 | cut -f1 -d'/') && \
    CONF_FLAGS="--enable-gpl --enable-nonfree --enable-libx264 --enable-libx265 --enable-libsvtav1 --enable-libdav1d --enable-openssl" && \
    if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        CONF_FLAGS="$CONF_FLAGS --enable-libvpl --enable-vaapi"; \
    fi && \
    ./configure $CONF_FLAGS \
        --extra-cflags="-I/usr/local/include" \
        --extra-ldflags="-L/usr/local/lib" && \
        make -j$(nproc) && \
        make install && \
        cd .. && rm -rf ffmpeg-snapshot*

# --- Stage 2: Final Image ---
FROM ubuntu:22.04

ARG TARGETPLATFORM
ENV DEBIAN_FRONTEND=noninteractive

# Install prerequisites
RUN apt-get update && apt-get install -y \
    wget \
    gpg \
    ca-certificates \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Conditional Intel GPU repositories and drivers
RUN if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor | tee /usr/share/keyrings/intel-graphics.gpg >/dev/null && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list && \
        apt-get update && apt-get dist-upgrade -y; \
    fi

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libdav1d-dev \
    libnuma1 \
    libx264-dev \
    libx265-dev \
    && if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        apt-get install -y intel-media-va-driver-non-free libvpl2 vainfo; \
    fi && \
    rm -rf /var/lib/apt/lists/*

# Copy FFmpeg and libraries from builder stage
COPY --from=builder /usr/local/bin/ffmpeg /usr/local/bin/
COPY --from=builder /usr/local/bin/ffprobe /usr/local/bin/
COPY --from=builder /usr/local/lib /usr/local/lib

# Update linker cache
RUN ldconfig

# Set Intel-specific envs only if on amd64
RUN if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        echo "ENV LIBVA_DRIVER_NAME=iHD" >> /etc/environment && \
        echo "ENV ONEVPL_DEVICE=GPU" >> /etc/environment; \
    fi

# To ensure the variables are available to the shell, we set them conditionally in a way Docker understands or handle it at runtime.
# Since ENV is static, we will leave them as is but the code handles USE_GPU=false.
# We'll set them here and the user can override them or the app can ignore them.
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
