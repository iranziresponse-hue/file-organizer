// Realtime Decision Inbox actions. Approve/Ignore/Reroute submit via
// fetch() instead of a full page navigation, then remove that one row --
// no new endpoints, no JSON API. The server still returns the exact same
// full sorting_inbox page it always has; this only reads that response as
// the source of truth (does the item still show up as pending?) rather
// than guessing at success from the HTTP status, since these views always
// redirect back to the same page whether the action worked or not.
//
// Anything unexpected (network failure, item still pending after the
// request, no rows left) falls back to a real page load, so the user
// always ends up looking at the real, server-rendered state.
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

    function syncStats(freshDoc) {
        ['stat-pending', 'stat-approved', 'stat-rerouted', 'stat-ignored'].forEach(function (id) {
            var freshEl = freshDoc.getElementById(id);
            var liveEl = document.getElementById(id);
            if (freshEl && liveEl) liveEl.textContent = freshEl.textContent;
        });
    }

    function handleSubmit(e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-inbox-action')) return;

        e.preventDefault();
        var pk = form.dataset.itemPk;
        var body = new FormData(form);

        fetch(form.action, { method: 'POST', body: body, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) throw new Error('Request failed: ' + response.status);
                return response.text();
            })
            .then(function (html) {
                var freshDoc = new DOMParser().parseFromString(html, 'text/html');

                if (freshDoc.querySelector('[data-pk="' + pk + '"]')) {
                    // The item is still pending in the server's own response --
                    // the action didn't go through. Reload for real so the
                    // authoritative error message shows.
                    window.location.reload();
                    return;
                }

                syncMessages(freshDoc);
                syncStats(freshDoc);

                var overlay = document.getElementById('reroute-form');
                if (overlay) overlay.hidden = true;

                var row = document.querySelector('.profile-row[data-pk="' + pk + '"]');
                if (row) row.remove();

                var countEl = document.getElementById('pending-count');
                var remaining = document.querySelectorAll('.profile-row[data-pk]').length;
                if (countEl) countEl.textContent = String(remaining);

                if (remaining === 0) {
                    // No template for the empty state is loaded on this page --
                    // a real reload shows it correctly.
                    window.location.reload();
                }
            })
            .catch(function () {
                form.submit();
            });
    }

    document.addEventListener('submit', handleSubmit);
})();
