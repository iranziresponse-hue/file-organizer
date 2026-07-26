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

    function tick() {
        fetch('/api/status-bar/', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(render)
            .catch(function () {})
            .then(function () {
                setTimeout(tick, POLL_MS);
            });
    }

    tick();
})();
