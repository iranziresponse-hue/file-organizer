# Orch

A Django + PyQt6 desktop app for Windows that organizes learning files and tracks study flow. Point it at a folder, tell it what you're organizing, and it routes every download to the right place automatically: school notes, online course material, research papers, work training docs, whatever fits.

## What it does

Orch runs as a system tray app that watches your Downloads folder (and a second configurable download location) and moves each new file to where it belongs, without you having to do it by hand.

**Profiles.** A profile is a context: School, Online courses, Work training, Research, Certifications, or anything custom. Each profile has its own folder, its own group labels (a student calls them "Year" / "Semester", an online learner might call them "Year" / "Bootcamp"), its own subject list, and its own dashboard. Only one profile is active at a time, and switching is one click.

**Routing.** Within the active profile, documents get sorted by subject code or topic keyword into `<profile folder>\<primary group>\<secondary group>\<subject>\<category>`, with the category (lecture notes, assignments, past papers, reports, or reference material) detected from the filename. Ebooks, media files, installers, archives, sensitive files (passwords, keys, certificates), and loose code/project files each get their own destination, independent of any profile.

**History.** Every move is logged both to a text log file and to a Django database table, so there is a searchable, per-profile history of what got moved where and why, surfaced on a dashboard.

**Setup wizard.** A three-step flow (purpose, structure, sorting behavior) gets a new profile running in under a minute. Subject codes are added as removable chips, not a comma-separated text blob, and group labels suggest common presets ("Year", "Topic", "Department"...) while still taking anything you type.

**Connects to folders you already have.** A "Browse..." button opens your real file system to point a profile at an existing folder, no typing paths from memory. Once picked, Orch reads what's already inside it: the primary/secondary group fields suggest folders that already exist there (e.g. "Year 2", "Semester 1"), and the subject list suggests the subfolders already sitting under those, one click to adopt them instead of retyping. Each profile connects to its own folder, so having two or more existing folder structures (say, a School drive and a separate Work folder) is exactly what profiles are for.

**Settings.** Nothing is hardcoded to one machine. Which folders get watched, and where ebooks land, are all editable from a Settings page, defaulted sensibly to your own Windows user profile the first time the app runs.

**Guide.** A `?` button in the top bar explains the routing logic in a few bullet points, no digging through docs.

**Document summaries.** Next to any sorted PDF or Word document in Recent Moves, a "Summarize" button generates a long, structured study companion, not a one-line blurb. It reads the actual file, pulls in the other summarizable files already sitting in the same destination folder, and writes a piece with a real hook, a detailed breakdown of the content, and a dedicated section connecting it to those related files. View it in a scrollable popup or download it as a formatted PDF. This is an AI feature (see below), off until you configure a key, and the prompt explicitly forbids em dashes and dash-divider lines.

**Makerere University setup.** The first time you create a profile, Orch asks whether you're a Makerere student. If so, a guided flow walks through your real college, school, and program (typeahead search across all 10 colleges and every school in them, verified directly against each college's official site, not a plain scrolling dropdown), then your year, semester, and this semester's course units, and builds the folder structure for you. Every course unit gets its own "Guide" button: a long, AI-generated academic overview of what a course like that typically covers, clearly presented as general guidance rather than an official syllabus, since Orch has no access to any institution's actual curriculum documents. See `organizer/core/makerere.py` for exactly what's verified versus reasonably inferred, with sources.

**Get your downloads flowing to Orch.** The first-run page walks through pointing your browser's (and other apps') default download location at the folder Orch watches, since Orch only ever sees files that land there.

## Tech stack

- **Django** provides the data model (`AppSettings`, `Profile`, `CourseConfig`, `CurriculumEntry`, `MoveEvent`, `FileSummary`, `CourseGuide`), the admin site, the dashboard, and a small read-only local API (`/api/browse-folders/`) that lets the UI browse this machine's real folders. The dashboard only ever binds to `127.0.0.1` (see `gui/server.py`), so this never leaves the machine.
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
    models.py                AppSettings, Profile, CourseConfig, CurriculumEntry, MoveEvent, FileSummary, CourseGuide
    views.py                  Dashboard, profile wizard/edit/list/activate/delete, Makerere wizard, settings, summary/guide views
    admin.py                   Django admin registrations
    core/
        paths.py               Filesystem paths/constants not specific to any one profile
        rules.py               Pure destination-decision logic (no Django imports, unit-testable)
        ai_classify.py         Optional, off-by-default AI fallback classifier
        summarize.py           Long-form AI document summaries and course guides: extraction, prompts, HTML/PDF rendering
        makerere.py            Verified Makerere University college/school/programme structure, with sources
        watcher.py             The polling watcher loop and move/cleanup logic
    static/organizer/img/      The Orch mark (favicon, tray icon, exe icon)
    static/organizer/js/       Small vanilla-JS widgets: tag/chip input, folder browser, folder suggestions, summary/guide popups
    templates/organizer/       Dashboard, wizard, Makerere wizard, profile, start, and settings templates
    tests/                    Unit tests for rules, ai_classify, summarize, makerere, watcher, views, settings, and folder browsing
main.py                      Desktop app entry point (python main.py, or the PyInstaller target)
runtime.py                   Resolves persistent-state paths, dev root vs. exe-adjacent when frozen
Orch.spec                    PyInstaller build spec
```

## Setup

```
pip install -r requirements.txt
python main.py
```

This runs migrations automatically, starts the dashboard on `http://127.0.0.1:8765/`, and puts a tray icon in the system tray with Start/Stop watching, Open dashboard, Open log, Start with Windows, and Quit. On first launch it opens the get-started page so you can create your first profile.

If you just want the Django dashboard on its own, without the tray app or the watcher:

```
python manage.py migrate
python manage.py runserver
```

## Advanced: AI features

Three things use an AI model, all off until you configure a key, and none required to use Orch:

- Each profile has an optional "smart fallback match" setting. If enabled, files that match no subject code and no topic keyword get one more pass through an AI classifier before falling back to `_Unsorted`.
- Document summaries (the "Summarize" button on a sorted PDF or Word file) always need a key, since there is no non-AI fallback for that feature.
- Course guides (the "Guide" button on a course unit token) also always need a key. These are general academic overviews grounded only in the course code and program context, explicitly not claiming to be an official syllabus.

All three use the same Groq OpenAI-compatible API and the same key: copy `ai_config.example.json` to `ai_config.json` in the project root (or next to the built exe) and fill it in. `ai_config.json` is gitignored and never committed.

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
