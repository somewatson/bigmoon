# Project TODOs

## Completed Features
- [x] **My Library Page Polish**
    - Add "Select All" checkbox and search/filter bar
    - Implement numerical sorting (Date, Size, Name)
    - Optimize thumbnail endpoint with timeouts and caching
- [x] **Auto-Download & Automation Pipeline**
    - Create `MonitoredChannel` model with compression settings
    - Implement background monitoring worker (APScheduler)
    - Add 24h lookback and duplicate check logic
    - Implement task chaining: Download $\rightarrow$ Compress
    - Create UI management menu for automation settings
- [x] **UI & UX Polish**
    - Replace all "QSV" references with "VA-API/Hardware Accelerated"
    - Implement global CSS tooltip system across all interactive buttons

