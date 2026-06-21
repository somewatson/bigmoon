# 🌙 Big Moon

Big Moon is a self-hosted Twitch VOD downloader with a web interface, user authentication, and hardware acceleration for Intel GPUs.

## 🚀 Features

- **VOD Discovery**: Search for any Twitch channel and browse their available VODs.
- **Hardware Accelerated**: Uses Intel QuickSync (QSV) via `/dev/dri` to speed up video processing.
- **User Management**: 
  - **Admin**: Create users and manage the system.
  - **User**: Search and request VOD downloads.
- **Dockerized**: Easy deployment with Docker Compose.
- **Persistent Storage**: All VODs and user data are stored in mapped volumes.

## 🛠️ Setup

### 1. Prerequisites
- Docker and Docker Compose installed.
- A Twitch App Client ID and Client Secret (get them from the [Twitch Dev Console](https://dev.twitch.tv/console)).
- An Intel GPU (for hardware acceleration).

### 2. Configuration
Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
- `TWITCH_CLIENT_ID`: Your Twitch App Client ID.
- `TWITCH_CLIENT_SECRET`: Your Twitch App Client Secret.
- `ADMIN_USERNAME`: The username for the initial admin account.
- `ADMIN_PASSWORD`: The password for the initial admin account.
- `USE_GPU`: Set to `true` to enable Intel QSV acceleration.

### 3. Deployment
Start the application:
```bash
docker compose up -d --build
```

The app will be available at `http://localhost:5000`.

## 📂 Directory Structure
- `/app`: Source code for the Flask backend and templates.
- `/data`: Persistent SQLite database for users.
- `/downloads`: Location where downloaded VODs are stored.

## 🛡️ Security
- No public sign-up page.
- Initial admin is created automatically from `.env` on first run.
- Subsequent users must be created by an administrator through the Admin Dashboard.

## 📜 Credits

This project was created by [Some Watson](https://somewatson.com) with the assistance of [opencode](https://opencode.ai), an AI software engineering agent.

## 📄 License

This project is licensed under the MIT License.
