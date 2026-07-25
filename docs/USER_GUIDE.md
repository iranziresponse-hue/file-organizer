# Orch user guide

Orch is a Windows desktop app that watches your Downloads folder and files
every download away automatically, then builds a "study cockpit" on top of
what it's sorted: summaries, review scheduling, deadlines, and course
guides. This guide covers every page in that cockpit, what each Settings
field actually controls, and what to do when Orch tells you something isn't
configured yet.

If you just want to install and run it, see the [README](../README.md)
first. This guide assumes it's already running.

## Contents

- [First run](#first-run)
- [The setup checklist](#the-setup-checklist)
- [Dashboard](#dashboard)
- [Study cockpit](#study-cockpit)
  - [Timeline](#timeline)
  - [Digests](#digests)
  - [Subjects](#subjects)
  - [Reviews](#reviews)
  - [Resources](#resources)
  - [Routes](#routes)
  - [Decision inbox](#decision-inbox)
  - [Folder rules](#folder-rules)
  - [Import plans](#import-plans)
  - [Undo](#undo)
  - [Export bundles](#export-bundles)
- [Settings](#settings)
- [Profiles](#profiles)
- [MUELE integration (Makerere students)](#muele-integration-makerere-students)
- [AI features](#ai-features)
- [Contact support](#contact-support)
- [The owner console (admin account)](#the-owner-console-admin-account)
- [When something isn't configured](#when-something-isnt-configured)
- [Where your data lives](#where-your-data-lives)

## First run

The first time Orch runs, it has no profile yet, so it opens straight to
`/study/setup/`, the setup checklist. There are two ways to create your
first profile from there:

- **Makerere University** — a guided flow: pick your real college, school,
  and programme (searchable, matched against each college's actual site),
  then your year and semester. Orch builds the folder structure and
  suggests that semester's real course units for you.
- **Manual setup** — a three-step wizard (purpose, folder structure,
  sorting behavior) for any other use: a non-Makerere school, online
  courses, work training, research, or something custom.

Either path also needs you to point your browser's download location at the
folder Orch actually watches — Orch only ever sees files that land there.
The first-run page walks through that.

## The setup checklist

`/study/setup/` (also reachable as **Setup** from the study cockpit's quick
nav) is the one page that tells you, plainly, what Orch still needs from
you. Each row is either done (green check) or not, with a **Set up** button
that jumps straight to the right page. It checks, in order:

1. **A profile exists.** Nothing else works without one.
2. **A downloads folder is set**, and that the folder actually still
   exists on disk (if it was moved or deleted, this shows a warning
   instead of silently failing later).
3. **The profile has subjects/groups configured**, so files have somewhere
   to route to.
4. **The file watcher is active** (on by default from the tray icon).
5. **AI features** — optional, shown as not-done until `ai_config.json`
   exists, never blocks anything else.
6. **MUELE connected** — only shown for Makerere profiles.
7. **Owner account created** — only shown at all if owner mode has been
   turned on (see [the owner console](#the-owner-console-admin-account)).
   Regular installs never see this row.

The progress bar at the top is `done / total`, where AI is excluded from
the denominator since it's optional by design.

## Dashboard

The dashboard (`/`, the app's default page once a profile exists) shows:

- **Per-method stat boxes** — how many files were sorted by subject match,
  keyword match, AI fallback, MUELE sync, etc., each with the exact
  filename and timestamp of the most recent one of that kind, not just a
  count.
- **MUELE panel** (Makerere profiles only) — most recently synced course,
  nearest assignment deadline with its real due date, and exact last-sync
  time, all pulled live from the database, never estimated.
- **Recent Moves table** — every move Orch has made, paginated and
  searchable (type into the search box above it to filter by filename
  instantly, no page reload). Each row shows the exact drive and folder a
  file landed in, plus a **Move** button to relocate it yourself through
  the same folder picker used everywhere else, even long after it was
  sorted, and a **Summarize** button next to any PDF/Word file (see
  [AI features](#ai-features)).

Every real move also fires a notification, both as a tray toast and as a
permanent record on the Notifications page (`/study/notifications/`),
naming the file and its destination drive, so nothing that happens is
silent or hard to trace back later.

## Study cockpit

`/study/` is the hub for everything past initial sorting — a grid of
cards linking to the pages below, plus the same quick-nav pills at the top
of most study pages (Packs, Digests, Subjects, Resources, Routes, Reviews,
Inbox, Rules, Imports, Setup, Timeline).

### Timeline

`/study/timeline/` — a chronological feed of everything that's happened:
files sorted, summaries generated, reviews completed, MUELE syncs, digests
created. Filterable by activity type and by time window (week / month /
quarter / all).

### Digests

`/study/digests/` — periodic study digests: metrics for a day or week
(files sorted, reviews due, subjects touched, assignments opened), a
subject breakdown, and a notification when one's ready. Click into any
digest for the full detail view.

### Subjects

`/study/subjects/` — one dashboard per subject: detected themes (topics
Orch has picked up from your files' content), recent activity, and how
current each subject's "memory" is. Click a subject to open its full
[subject memory](#subject-memory-detail) page: resources, focus themes,
assignments, activity timeline, and pending reviews for that one subject.

### Reviews

`/study/reviews/` — a spaced-repetition queue. **Auto-schedule from
files** seeds it from your recently sorted material; each item can be
marked **Done** (schedules the next review at the right interval) or
**Skip**. Broken down by priority and by subject.

### Resources

`/study/resources/` — suggested further reading/watching, generated from
your subject memory, detected themes, and weak areas. Every suggestion is
a transparent search/discovery link, not a claim that Orch found a
specific real video or book — save the ones worth keeping, dismiss the
rest.

### Routes

`/study/routes/` — turns a weak area into a sequenced, step-by-step study
path (a "learning route"), built from a recommendation and tracked
step-by-step with a **Mark done** action per step.

### Decision inbox

`/study/inbox/` — files a folder rule flagged for manual approval instead
of routing automatically (low confidence match, or a rule explicitly set
to ask first). Each pending item can be **Approved** (goes where
suggested), **Rerouted** (pick a different destination folder), or
**Ignored**.

### Folder rules

`/study/rules/` — a visual rule builder for custom routing logic beyond
the default subject/keyword matching, with a live **Test** button to check
a rule against a sample filename before saving it.

### Import plans

`/study/import/` — for folders you already had before installing Orch:
point it at an existing folder, review the plan Orch proposes for
reorganizing what's already there, then **Approve** or **Reject** each
part before anything actually moves.

### Undo

`/study/undo/` — every move Orch makes is reversible. Lists recently moved
files with a **Restore** button per file (moves it back to exactly where
it came from), plus a **Restore last hour** bulk action.

### Export bundles

`/study/exports/` — packages a subject's sorted files and summaries into a
portable "knowledge pack" you can download as a single archive, useful for
backing up or handing off a subject's material.

## Settings

`/settings/` controls the paths Orch actually watches — nothing here is
hardcoded to one machine:

| Field | What it controls |
|---|---|
| Downloads folder | The primary folder Orch watches for new files. Defaults to your Windows user's real Downloads folder the first time the app runs. |
| Secondary downloads folder | An optional second folder to watch (e.g. a browser configured to save elsewhere). Leave blank to disable. |
| Library inbox folder | Where ebooks and other library-type files land, independent of any profile. |
| Installer "stale" days | How many days an installer file (e.g. a `.exe`/`.msi` in Downloads) sits untouched before Orch treats it as stale. |
| Installer delete days | How many days after that before Orch offers to delete it outright. |

Each has a **Browse...** button that opens a real file-system picker
against this machine — never type a path from memory.

## Profiles

`/profiles/` lists every profile you've created (School, Online courses,
Work training, Research, Certifications, or custom); only one is **active**
at a time, and switching is one click. Each profile has its own folder, own
group labels (a student might call them "Year"/"Semester"; an online
learner might use "Year"/"Bootcamp"), own subject list, and own dashboard
data — profiles never share files or history with each other.

**Subject folders** are created automatically whenever you save a profile
(from the wizard or the edit page): one folder per subject/course unit,
under `<profile folder>\<primary group>\<secondary group>\<subject code>`.
Already have some of them from before installing Orch? Nothing is
duplicated or overwritten — Orch only creates the ones that are missing.
If you add subjects later without resaving, "Check for missing subject
folders" on the profile's edit page does the same check on demand.

## MUELE integration (Makerere students)

MUELE is Makerere University's Moodle-based e-learning platform. For a
Makerere profile, `/integrations/muele/connect/` connects Orch to your real
MUELE account so it can sync course files, assignment deadlines, and
calendar events automatically. Two ways to authenticate:

- **Log in to MUELE** (primary) — enter your real MUELE username and
  password once; Orch exchanges them for a token and never stores the
  password itself.
- **Manual token entry** (fallback, secondary) — for a token generated
  another way.

Once connected, that same `/integrations/muele/connect/` page leads with a
clear "MUELE is connected" state instead of the login form — the login/token
forms are still there for reconnecting after a session timeout, just tucked
behind a "Reconnect MUELE" toggle instead of shown as if nothing had
happened yet. `/integrations/muele/courses/` lists your synced courses with
a toggle per course for automatic file downloads, and settings for which
colleges/sync targets (course files, assignments, calendar) are active.

## AI features

Three things use an AI model, every one of them off until you configure a
key, and none required for Orch's core file-sorting to work:

- **Smart fallback match** (per-profile setting) — if a file matches no
  subject code and no keyword, one more pass through an AI classifier
  before it falls back to `_Unsorted`.
- **Document summaries** — the **Summarize** button next to a sorted
  PDF/Word file on the dashboard or a subject page. Always needs a key;
  there's no non-AI fallback for this one.
- **Course guides** — the **Guide** button on a course-unit chip. A
  general academic overview grounded only in the course code and
  programme context, explicitly not a claim to be an official syllabus.

All three share one Groq API key, set from **Settings → AI features**:
check the enable box, paste a key, save. Settings links directly to the
steps for getting a free key from Groq's console if you don't have one
yet. Until a key is set, the setup checklist shows AI features as not
configured, but nothing else is blocked.

## Contact support

The circular button in the bottom-right corner of every page opens a small
form (name and email optional, message required) that sends straight to
Orch's support inbox. The message is always saved locally first, so it's
never lost even before email sending is set up — see
`support_email.example.json` for the SMTP settings that make the "send"
half actually work. Without that file, messages still save; they just stay
local until support_email.json exists.

## The owner console (admin account)

The owner console is a **hidden, opt-in troubleshooting tool** — not shown
to regular users, and not needed to use Orch day to day. It gives access to
Django's real admin site (`/admin/` via `/owner/`), useful for the app's
author or a tester inspecting the raw database directly.

It's off by default and gated two ways at once: the request must come from
this machine (`127.0.0.1`), **and** owner mode must be explicitly turned
on. To turn it on, create a file named `orch-owner.json` next to the exe
(copy `owner_config.example.json` and rename it) containing:

```json
{ "owner_mode": true }
```

(Or set the environment variable `ORCH_OWNER_MODE=1` before launching, if
you'd rather not leave a file behind.)

With owner mode on:

1. Open `http://127.0.0.1:8765/owner/` in a browser on the same machine.
2. If no admin account exists yet, you're redirected to `/owner/setup/` —
   a real form (username, email, password) that creates the first Django
   superuser. This exists because a windowed exe has no console to run
   `manage.py createsuperuser` from.
3. After that, `/owner/` always redirects straight to the Django admin
   (`/admin/`), where every model — profiles, move events, summaries,
   integration connections, everything — is browsable and editable
   directly.

Turn `owner_mode` back off (or delete `orch-owner.json`) once you're done;
there's no reason to leave the admin site reachable on a machine that
doesn't need it. The setup checklist only shows the "Owner account
created" row while owner mode is on, so it won't nag a regular install
about a feature it isn't using.

## When something isn't configured

Orch is built to say what's wrong instead of failing silently or showing a
raw crash:

- **No profile / no downloads folder / no subjects** — the setup checklist
  at `/study/setup/` lists exactly which of these is missing, with a
  direct link to fix each one. Orch also redirects here automatically on
  first run.
- **A configured folder no longer exists** (moved or deleted on disk) —
  flagged with a warning on the checklist instead of quietly doing
  nothing.
- **AI features used without a key** — every AI-backed button (Summarize,
  Guide, smart fallback) reports the real reason if it fails: no key
  configured, request too large, rate-limited, or a bad key, never a bare
  "something went wrong."
- **MUELE not connected, or its session expired** — the MUELE panel and
  courses page say so directly and link to reconnect, rather than syncing
  silently failing.
- **An unexpected error anywhere else** — shows an Orch-branded page
  instead of Django's raw debug traceback, with a pointer to "Open log"
  from the tray icon for details. (Set `"debug": true` in
  `secret_config.json` to see full tracebacks instead, for local
  development only — never do this on a machine other people use.)

## Where your data lives

Everything Orch needs to keep between runs lives next to the exe (or in the
project root in dev), never inside a temp folder that gets wiped:

- `db.sqlite3` — every profile, move event, summary, digest, and setting.
- `secret_config.json` — this install's Django secret key and debug flag,
  generated automatically on first run.
- `ai_config.json` — your AI API key, if configured. Never committed to git.
- `orch-owner.json` — owner console toggle, if you've enabled it.
- `organize-log.txt` (in your Documents\Scripts folder) — a plain-text log
  of every move and every error, reachable from the tray icon's "Open log."
