# Implementation Plan: Temporary Shared Links for Videos

## Objective
Implement a functionality to generate a shared, public link for video files that allows downloading without authentication. These links must be cryptographically secure and expire automatically after 24 hours.

## Technical Specification

### 1. Database Schema
Create a new table `shared_links` to track temporary access:
- `id`: Integer, Primary Key.
- `video_id`: Integer, Foreign Key (references the video/VOD table).
- `token`: String, Unique, Indexed (cryptographically secure random string).
- `created_at`: DateTime, defaults to current time.
- `expires_at`: DateTime (set to `created_at` + 24 hours).

### 2. Backend Logic (`/app`)
- **Token Service**: Create a utility to generate secure tokens (e.g., using `secrets` or `uuid` module) and manage the database entries.
- **API Endpoint**: 
    - `POST /api/videos/<video_id>/share`: Generates a new token, stores it in the DB, and returns the full public URL.
- **Public Download Route**:
    - `GET /share/<token>`:
        1. Look up the token in `shared_links`.
        2. Verify `expires_at` > current time.
        3. Retrieve the corresponding file path from the video's record.
        4. Use Flask's `send_from_directory` to serve the file from `/app/downloads`.
        5. Return 404 if the token is invalid or expired.

### 3. Frontend Updates
- **Video Details Page**: Add a "Generate Share Link" button.
- **Library View**: Add a share icon/button to each video entry.
- **User Interface**: Implement a copy-to-clipboard mechanism (modal or toast) to display the generated link to the user.

### 4. Security & Maintenance
- **Authentication Bypass**: Ensure the `/share/<token>` route is excluded from the global authentication middleware/decorators.
- **Cleanup**: (Optional) Implement a periodic task (via Dramatiq) to purge expired tokens from the database to prevent bloat.
- **Scope**: Ensure the link only permits downloading the file and provides no access to the administrative dashboard or other database records.

## Execution Steps
1. [ ] Analyze existing database models to identify the correct video table.
2. [ ] Implement the `shared_links` table migration/creation.
3. [ ] Implement the token generation and storage logic.
4. [ ] Create the public download route and test it with a manual token.
5. [ ] Create the API endpoint for the frontend.
6. [ ] Update the UI to allow users to request and copy share links.
7. [ ] Verify that links expire correctly after 24 hours.
