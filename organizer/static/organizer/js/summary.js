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

    function showSummary(moveId) {
        overlay.hidden = false;
        meta.textContent = '';
        body.innerHTML = '<p>Loading…</p>';
        downloadLink.href = '/moves/' + moveId + '/summary.pdf';

        fetch('/moves/' + moveId + '/summary/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    body.innerHTML = '<p>' + data.error + '</p>';
                    return;
                }
                meta.textContent = data.filename + ' · generated ' + data.created_at;
                body.innerHTML = data.html;
            })
            .catch(function () {
                body.innerHTML = '<p>Could not load this summary. Try again.</p>';
            });
    }

    function generateSummary(moveId, btn) {
        var originalText = btn.textContent;
        btn.textContent = 'Generating…';
        btn.disabled = true;

        fetch('/moves/' + moveId + '/summarize/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btn.disabled = false;
                if (data.error) {
                    btn.textContent = originalText;
                    window.alert(data.error);
                    return;
                }
                btn.textContent = 'View summary';
                btn.dataset.action = 'view';
                showSummary(moveId);
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = originalText;
                window.alert('Something went wrong generating this summary. Try again.');
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
