# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

> From 2.4.0 onwards the changelog and commit messages are written in English.
> The README and the app's Portuguese locale remain in Portuguese.

## [Unreleased]

### Added

- **Resolution setting** — Auto (detects the widest monitor and picks 1080p,
  1440p or 4K), High (4K) and Low (1080p). Unsplash, Wallhaven and Bing are
  queried at the matching size (Unsplash quality adapts too) and oversized
  downloads are downscaled before saving, saving bandwidth and disk space.
  Screen detection uses `EnumDisplayMonitors` on Windows, `NSScreen` on macOS
  and `xrandr` on Linux, with a 1920 px fallback.
- New `resolution` setting with validation/migration, plus a Resolution
  selector in Settings → General next to the language selector.
- Tests for screen bucketing, per-source size parameters and the
  downscale-on-save path.

### Fixed

- CI flakiness on `windows-latest` / Python 3.10: the runner's Tcl/Tk install
  can be broken (`ttk/defaults.tcl` missing). UI tests now share a single Tk
  root and skip cleanly when Tk cannot be initialised. (The `v2.4.0` tag build
  passed with the same code — this was an environment issue.)
- CI no longer fails when GitHub has no macOS arm64 runners available
  ("The job was not acquired by Runner of type hosted"). macOS was removed
  from the routine test matrix — its UI tests were already skipped there and
  the pure-Python tests are covered by Windows/Linux. macOS is still built
  and packaged on releases.

### Changed

- CI matrix is now Windows + Linux × Python 3.10/3.12; builds run only for
  `v*` tags or manual dispatch, and a `concurrency` group cancels superseded
  runs so runners are not wasted.
- **The whole repository is now in English**: README, CI job/step names,
  `.gitignore` comments, `pyproject.toml` metadata and ruff comments, all
  module/function docstrings and inline comments, log messages, build scripts
  and test messages. Commit messages and the changelog were already in English.
- **The GitHub project page is in English too**: repository description,
  topics and website link; release notes rewritten in English; all eight
  documentation screenshots regenerated with the English UI (and renamed to
  English filenames). `WPC_SHOT_LANG=pt` still regenerates Portuguese shots.
- The Portuguese UI strings remain in the code on purpose: they are the
  source locale of the `pt`/`en` translation catalog.

## [2.4.0] — 2026-11-25

### Added

- **English interface**: the app now ships with Portuguese (source) and English
  locales. The system language is detected automatically (Windows UI language
  or `LANG`/`LC_*` on macOS/Linux) and can be overridden in
  **Settings → General → Language** (`auto` / `pt` / `en`). Tray menus,
  notifications, dialogs and error messages are translated too.
- Lightweight in-code i18n (`i18n.py`): no `.mo`/gettext tooling or extra data
  files, so PyInstaller builds need no changes.
- New setting `language` with validation and migration of unknown values.
- The tray menu is rebuilt in the new language as soon as settings are saved.
- Tests: translation lookup, system-language detection, settings validation,
  translated interval labels, an English UI integration test, and an AST check
  that guarantees every `t("...")` string has an English entry.

### Changed

- Commit messages and changelog are now written in English.
- `INTERVAL_LABELS` remains the Portuguese canonical list (used for settings
  migration); `interval_labels()` returns translated labels for the UI/tray.
- Theme/interval selectors in the settings window now map translated labels
  back to their ids via per-window lookup tables instead of module constants.

## [2.3.0] — 2026-11-24

### Added

- Retries with exponential backoff across all three image sources (Unsplash,
  Bing, Wallhaven): transient network errors, `429` and `5xx` no longer abort
  the whole source cycle.
- Log rotation (`log.txt` rotates to `log.txt.1` past 1 MB).
- Lint job (ruff) and test coverage (pytest-cov) in CI.
- CI now tests **Python 3.10 and 3.12** (previously only 3.12) on all three OSes.
- Packaging metadata: homepage/repository URLs and a modern `requests>=2.32`
  floor; ruff configuration aligned with the project's style.
- New tests: suggestion deduplication, log rotation, orphan-file cleanup and
  single-source versioning.

### Fixed

- **"New suggestion"** now also rejects already-used wallpapers (previously it
  only checked the tone), keeping the "no repeats" promise.
- Image files are always closed (`with Image.open(...)`) — on Windows, open
  handles could silently prevent the automatic cleanup of old images.
- A wallpaper that fails to apply no longer leaves an orphan file behind.
- Shared runtime state (`last_change`, `last_source`, …) is protected by a
  lock — no more inconsistent reads between the UI and worker threads.
- AppleScript escaping on macOS now also escapes backslashes.

### Changed

- The version has a **single source of truth**
  (`wallpaper_changer/__init__.py`); `pyproject.toml` reads it dynamically and
  `config.py` imports it.
- The recent-images gallery is computed in a worker thread (off the Tk main
  thread), avoiding freezes in the settings window.
- Removed the unused parameter of `_enabled_sources`.

## [2.2.1] — 2026

- Windows startup uses `pythonw.exe` (no console window).
- Hardened tray: X11 fallback on Linux, warning dialogs and a single-instance
  mutex on Windows.

## [2.2.0] — 2026

- Persistent used-wallpaper history (exact + perceptual hash) to never repeat
  images.

## [2.1.0] — 2026

- Wally-style preview, Wallhaven source (no key), more intervals, pause and
  theme-detection fixes.

## [2.0.0] — 2026

- First public release with CI on all three platforms and automatic releases
  on `v*` tags.
