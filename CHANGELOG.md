# Changelog

All notable changes to the Faceless Video Pipeline will be documented in this file.

## [1.0.0] - 2024-03-01

### Added
- **Synchronized Subtitles**: Precise word-level timing captured from AI narration and overlaid on video.
- **Pillow-based Text Rendering**: Robust fallback for subtitle rendering when ImageMagick is not available.
- **Local Gameplay Backgrounds**: Support for Minecraft, GTA 5, Soap Cutting, and Satisfying videos stored in `assets/backgrounds/`.
- **Manual Visual Selection**: UI now allows picking specific files from the built-in library.
- **Trending Reddit Categories**: Added "Drama" (AITA), "Tales," "Entitled," and "Revenge" categories.
- **Series Detection**: Identify "Part 1," "Part 2" stories from Reddit automatically.
- **One-Click Launch**: Added `run.sh` (Linux/macOS) and `run.bat` (Windows) scripts that automatically set up the environment and open the browser.
- **Parallel Downloads**: Used `ThreadPoolExecutor` to speed up Pexels clip fetching.
- **Rolling Retention Policy**: Automatically keeps only the 3 most recent final videos to save disk space.

### Changed
- **UI Overhaul**: Structured 3-step workflow (Content Selection -> Visuals Selection -> Generate & Review).
- **Harden Uploader**: Multi-strategy success detection for YouTube/TikTok and automatic browser lock file cleanup.
- **Enhanced Reddit Sourcing**: Implemented rotating User-Agents and multi-subreddit retry loops.
- **Optimized Rendering**: Switched to `method="chain"` in MoviePy for faster stitching of identical-sized clips.

### Fixed
- **AskReddit Sourcing**: Fixed empty body posts by retrieving top comments.
- **Uploader Locks**: Automatically handles `SingletonLock` on Windows and similar session locks on Linux.
- **Integer Casting**: Fixed TypeError in video engine when passing float coordinates to underlying libraries.
- **Sentence Splitting**: Improved regex to handle abbreviations and clean newlines.

---
*Next update will be documented here.*
