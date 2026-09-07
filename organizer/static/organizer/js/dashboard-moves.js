// Recent Moves card on the dashboard: the "Move to..." dialog, row-action
// menus, the "Why?" disclosure rows, per-row Undo, and the instant-search
// that swaps in a fresh table slice as the user types. Moved verbatim out
// of dashboard.html when that template was split into partials -- behaviour
// is unchanged. No-ops on any page without #move-form.
(function () {
    var overlay = document.getElementById('move-form');
    var filenameEl = document.getElementById('move-filename');
    var form = document.getElementById('move-form-inner');
    var feedback = document.getElementById('move-feedback');
    var submitBtn = document.getElementById('move-submit');
    if (!overlay) return;

    function resetFeedback() {
        feedback.classList.remove('is-success', 'is-danger');
        feedback.textContent = '';
    }

    function hide() { overlay.hidden = true; resetFeedback(); }

    // Re-run after every search swap below, since replacing
    // #recent-moves-body's content wipes out any listeners already
    // attached to the old .move-btn elements it contained.
    function wireMoveButtons() {
        document.querySelectorAll('.move-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeAllMenus();
                filenameEl.textContent = 'Moving: ' + this.dataset.filename;
                form.dataset.movePk = this.dataset.moveId;
                document.getElementById('move_destination').value = '';
                overlay.hidden = false;
            });
        });
    }
    wireMoveButtons();

    function closeAllMenus() {
        if (window.OrchDropdowns) window.OrchDropdowns.close(false);
    }

    function wireRowActionMenus() {
        if (window.OrchDropdowns) window.OrchDropdowns.wire(moveBody || document);
    }
    wireRowActionMenus();

    function wireWhyToggles() {
        (moveBody || document).querySelectorAll('[data-why-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var row = document.getElementById(this.dataset.whyToggle);
                if (!row) return;
                var expanded = this.getAttribute('aria-expanded') === 'true';
                row.hidden = expanded;
                this.setAttribute('aria-expanded', expanded ? 'false' : 'true');
            });
        });
    }
    wireWhyToggles();

    function wireUndoButtons() {
        document.querySelectorAll('.undo-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeAllMenus();
                var filename = this.dataset.filename;
                var pk = this.dataset.moveId;
                window.orchConfirm('Undo this move? "' + filename + '" will go back to where it was found.').then(function (ok) {
                    if (!ok) return;
                    fetch('/moves/' + pk + '/undo/', {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        },
                    })
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                            if (data.ok) {
                                window.location.reload();
                            } else {
                                window.showToast(data.error || 'Could not undo that move.', 'error');
                            }
                        })
                        .catch(function () {
                            window.showToast('Could not reach Orch. Try again.', 'error');
                        });
                });
            });
        });
    }
    wireUndoButtons();

    document.getElementById('move-close').addEventListener('click', hide);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) hide(); });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (submitBtn.disabled) return;
        var pk = form.dataset.movePk;
        submitBtn.disabled = true;
        feedback.classList.remove('is-success', 'is-danger');
        feedback.textContent = 'Moving...';

        fetch('/moves/' + pk + '/relocate/', {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                submitBtn.disabled = false;
                if (data.ok) {
                    feedback.classList.add('is-success');
                    feedback.textContent = 'Moved.';
                    setTimeout(function () { window.location.reload(); }, 600);
                } else {
                    feedback.classList.add('is-danger');
                    feedback.textContent = data.error || 'Could not move that file.';
                }
            })
            .catch(function () {
                submitBtn.disabled = false;
                feedback.classList.add('is-danger');
                feedback.textContent = 'Could not reach Orch. Try again.';
            });
    });

    // Instant search: re-fetches this same page with ?q=<query> as the
    // user types, and swaps in just the fresh table: no submit button,
    // no full page reload, so a search feels immediate.
    var searchInput = document.getElementById('move-search-input');
    var searchShell = document.getElementById('recent-moves-search');
    var searchClear = document.getElementById('move-search-clear');
    var searchStatus = document.getElementById('move-search-status');
    var searchTotal = document.getElementById('recent-moves-total');
    var moveBody = document.getElementById('recent-moves-body');
    var searchTimer = null;
    var searchController = null;
    var searchRunId = 0;

    function setSearchLoading(isLoading) {
        if (searchShell) searchShell.classList.toggle('is-searching', isLoading);
        if (moveBody) moveBody.setAttribute('aria-busy', isLoading ? 'true' : 'false');
    }

    function setSearchStatus(message) {
        if (searchStatus) searchStatus.textContent = message || '';
    }

    function syncSearchControls() {
        if (searchClear) searchClear.hidden = !searchInput.value;
    }

    function countVisibleRows() {
        if (!moveBody) return 0;
        return moveBody.querySelectorAll('table tr').length ? Math.max(0, moveBody.querySelectorAll('table tr').length - 1) : 0;
    }

    function runSearch(query) {
        closeAllMenus();
        var url = new URL(window.location.href);
        var trimmedQuery = query.trim();
        if (trimmedQuery) {
            url.searchParams.set('q', trimmedQuery);
        } else {
            url.searchParams.delete('q');
        }
        url.searchParams.delete('page');

        searchRunId += 1;
        var runId = searchRunId;
        if (searchController) searchController.abort();
        searchController = window.AbortController ? new AbortController() : null;
        setSearchLoading(true);
        setSearchStatus(trimmedQuery ? 'Searching...' : 'Refreshing recent moves...');

        var options = { credentials: 'same-origin' };
        if (searchController) options.signal = searchController.signal;

        fetch(url.toString(), options)
            .then(function (r) { return r.text(); })
            .then(function (html) {
                if (runId !== searchRunId) return;
                var freshDoc = new DOMParser().parseFromString(html, 'text/html');
                var freshBody = freshDoc.getElementById('recent-moves-body');
                if (!freshBody) return;
                moveBody.innerHTML = freshBody.innerHTML;
                var freshTotal = freshDoc.getElementById('recent-moves-total');
                if (freshTotal && searchTotal) searchTotal.textContent = freshTotal.textContent;
                window.history.replaceState({}, '', url.toString());
                wireMoveButtons();
                wireRowActionMenus();
                wireUndoButtons();
                wireWhyToggles();
                var visibleRows = countVisibleRows();
                setSearchStatus(trimmedQuery ? visibleRows + ' visible match' + (visibleRows === 1 ? '' : 'es') : '');
            })
            .catch(function (error) {
                if (error && error.name === 'AbortError') return;
                setSearchStatus('Search could not refresh. Try again.');
            })
            .finally(function () {
                if (runId === searchRunId) setSearchLoading(false);
            });
    }

    if (searchInput) {
        syncSearchControls();
        searchInput.addEventListener('input', function () {
            var query = searchInput.value;
            syncSearchControls();
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () { runSearch(query); }, 200);
        });
        if (searchClear) {
            searchClear.addEventListener('click', function () {
                searchInput.value = '';
                syncSearchControls();
                clearTimeout(searchTimer);
                runSearch('');
                searchInput.focus();
            });
        }
    }
})();
