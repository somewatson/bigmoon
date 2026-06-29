# AGENTS.md - Big Moon Guidance

## Project Tracking
- **Todo List**: `TODO.md`

## Developer Commands
- **Run App (Local)**: `python app/main.py --debug`
- **Run Tests**: `export FLASK_ENV=testing && pytest tests/test_app.py`
- **GPU Verification**: `vainfo` (Verify Intel VA-API access)
- **Codec Check**: `ffmpeg -encoders | grep -E "av1_vaapi|libsvtav1"`

## Architecture Notes
- **Backend**: Flask application located in `/app`.
- **Persistence**: SQLite database stored in `/data`.
- **VOD Storage**: Downloaded files stored in `/app/downloads` (or `/downloads` on host).
- **Hardware Accel**: Relies on Intel VA-API and `iHD` driver. Uses SVT-AV1 for AV1 encoding.
- **Code Style**: Files should aim for a maximum length of 750 lines. If a file exceeds this threshold, start extracting related functionality into modular files.

## Environment & Setup
- **Required `.env` Keys**: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `USE_GPU`.
- **Permissions**: Local development requires user to be in `render` and `video` groups.
- **Driver**: `LIBVA_DRIVER_NAME=iHD` must be set for Intel GPU acceleration.
