// Keeps the persistent status bar (base.html's #app-status-bar) fresh
// without a full page reload -- polls the same snapshot shape the bar was
// server-rendered with (organizer.core.status_bar.get_snapshot), so a
// refresh here never looks different from a hard reload.
(function () {
    var bar = document.getElementById('app-status-bar');
    if (!bar) {
        return;
    }

    var POLL_MS = 20000;

    function setItem(id, show) {
        var el = document.getElementById(id);
        if (el) {
            el.hidden = !show;
        }
        return el;
    }

    function render(data) {
        bar.hidden = !data.has_profile;
        if (!data.has_profile) {
            return;
        }

        var watching = document.getElementById('status-bar-watching');
        if (watching) {
            watching.querySelector('.status-bar-text').textContent =
                data.watching ? 'Watching ' + data.watching : 'Not watching a folder';
        }

        var lastMoveEl = setItem('status-bar-last-move', !!data.last_move);
        if (lastMoveEl && data.last_move) {
            lastMoveEl.querySelector('.status-bar-text').textContent = data.last_move;
        }

        var reviewEl = setItem('status-bar-review', !!data.pending_review);
        if (reviewEl) {
            var countEl = document.getElementById('status-bar-review-count');
            if (countEl) {
                countEl.textContent = data.pending_review;
            }
        }

        var sync = document.getElementById('status-bar-sync');
        if (sync) {
            sync.querySelector('.status-bar-text').textContent = data.sync || 'Local only';
        }

        var taskEl = setItem('status-bar-task', !!data.background_task);
        if (taskEl && data.background_task) {
            var label = document.getElementById('status-bar-task-label');
            if (label) {
                var text = data.background_task.label;
                if (data.background_task.progress_total) {
                    text += ' (' + data.background_task.progress_current + '/' + data.background_task.progress_total + ')';
                }
                label.textContent = text;
            }
        }
    }

    var timerId = null;

    function scheduleNext() {
        timerId = setTimeout(tick, POLL_MS);
    }

    function tick() {
        // The window is hidden (minimized to tray) rather than destroyed on
        // close, see gui/main_window.py's _on_closing -- without this check
        // this timer would keep hitting the database every 20s for as long
        // as Orch runs in the background, even while nobody is looking at
        // it. Skip the actual work, just keep the loop alive so it's ready
        // to resume the moment the page is visible again.
        if (document.hidden) {
            scheduleNext();
            return;
        }
        fetch('/api/status-bar/', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(render)
            .catch(function () {})
            .then(scheduleNext);
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            if (timerId) clearTimeout(timerId);
            tick();
        }
    });

    tick();
})();
