# 📝 Big Moon Development Roadmap

## 🛠️ High Priority

### 3. Library UX & Stability
**Goal**: Improve the loading and visual feedback of the library.
- [x] **Implement Loading States**:
      - Add visual loading indicators (spinners/skeletons) while `loadLibrary` is fetching thumbnail statuses.
      - Ensure no duplicate rows appear during async load.

### 4. Chat Integration & Compressed Previews
**Goal**: Enable downloading/viewing of chat logs and previewing of compressed videos.
- [ ] **Backend Implementation**:
      - [ ] Update database models to track `chat_json_path` and download status.
      - [ ] Implement `chat.json` downloader in `app/downloader.py`.
      - [ ] Create API endpoints for `/api/download/chat/<video_id>` and `/api/chat/<video_id>`.
- [ ] **Frontend Implementation**:
      - [ ] Implement a Chat Viewer UI (modal or tab) to render `chat.json` as a conversation.
      - [ ] Add "View Chat" and "Download Chat" buttons to the Library and Tasks views.
      - [ ] Update preview logic to support compressed video file paths.
- [ ] **Verification**:
      - [ ] Verify chat download and rendering accuracy.
      - [ ] Confirm compressed video previews load correctly.


## 📉 Medium Priority
- [ ] General performance optimization for thumbnail generation.