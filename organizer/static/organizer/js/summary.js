(function () {
    var overlay = document.getElementById('summary-overlay');
    if (!overlay) return;

    var body = document.getElementById('summary-body');
    var meta = document.getElementById('summary-meta');
    var closeBtn = document.getElementById('summary-close');
    var downloadLink = document.getElementById('summary-download');

    function hide() { overlay.hidden = true; }

    function getCsrfToken() {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    function viewSummaryIcon() {
        return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 6.5C5 5.1 6.1 4 7.5 4h9C17.9 4 19 5.1 19 6.5v11c0 1.4-1.1 2.5-2.5 2.5h-9C6.1 20 5 18.9 5 17.5v-11Z" stroke="currentColor" stroke-width="1.8"/><path d="M9 9h6M9 12h6M9 15h3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
    }

    function setButtonContent(btn, icon, label) {
        btn.innerHTML = icon + '<span>' + label + '</span>';
    }

    function showSummary(moveId) {
        overlay.hidden = false;
        meta.textContent = '';
        body.innerHTML = '<p>Loading...</p>';
        downloadLink.href = '/moves/' + moveId + '/summary.pdf';

        fetch('/moves/' + moveId + '/summary/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    body.innerHTML = '<p>' + data.error + '</p>';
                    return;
                }
                meta.textContent = data.filename + ' - generated ' + data.created_at;
                body.innerHTML = data.html;
            })
            .catch(function () {
                body.innerHTML = '<p>Could not load this summary. Try again.</p>';
            });
    }

    function generateSummary(moveId, btn) {
        var originalHtml = btn.innerHTML;
        setButtonContent(btn, viewSummaryIcon(), 'Generating...');
        btn.disabled = true;

        fetch('/moves/' + moveId + '/summarize/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btn.disabled = false;
                if (data.error) {
                    btn.innerHTML = originalHtml;
                    window.showToast(data.error, 'error');
                    return;
                }
                setButtonContent(btn, viewSummaryIcon(), 'View summary');
                btn.dataset.action = 'view';
                showSummary(moveId);
            })
            .catch(function () {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
                window.showToast('Something went wrong generating this summary. Try again.', 'error');
            });
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.summarize-btn');
        if (!btn) return;
        var moveId = btn.dataset.moveId;
        if (btn.dataset.action === 'view') {
            showSummary(moveId);
        } else {
            generateSummary(moveId, btn);
        }
    });

    closeBtn.addEventListener('click', hide);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) hide();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !overlay.hidden) hide();
    });
})();
