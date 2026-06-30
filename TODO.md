# 📝 Big Moon Development Roadmap

## 🛠️ High Priority

### 8. Task Pause & Resume System
**Goal**: Allow downloads and compression tasks to persist across Docker container restarts and deployments without restarting from 0%.
- [ ] **Persistence Layer**:
    - [ ] Add `last_byte_offset` to `DownloadTask` model in `models.py`.
    - [ ] Implement periodic offset saving in `downloader.py` during active downloads.
- [ ] **Graceful Shutdown (Pause)**:
    - [ ] Update `handle_shutdown` and `shutdown_all_tasks` to transition statuses to `paused` instead of `error`.
    - [ ] Ensure current progress is flushed to DB before exit.
- [ ] **Recovery Manager (Resume)**:
    - [ ] Replace "Startup Cleanup" in `bootstrap_admin` with a recovery scan for `paused` or hanging tasks.
    - [ ] Implement Range-request based resuming for downloads using `last_byte_offset`.
    - [ ] Implement partial-file check and batch-skip logic for compression recovery.
    - [ ] Automatically re-trigger async tasks for recovered items.
- [ ] **Verification**:
    - [ ] Simulate container restart during large download and verify resume from offset.

### 7. Admin Activity Monitor (Fixes)
**Goal**: Fix data gaps in the Activity Monitor dashboard.
- [ ] **API Fixes**:
    - [ ] Add `total_users` to `/api/admin/activity` stats.
    - [ ] Implement `user_summaries` aggregation (total, completed, failed tasks per user).
- [ ] **Verification**:
    - [ ] Verify "Total Users" and "User Activity Summaries" are populated in the UI.
