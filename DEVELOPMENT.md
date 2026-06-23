# 🛠️ Local Development Guide

This guide explains how to run Big Moon on your host machine without using Docker. 

## ⚠️ Prerequisites

Local development requires several system-level dependencies that are otherwise handled by the Docker image.

### 1. System Dependencies (Linux)
You must have the following installed on your host:

- **Python 3.10+**
- **FFmpeg**: Must be compiled with:
  - `vaapi` (for Intel hardware acceleration)
  - `libsvtav1` (for AV1 encoding)
- **Intel GPU Drivers**: 
  - `intel-media-va-driver-non-free` (or `intel-media-driver`)
  - `libva-utils` (to run `vainfo`)
- **Git**

### 2. Hardware Access
Ensure your user has permission to access the GPU:
```bash
sudo usermod -aG render $USER
sudo usermod -aG video $USER
```
*(Log out and log back in for changes to take effect)*

---

## 🚀 Setup Instructions

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd bigmoon
```

### 2. Virtual Environment
It is highly recommended to use a virtual environment to avoid polluting your system Python.
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configuration
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Fill in your `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, and admin credentials.

---

## 🏃 Running the App

Start the Flask server in debug mode:
```bash
python app/main.py --debug
```
The application will be available at `http://localhost:5000`.

---

## 🧪 Testing

To run the integration test suite:
```bash
export FLASK_ENV=testing
pytest tests/test_app.py
```

## 🔍 Troubleshooting

### Hardware Acceleration
If you encounter errors during compression, verify your GPU is accessible:
```bash
vainfo
```
If `vainfo` fails, ensure the Intel Media Driver is installed and the user is in the `render` group.

### FFmpeg Codecs
Check if your local FFmpeg supports the required encoders:
```bash
ffmpeg -encoders | grep -E "av1_vaapi|libsvtav1"
```
If these are missing, you may need to install a more complete version of FFmpeg or compile it from source as described in the `Dockerfile`.
