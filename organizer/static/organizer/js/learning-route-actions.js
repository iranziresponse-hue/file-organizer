// Realtime "Mark done" for Learning Route steps. Same approach as
// inbox-actions.js: submit via fetch(), then read the server's own
// re-rendered page as the source of truth for whether the step actually
// got marked done, rather than guessing from the HTTP status (the view
// always redirects back to this page either way). Anything unexpected
// falls back to a real page load.
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

    function handleSubmit(e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-learning-action')) return;

        e.preventDefault();
        var routePk = form.querySelector('[name="route_pk"]').value;
        var stepIndex = form.querySelector('[name="step_index"]').value;
        var body = new FormData(form);

        fetch(form.action || window.location.href, { method: 'POST', body: body, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) throw new Error('Request failed: ' + response.status);
                return response.text();
            })
            .then(function (html) {
                var freshDoc = new DOMParser().parseFromString(html, 'text/html');
                var selector = '[data-route-pk="' + routePk + '"][data-step-index="' + stepIndex + '"]';
                var freshStep = freshDoc.querySelector(selector);
                var freshActions = freshStep ? freshStep.querySelector('.profile-actions') : null;

                if (!freshActions || freshActions.querySelector('form[data-learning-action]')) {
                    // The server's own response still shows this step as not
                    // done -- the request didn't do what it looked like it
                    // would. Reload for real so the authoritative state and
                    // any error message show.
                    window.location.reload();
                    return;
                }

                syncMessages(freshDoc);

                var liveActions = document.getElementById('step-actions-' + routePk + '-' + stepIndex);
                if (liveActions) liveActions.innerHTML = freshActions.innerHTML;

                var freshSummary = freshDoc.getElementById('route-summary-' + routePk);
                var liveSummary = document.getElementById('route-summary-' + routePk);
                if (freshSummary && liveSummary) liveSummary.textContent = freshSummary.textContent;
            })
            .catch(function () {
                form.submit();
            });
    }

    document.addEventListener('submit', handleSubmit);
})();
