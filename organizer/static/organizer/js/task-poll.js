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
var ORCH_TASK_PLACEHOLDER_PK = '999999999';

function orchPollTask(taskId, opts) {
    opts = opts || {};
    var intervalMs = opts.intervalMs || 1200;
    var onDone = opts.onDone || function () {};
    var onFailed = opts.onFailed || function () {};
    // Fired on every poll, including non-terminal ones ("running",
    // "cancelling") -- for a live progress display. "cancelled" counts as
    // done (a clean stop, not an error); check data.status inside onDone
    // if the two need to look different.
    var onProgress = opts.onProgress || function () {};

    var statusUrl = opts.statusUrlTemplate
        ? opts.statusUrlTemplate.replace(ORCH_TASK_PLACEHOLDER_PK, taskId)
        : '/api/tasks/' + taskId + '/';

    function tick() {
        fetch(statusUrl, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                onProgress(data);
                if (data.status === 'done' || data.status === 'cancelled') {
                    onDone(data);
                } else if (data.status === 'failed') {
                    onFailed(data);
                } else {
                    setTimeout(tick, intervalMs);
                }
            })
            .catch(function () {
                setTimeout(tick, intervalMs);
            });
    }
    tick();
}
