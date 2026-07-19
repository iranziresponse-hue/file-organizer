# Orch

A Django + PyQt6 desktop app for Windows that automatically routes every downloaded file to where it belongs, based on filename, extension, and course/topic rules. It is a rewrite of an older PowerShell script (`OrganizeDownloads.ps1`), packaged into a standalone `.exe`.

## What it does

Orch watches your Downloads folder (and a second configurable download location) and moves each new file to where it belongs, without you having to do it by hand:

- School documents get routed by course code or topic keyword into `D:\School\<year>\<semester>\<course>\<category>`, with the category (lecture notes, assignments, past papers, reports, or reference material) detected from the filename.
- Files with no matching course code or topic can optionally fall back to an AI classifier (Groq's OpenAI-compatible API) that reasons over the filename against your course list.
- Ebooks, media files, installers, archives, sensitive files (passwords, keys, certificates), and loose code/project files each get their own destination.
- Stale installers get moved to a review folder after 30 days and deleted after 60.

Every move is logged both to a text log file and to a Django database table, so there is a searchable history of what got moved where and why, surfaced on a dashboard.

## Tech stack

- **Django** provides the data model (`CourseConfig`, `CurriculumEntry`, `MoveEvent`), the admin site, and the dashboard for reviewing recent moves and editing the current semester's config.
- **PyQt6** provides the desktop shell: a system tray icon that starts and stops the watcher, opens the dashboard in your browser, and opens the log file, all without a console window.
- The watcher itself is a polling loop, not a filesystem-events watcher, because a `FileSystemWatcher`/`Register-ObjectEvent` approach in the original PowerShell version was found to silently stop firing when run as a detached background process.
- `main.py` runs Django's migrations and dashboard server on background threads inside the same process as the tray icon, so the packaged exe needs no separate `manage.py` steps.
- The whole app is packaged into a single Windows `.exe` with PyInstaller, targeting `main.py`.

## Project layout

```
config/                     Django project settings, URLs, WSGI/ASGI entry points
gui/
    app.py                   Desktop entry point: django.setup(), migrate, tray, dashboard server
    tray.py                  System tray icon and menu
    server.py                Runs the Django dashboard on a background thread
    watcher_controller.py    Starts/stops the watcher on a background thread
    assets.py                Resolves bundled asset paths, dev and PyInstaller alike
organizer/
    models.py                CourseConfig, CurriculumEntry, MoveEvent
    views.py                  Dashboard and config-edit views
    admin.py                   Django admin registrations
    core/
        paths.py               Every filesystem path/constant the app touches
        rules.py               Pure destination-decision logic (no Django imports, unit-testable)
        ai_classify.py         Optional AI fallback classifier
        watcher.py             The polling watcher loop and move/cleanup logic
    static/organizer/img/      The Orch mark (favicon, tray icon, exe icon)
    templates/organizer/       Dashboard and config-edit HTML templates
    tests/                    Unit tests for rules, ai_classify, watcher, and the views
main.py                      Desktop app entry point (python main.py, or the PyInstaller target)
Orch.spec                    PyInstaller build spec
```

## Setup

```
pip install -r requirements.txt
python main.py
```

This runs migrations automatically, starts the dashboard on `http://127.0.0.1:8765/`, and puts a tray icon in the system tray with Start/Stop watching, Open dashboard, Open log, and Quit.

If you just want the Django dashboard on its own, without the tray app or the watcher:

```
python manage.py migrate
python manage.py runserver
```

Copy `ai_config.example.json` to `ai_config.json` in the project root and fill in your API key if you want the AI fallback classifier enabled. `ai_config.json` is gitignored and never committed. Without it, unmatched files fall back to `_Unsorted` or `_NeedsSorting`.

## Tests

```
python manage.py test
```

Every test that touches `organizer.core.paths` runs against a throwaway temp directory (see `organizer/tests/helpers.py`), never against the real `D:\School`, `D:\myDownloads`, or `Documents` folders those constants point at.

## Build the Windows app

```
pyinstaller Orch.spec
```

The packaged `.exe`, tray icon, app icon, and dashboard favicon all use the Orch mark from `organizer/static/organizer/img/`.

## License

Copyright (c) 2026 Iranzi. All rights reserved. See [LICENSE](LICENSE).
