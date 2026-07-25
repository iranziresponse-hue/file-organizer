# Orch

A Django + PyQt6 desktop app for Windows, by **Iranzi**, that organizes
learning files and turns what it's sorted into a full study cockpit: point
it at a folder, tell it what you're organizing, and it routes every
download to the right place automatically, then layers summaries, review
scheduling, deadlines, and course guides on top.

## Download and run (GitHub Releases)

Grab the latest `Orch.exe` from this repo's
[Releases](../../releases) page and run it directly — no install, no
Python required. On first launch it opens the setup checklist so you can
create your first profile. There's also a landing page in
[site/](site/) (see below) with the same download link and a walkthrough
of every feature with screenshots.

The exe is a single file that carries its own state next to it
(`db.sqlite3`, config files) — run it from a normal folder you have write
access to, not a read-only location. See
[docs/USER_GUIDE.md](docs/USER_GUIDE.md) for a full walkthrough of every
page, and the [admin console section below](#admin-console-owner-mode) if
you're setting one up for testing.

## What it does

Orch runs as a system tray app that watches your Downloads folder (and a
second configurable download location) and moves each new file to where it
belongs, without you having to do it by hand.

**Profiles.** A profile is a context: School, Online courses, Work
training, Research, Certifications, or anything custom. Each profile has
its own folder, its own group labels (a student calls them "Year" /
"Semester", an online learner might call them "Year" / "Bootcamp"), its own
subject list, and its own dashboard. Only one profile is active at a time,
and switching is one click.

**Routing.** Within the active profile, documents get sorted by subject
code or topic keyword into `<profile folder>\<primary group>\<secondary
group>\<subject>\<category>`, with the category (lecture notes,
assignments, past papers, reports, or reference material) detected from
the filename. Ebooks, media files, installers, archives, sensitive files
(passwords, keys, certificates), and loose code/project files each get
their own destination, independent of any profile.

**History.** Every move is logged both to a text log file and to a Django
database table, so there is a searchable, per-profile history of what got
moved where and why, surfaced on a dashboard.

**Setup wizard.** A three-step flow (purpose, structure, sorting behavior)
gets a new profile running in under a minute. Subject codes are added as
removable chips, not a comma-separated text blob, and group labels suggest
common presets ("Year", "Topic", "Department"...) while still taking
anything you type.

**Connects to folders you already have.** A "Browse..." button opens your
real file system to point a profile at an existing folder, no typing paths
from memory. Once picked, Orch reads what's already inside it: the
primary/secondary group fields suggest folders that already exist there
(e.g. "Year 2", "Semester 1"), and the subject list suggests the
subfolders already sitting under those, one click to adopt them instead of
retyping.

**Settings.** Nothing is hardcoded to one machine. Which folders get
watched, where ebooks land, and AI features (on/off and the API key) are
all editable from a Settings page, defaulted sensibly to your own Windows
user profile the first time the app runs.

**Dashboard.** Every move is logged with the exact drive, folder, method,
and timestamp, so nothing about where a file went is ever a guess. A
"Move" button next to any sorted file lets you relocate it yourself
through the same folder picker used everywhere else, even long after it
was sorted. Instant search narrows the list to matching filenames as you
type. A notification fires for every real move, visible both as a tray
toast and in the permanent notification history.

**Study cockpit.** Past initial sorting, Orch layers on a full study
workflow: a learning timeline, periodic digests, per-subject "memory"
dashboards with detected themes, a spaced-repetition review queue,
transparent resource discovery links, sequenced learning routes for weak
areas, a decision inbox for files that need manual approval, a visual
folder-rule builder, an import flow for folders you already had before
installing Orch, one-click undo on every move, and exportable "knowledge
pack" bundles per subject. See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for
what every page does.

**Document summaries.** Next to any sorted PDF or Word document, a
"Summarize" button generates a long, structured study companion, not a
one-line blurb. It reads the actual file, pulls in the other summarizable
files already sitting in the same destination folder, and writes a piece
with a real hook, a detailed breakdown of the content, and a dedicated
section connecting it to those related files. View it in a scrollable
popup or download it as a formatted PDF. This is an AI feature (see
below), off until you configure a key.

**Makerere University setup.** The first time you create a profile, Orch
asks whether you're a Makerere student. If so, a guided flow walks through
your real college, school, and program (typeahead search across all 10
colleges and every school in them, verified directly against each
college's official site, not a plain scrolling dropdown), then your year,
semester, and this semester's real course units, and builds the folder
structure for you. Every course unit gets its own "Guide" button: a long,
AI-generated academic overview of what a course like that typically
covers, clearly presented as general guidance rather than an official
syllabus. Makerere profiles can also connect to **MUELE** (the
university's Moodle-based e-learning platform) to sync course files,
assignment deadlines, and calendar events automatically.

**Get your downloads flowing to Orch.** The first-run page walks through
pointing your browser's (and other apps') default download location at
the folder Orch watches, since Orch only ever sees files that land there.

**Contact support.** A floating button on every page opens a small form
that sends a message straight to Orch's support inbox. The message is
always saved locally first, so nothing is lost even before SMTP is set up
(see `support_email.example.json`).

## Admin console (owner mode)

Orch ships a hidden, opt-in admin console for troubleshooting and
inspecting the database directly through Django's real admin site — off by
default, and not something a regular user ever needs to touch. To set one
up (e.g. for testing a downloaded release build):

1. Next to the exe, copy `owner_config.example.json` to `orch-owner.json`
   and set `"owner_mode": true` (or set the environment variable
   `ORCH_OWNER_MODE=1` before launching).
2. Open `http://127.0.0.1:8765/owner/` in a browser on the same machine.
3. First time, you'll land on `/owner/setup/` to create the admin account
   (username/email/password) — a real in-app form, since a windowed exe
   has no console to run `manage.py createsuperuser` from.
4. After that, `/owner/` redirects straight into `/admin/`.

Both the localhost check and the `owner_mode` flag are required — full
detail in [docs/USER_GUIDE.md](docs/USER_GUIDE.md#the-owner-console-admin-account).

## Tech stack

- **Django** provides the data model, the admin site, the dashboard, and a
  small read-only local API (`/api/browse-folders/`) that lets the UI
  browse this machine's real folders. The dashboard only ever binds to
  `127.0.0.1` (see `gui/server.py`), so this never leaves the machine.
- **PyQt6** provides the desktop shell: a taskbar-visible window
  (`gui/main_window.py`) that embeds the real dashboard directly via
  `QWebEngineView` and opens automatically on launch, plus a system tray
  icon for background controls (start/stop the watcher, pause, open the
  log, toggle launch-at-startup) that keeps running when the window is
  closed. The window quietly re-fetches its current page every few
  seconds so newly sorted files and notifications show up without a
  manual refresh, without disrupting anything you're actively typing.
- The watcher itself is a polling loop, not a filesystem-events watcher,
  because a `FileSystemWatcher`/`Register-ObjectEvent` approach in the
  original PowerShell version this was ported from was found to silently
  stop firing when run as a detached background process.
- `main.py` runs Django's migrations and dashboard server on background
  threads inside the same process as the tray icon, so the packaged exe
  needs no separate `manage.py` steps.
- The whole app is packaged into a single Windows `.exe` with PyInstaller,
  targeting `main.py`.

## Project layout

```
config/                     Django project settings, URLs, WSGI/ASGI entry points
docs/
    USER_GUIDE.md            What every page does, Settings fields, owner console setup
gui/
    app.py                   Desktop entry point: django.setup(), migrate, tray, dashboard server
    tray.py                  System tray icon and menu
    main_window.py           Minimal native shell window (TopBar + status panel)
    topbar.py                Floating translucent top bar for the native shell
    server.py                Runs the Django dashboard on a background thread
    watcher_controller.py    Starts/stops the watcher on a background thread
    muele_controller.py      MUELE sync orchestration from the desktop side
    autostart.py             Windows launch-at-login toggle (per-user registry key)
    assets.py                Resolves bundled asset paths, dev and PyInstaller alike
organizer/
    models.py                Profile, CourseConfig, MoveEvent, FileSummary, CourseGuide, and the study-cockpit models
    views.py                  Dashboard, wizards, settings, study cockpit, MUELE, owner console
    admin.py                  Django admin registrations
    core/
        paths.py               Filesystem paths/constants not specific to any one profile
        rules.py                Pure destination-decision logic (no Django imports, unit-testable)
        ai_classify.py          Optional, off-by-default AI fallback classifier
        summarize.py            Long-form AI document summaries and course guides
        makerere.py             Verified Makerere University college/school/programme structure, with sources
        makerere_curricula.py   Per-programme, per-semester course units
        muele_api.py            MUELE (Moodle) authentication and API calls
        muele_sync.py           MUELE course/assignment/calendar sync
        digest.py               Daily/weekly study digest generation
        learning_route.py       Sequenced study paths for weak areas
        resources.py            Transparent resource discovery links
        sorting.py               Decision inbox and folder-rule matching
        undo.py                  Move restoration
        owner_access.py          Local-only gate for the admin console
        watcher.py               The polling watcher loop and move/cleanup logic
    static/organizer/img/      The Orch mark (favicon, tray icon, exe icon)
    static/organizer/js/       Small vanilla-JS widgets and realtime AJAX handlers
    templates/                 404/500 error pages (Orch-branded, shown when DEBUG is off)
    templates/organizer/       Dashboard, wizards, study cockpit, settings, and profile templates
    tests/                    Unit and view-level tests
main.py                      Desktop app entry point (python main.py, or the PyInstaller target)
runtime.py                   Resolves persistent-state paths, dev root vs. exe-adjacent when frozen
version_info.txt             Windows exe version resource (company, product, file description)
Orch.spec                    PyInstaller build spec
```

## Setup (running from source)

```
pip install -r requirements.txt
python main.py
```

This runs migrations automatically, starts the dashboard on
`http://127.0.0.1:8765/`, puts a tray icon in the system tray, and opens
Orch's main window. On first launch that window opens straight to the
setup checklist so you can create your first profile.

If you just want the Django dashboard on its own, without the tray app or
the watcher:

```
python manage.py migrate
python manage.py runserver
```

## Configuration files (all gitignored, none committed)

| File | Purpose | Example to copy |
|---|---|---|
| `secret_config.json` | Django secret key and debug flag | auto-generated on first run |
| `ai_config.json` | AI (Groq) API key for summaries/guides | Set from Settings → AI features in-app, or `ai_config.example.json` by hand |
| `orch-owner.json` | Turns on the admin console | `owner_config.example.json` |
| `support_email.json` | SMTP credentials for the support popup (recipient is always iranziresponse@gmail.com) | `support_email.example.json` |

`secret_config.json` doesn't need an example file — Orch generates one
itself the first time it runs, with a real random secret key and
`"debug": false`, so a downloaded exe never shows Django's raw
debug/traceback pages to whoever's running it. Set `"debug": true` by hand
only for local development.

## Advanced: AI features

Three things use an AI model, all off until you configure a key, and none
required to use Orch:

- Each profile has an optional "smart fallback match" setting. If enabled,
  files that match no subject code and no topic keyword get one more pass
  through an AI classifier before falling back to `_Unsorted`.
- Document summaries always need a key, since there is no non-AI fallback
  for that feature.
- Course guides also always need a key. These are general academic
  overviews grounded only in the course code and program context,
  explicitly not claiming to be an official syllabus.

All three use the same Groq OpenAI-compatible API and the same key: set it
from **Settings → AI features** in the app itself (enable the toggle, paste
a key, save) -- Settings links to the exact steps for getting a free Groq
key from there. `ai_config.example.json` still documents the underlying
file format if you'd rather edit `ai_config.json` by hand.

## Tests

```
python manage.py test
```

Every test that touches `organizer.core.paths` runs against a throwaway
temp directory (see `organizer/tests/helpers.py`), never against your real
profile folders, Downloads, or Documents.

## Build the Windows app

```
pyinstaller Orch.spec
```

The packaged `.exe`, tray icon, app icon, and dashboard favicon all use the
Orch mark from `organizer/static/organizer/img/`. Exe metadata (company,
product name, file description) comes from `version_info.txt`. The
database and config files live next to the built exe (see `runtime.py`),
so they persist across runs instead of living inside PyInstaller's
temporary extraction folder.

## Landing page

`site/` is a self-contained static marketing page (no build step, no
framework) that pitches Orch to prospective users and links straight to
the latest `Orch.exe`. Preview it locally with:

```
cd site
python -m http.server 8099
```

then open `http://127.0.0.1:8099/`. `render.yaml` at the repo root is a
Render Blueprint that deploys `site/` as a free static site straight from
this repo — free static sites on Render never sleep (that's only a
free-tier *web service* limitation), so no keep-alive cron job is needed.
To deploy: connect this repo in the Render dashboard and pick "New
Blueprint" — it reads `render.yaml` automatically.

The page's screenshots (`site/assets/img/screenshots/`) are real captures
of the running app with representative sample data, not mockups.

## License

Copyright (c) 2026 Iranzi. All rights reserved. See [LICENSE](LICENSE).
