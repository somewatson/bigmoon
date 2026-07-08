# FFmpeg Distributed Architecture: Dramatiq & RabbitMQ

## Overview
This document outlines the architecture and implementation plan for a distributed video processing system. The system uses **Dramatiq** as the task queue, **RabbitMQ** as the message broker, **Docker** for containerization, and **NFS** for shared storage across multiple physical servers.

## Architecture
### 1. Components
- **Broker Server**: Runs RabbitMQ. Acts as the central coordinator for all tasks.
- **App Server**: The Python application that produces tasks and handles user requests.
- **Worker Servers**: Multiple servers running Docker containers with a custom-built `ffmpeg` and the Dramatiq worker process.
- **Shared Storage (NFS)**: A central file server mounted on all nodes to allow seamless file access.

### 2. Data Flow
`User Request` $\rightarrow$ `App Server` $\rightarrow$ `RabbitMQ` $\rightarrow$ `Distributed Worker` $\rightarrow$ `FFmpeg` $\rightarrow$ `NFS Storage`

---

## Implementation Detail

### 1. Infrastructure Setup
#### NFS Configuration
- **Mount Point**: `/mnt/video_storage` on all servers.
- **Recommended `/etc/fstab` options**: `rw,hard,intr,rsize=32768,wsize=32768,tcp,nfsvers=4`.
- **Structure**:
  - `/mnt/video_storage/inputs/`
  - `/mnt/video_storage/outputs/`
  - `/mnt/video_storage/tmp/`

#### RabbitMQ Setup
- **Image**: `rabbitmq:management`
- **Ports**: 
  - `5672`: AMQP protocol (Workers/App).
  - `15672`: Management UI (Admin).

### 2. Docker Strategy
#### Docker Compose Configuration
Since this is a distributed system across different servers, we use separate `docker-compose.yml` files for different roles.

**A. Broker Server (`docker-compose.broker.yml`)**
Runs the central RabbitMQ instance.
```yaml
services:
  rabbitmq:
    image: rabbitmq:management
    container_name: rabbitmq
    ports:
      - "5672:5672"   # AMQP Protocol
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: always

volumes:
  rabbitmq_data:
```

**B. Worker Servers (`docker-compose.worker.yml`)**
Deployed on every worker machine. Note the use of `devices` for GPU access.
```yaml
services:
  ffmpeg-worker:
    build: .
    container_name: ffmpeg-worker
    devices:
      - /dev/dri:/dev/dri # For Intel/AMD GPUs
    # deploy: # Uncomment for NVIDIA GPUs
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]
    volumes:
      - /mnt/video_storage:/data # Host NFS mount mapped to container
    environment:
      - RABBITMQ_URL=amqp://guest:guest@<BROKER_IP>:5672
    restart: always
```

**C. App Server (`docker-compose.app.yml`)**
The producer of the tasks.
```yaml
services:
  app:
    build: .
    container_name: bigmoon-app
    ports:
      - "5000:5000"
    volumes:
      - /mnt/video_storage:/data
    environment:
      - RABBITMQ_URL=amqp://guest:guest@<BROKER_IP>:5672
    restart: always
```

#### High-Performance FFmpeg Build
The workers use a multi-stage Docker build...

#### Dynamic Hardware Routing (Self-Aware Workers)
The image uses an `entrypoint.sh` script to detect available hardware and join the corresponding RabbitMQ queues automatically.

**`entrypoint.sh` Logic:**
1. Probes for NVIDIA GPUs via `nvidia-smi`.
2. Probes for AMD GPUs via `/dev/dri` and `lspci`.
3. Probes for Intel GPUs via `vainfo`.
4. Joins a comma-separated list of detected queues (e.g., `nvidia_queue,intel_queue`).
5. Falls back to `cpu_queue` if no GPU is detected.

#### Deployment Command
Workers must be started with the `--device /dev/dri` flag (and `--gpus all` for NVIDIA) to access hardware:
```bash
docker run -d \
  --name ffmpeg-worker \
  --device /dev/dri:/dev/dri \
  -v /mnt/video_storage:/data \
  -e RABBITMQ_URL=amqp://guest:guest@<BROKER_IP>:5672 \
  ffmpeg-worker-image
```

### 3. Application Logic
#### Dramatiq Actor
The app routes tasks to specific queues based on the required hardware.

```python
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
import subprocess

rabbitmq_broker = RabbitmqBroker(url="amqp://guest:guest@<BROKER_IP>:5672")
dramatiq.set_broker(rabbitmq_broker)

@dramatiq.actor(max_retries=3, time_limit=3600 * 24)
def process_video(input_path, output_path, options):
    # options contain the encoder (e.g. h264_nvenc, h264_vaapi, or libx264)
    cmd = ['ffmpeg', '-i', input_path, *options, output_path]
    subprocess.run(cmd, check=True)

# Routing example:
# process_video.send_with_options(args=(in, out, opt), queue_name="nvidia_queue")
```

### 4. Key Considerations
- **I/O Performance**: Use local `/tmp` for intermediate FFmpeg fragments to avoid NFS network saturation.
- **Resource Management**: Use `--cpus` and `--memory` flags to protect the host OS.
- **Hardware Access**:
    - **NVIDIA**: Requires `nvidia-container-toolkit` and `--gpus all`.
    - **Intel/AMD**: Requires `--device /dev/dri`.
- **Monitoring**: RabbitMQ Management UI for queue health.

---

## Checklist for Implementation
- [ ] Setup NFS server and mount on all worker nodes.
- [ ] Deploy RabbitMQ container.
- [ ] Build custom FFmpeg Docker image (SVT-AV1 $\rightarrow$ dav1d $\rightarrow$ FFmpeg).
- [ ] Implement `tasks.py` with `subprocess` logic.
- [ ] Deploy workers using `entrypoint.sh` and correct device flags.
- [ ] Verify routing by sending tasks to `nvidia_queue`, `amd_queue`, `intel_queue`, or `cpu_queue`.
