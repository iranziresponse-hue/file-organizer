// Realtime Save/Unsave/Dismiss for Resource Radar recommendations. Same
// approach as inbox-actions.js and learning-route-actions.js: submit via
// fetch(), then read the server's own re-rendered page as the source of
// truth for what actually happened, since this view always redirects back
// to the same page either way. Anything unexpected falls back to a real
// page load. "Refresh radar" (generate) is left as a normal full-page
// submit -- it can add, remove, and reorder many rows at once.
(function () {
    function syncMessages(freshDoc) {
        var fresh = freshDoc.getElementById('page-messages');
        var current = document.getElementById('page-messages');
        if (current) {
            if (fresh) {
                current.replaceWith(fresh);
            } else {
                current.remove();
            }
        } else if (fresh) {
            var main = document.querySelector('main');
            if (main) main.insertBefore(fresh, main.firstChild);
        }
    }

    function syncCount(id, freshDoc) {
        var freshEl = freshDoc.getElementById(id);
        var liveEl = document.getElementById(id);
        if (freshEl && liveEl) liveEl.textContent = freshEl.textContent;
    }

    function handleSubmit(e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-radar-action')) return;

        e.preventDefault();
        var pk = form.querySelector('[name="recommendation_pk"]').value;
        var isDismiss = form.querySelector('[name="action"]').value === 'dismissed';
        var body = new FormData(form);

        fetch(form.action || window.location.href, { method: 'POST', body: body, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) throw new Error('Request failed: ' + response.status);
                return response.text();
            })
            .then(function (html) {
                var freshDoc = new DOMParser().parseFromString(html, 'text/html');
                var freshRow = freshDoc.querySelector('.profile-row[data-pk="' + pk + '"]');

                // Dismissed items drop out of the default recommendations
                // query; saved/unsaved ones stay visible either way. If
                // that's not what the server's own response shows, don't
                // guess -- reload for real.
                if (isDismiss ? freshRow : !freshRow) {
                    window.location.reload();
                    return;
                }

                syncMessages(freshDoc);
                syncCount('saved-count', freshDoc);
                syncCount('visible-count', freshDoc);

                if (isDismiss) {
                    var row = document.querySelector('.profile-row[data-pk="' + pk + '"]');
                    if (row) row.remove();
                    if (!document.querySelector('.profile-row[data-pk]')) {
                        window.location.reload();
                    }
                } else {
                    var liveActions = document.getElementById('rec-actions-' + pk);
                    var freshActions = freshRow.querySelector('.profile-actions');
                    if (liveActions && freshActions) liveActions.innerHTML = freshActions.innerHTML;
                }
            })
            .catch(function () {
                form.submit();
            });
    }

    document.addEventListener('submit', handleSubmit);
})();
