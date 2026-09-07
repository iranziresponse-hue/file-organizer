// Shared polling helper for organizer.core.jobs.enqueue()-based endpoints
// (MUELE sync, timetable sync, large folder sort, and anything else that
// returns {ok: true, task_id: N} instead of blocking). Polls the task's
// status URL until the BackgroundTask reaches a terminal state.
//
// statusUrlTemplate must be a real Django-rendered URL for this task's
// status endpoint with a placeholder pk in it, e.g. in a template:
//   {% url 'task_status' 999999999 %}
// so this keeps working under a path prefix (Orch hosted at /orch/, a
// reverse proxy, etc.) instead of a hardcoded '/api/tasks/' guess. Falls
// back to that hardcoded guess only if a caller doesn't pass one, for
// backwards compatibility.
//
// Failure handling (added after an audit found this retried a dead request
// forever with no ceiling, making a hung sync look identical to a working
// one):
//   - transient fetch failures back off exponentially, with a cap
//   - after `maxFailures` consecutive failures polling STOPS and
//     `onStalled` fires with { reason: 'unreachable', retry, cancel }
//   - a task that stays non-terminal with no progress change for
//     `stallAfterMs` also stops and fires `onStalled` with
//     { reason: 'stalled', retry, cancel }
//   - `retry()` resumes a fresh polling run; `cancel()` leaves it stopped
// A caller that passes no `onStalled` gets a plain error toast, so every
// existing call site still surfaces a stall instead of hanging silently.
var ORCH_TASK_PLACEHOLDER_PK = '999999999';

function orchPollTask(taskId, opts) {
    opts = opts || {};
    var intervalMs = opts.intervalMs || 1200;
    var maxBackoffMs = opts.maxBackoffMs || 30000;
    var maxFailures = opts.maxFailures || 6;
    var stallAfterMs = opts.stallAfterMs || 90000;
    var onDone = opts.onDone || function () {};
    var onFailed = opts.onFailed || function () {};
    // Fired on every poll, including non-terminal ones ("running",
    // "cancelling") -- for a live progress display. "cancelled" counts as
    // done (a clean stop, not an error); check data.status inside onDone
    // if the two need to look different.
    var onProgress = opts.onProgress || function () {};
    var onStalled = opts.onStalled || function (info) {
        var msg = info.reason === 'unreachable'
            ? 'Lost contact with Orch while this was running. It may still be working in the background.'
            : 'This is taking longer than expected. It may still be running in the background.';
        if (window.showToast) {
            window.showToast(msg, 'error');
        }
    };

    var statusUrl = opts.statusUrlTemplate
        ? opts.statusUrlTemplate.replace(ORCH_TASK_PLACEHOLDER_PK, taskId)
        : '/api/tasks/' + taskId + '/';

    var stopped = false;
    var failures = 0;
    var lastSignature = null;
    var lastChangeAt = Date.now();
    var timer = null;

    function stop() {
        stopped = true;
        if (timer) { clearTimeout(timer); timer = null; }
    }

    function control() {
        return {
            retry: function () {
                if (!stopped) return;
                stopped = false;
                failures = 0;
                lastChangeAt = Date.now();
                tick();
            },
            cancel: function () { stop(); },
        };
    }

    function backoffDelay() {
        // 1x, 2x, 4x, ... intervalMs, capped, with a little jitter so many
        // tabs/tasks don't all retry on the same tick.
        var base = Math.min(maxBackoffMs, intervalMs * Math.pow(2, failures));
        return base + Math.floor(Math.random() * 250);
    }

    function schedule(delay) {
        if (stopped) return;
        timer = setTimeout(tick, delay);
    }

    function signatureOf(data) {
        return [data.status, data.progress_current, data.progress_total, data.result_message].join('|');
    }

    function tick() {
        if (stopped) return;
        fetch(statusUrl, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (data) {
                failures = 0;
                onProgress(data);

                if (data.status === 'done' || data.status === 'cancelled') {
                    stop();
                    onDone(data);
                    return;
                }
                if (data.status === 'failed') {
                    stop();
                    onFailed(data);
                    return;
                }

                var sig = signatureOf(data);
                if (sig !== lastSignature) {
                    lastSignature = sig;
                    lastChangeAt = Date.now();
                } else if (Date.now() - lastChangeAt >= stallAfterMs) {
                    stop();
                    onStalled({ reason: 'stalled', retry: control().retry, cancel: control().cancel });
                    return;
                }
                schedule(intervalMs);
            })
            .catch(function () {
                failures += 1;
                if (failures >= maxFailures) {
                    stop();
                    onStalled({ reason: 'unreachable', retry: control().retry, cancel: control().cancel });
                    return;
                }
                schedule(backoffDelay());
            });
    }
    tick();

    return { stop: stop, retry: function () { control().retry(); } };
}
