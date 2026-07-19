# Orch

A Django + PyQt6 desktop app for Windows that organizes learning files and tracks study flow. Point it at a folder, tell it what you're organizing, and it routes every download to the right place automatically: school notes, online course material, research papers, work training docs, whatever fits.

## What it does

Orch runs as a system tray app that watches your Downloads folder (and a second configurable download location) and moves each new file to where it belongs, without you having to do it by hand.

**Profiles.** A profile is a context: School, Online courses, Work training, Research, Certifications, or anything custom. Each profile has its own folder, its own group labels (a student calls them "Year" / "Semester", an online learner might call them "Year" / "Bootcamp"), its own subject list, and its own dashboard. Only one profile is active at a time, and switching is one click.

**Routing.** Within the active profile, documents get sorted by subject code or topic keyword into `<profile folder>\<primary group>\<secondary group>\<subject>\<category>`, with the category (lecture notes, assignments, past papers, reports, or reference material) detected from the filename. Ebooks, media files, installers, archives, sensitive files (passwords, keys, certificates), and loose code/project files each get their own destination, independent of any profile.

**History.** Every move is logged both to a text log file and to a Django database table, so there is a searchable, per-profile history of what got moved where and why, surfaced on a dashboard.

**Setup wizard.** A three-step flow (purpose, structure, sorting behavior) gets a new profile running in under a minute.

## Tech stack

- **Django** provides the data model (`Profile`, `CourseConfig`, `CurriculumEntry`, `MoveEvent`), the admin site, and the dashboard: profile switcher, setup wizard, and recent-moves view.
- **PyQt6** provides the desktop shell: a system tray icon that starts and stops the watcher, opens the dashboard in your browser, opens the log file, and toggles launch-at-startup, all without a console window.
- The watcher itself is a polling loop, not a filesystem-events watcher, because a `FileSystemWatcher`/`Register-ObjectEvent` approach in the original PowerShell version this was ported from was found to silently stop firing when run as a detached background process.
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
    autostart.py             Windows launch-at-login toggle (per-user registry key)
    assets.py                Resolves bundled asset paths, dev and PyInstaller alike
organizer/
    models.py                Profile, CourseConfig, CurriculumEntry, MoveEvent
    views.py                  Dashboard, profile wizard/edit/list/activate/delete views
    admin.py                   Django admin registrations
    core/
        paths.py               Filesystem paths/constants not specific to any one profile
        rules.py               Pure destination-decision logic (no Django imports, unit-testable)
        ai_classify.py         Optional, off-by-default AI fallback classifier
        watcher.py             The polling watcher loop and move/cleanup logic
    static/organizer/img/      The Orch mark (favicon, tray icon, exe icon)
    templates/organizer/       Dashboard, wizard, and profile templates
    tests/                    Unit tests for rules, ai_classify, watcher, and the views
main.py                      Desktop app entry point (python main.py, or the PyInstaller target)
runtime.py                   Resolves persistent-state paths, dev root vs. exe-adjacent when frozen
Orch.spec                    PyInstaller build spec
```

## Setup

```
pip install -r requirements.txt
python main.py
```

This runs migrations automatically, starts the dashboard on `http://127.0.0.1:8765/`, and puts a tray icon in the system tray with Start/Stop watching, Open dashboard, Open log, Start with Windows, and Quit. On first launch it opens the setup wizard so you can create your first profile.

If you just want the Django dashboard on its own, without the tray app or the watcher:

```
python manage.py migrate
python manage.py runserver
```

## Advanced: AI fallback

Each profile has an optional "smart fallback match" setting, off by default. If enabled, files that match no subject code and no topic keyword get one more pass through an AI classifier (Groq's OpenAI-compatible API) before falling back to `_Unsorted`. It needs your own API key: copy `ai_config.example.json` to `ai_config.json` in the project root (or next to the built exe) and fill it in. `ai_config.json` is gitignored and never committed. Nobody needs this to use Orch.

## Tests

```
python manage.py test
```

Every test that touches `organizer.core.paths` runs against a throwaway temp directory (see `organizer/tests/helpers.py`), never against your real profile folders, Downloads, or Documents.

## Build the Windows app

```
pyinstaller Orch.spec
```

The packaged `.exe`, tray icon, app icon, and dashboard favicon all use the Orch mark from `organizer/static/organizer/img/`. The database and `ai_config.json` live next to the built exe (see `runtime.py`), so they persist across runs instead of living inside PyInstaller's temporary extraction folder.

## License

Copyright (c) 2026 Iranzi. All rights reserved. See [LICENSE](LICENSE).
