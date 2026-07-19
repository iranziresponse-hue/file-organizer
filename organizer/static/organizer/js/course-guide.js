(function () {
    var overlay = document.getElementById('course-guide-overlay');
    if (!overlay) return;

    var body = document.getElementById('course-guide-body');
    var meta = document.getElementById('course-guide-meta');
    var closeBtn = document.getElementById('course-guide-close');
    var downloadLink = document.getElementById('course-guide-download');

    function hide() { overlay.hidden = true; }

    function getCsrfToken() {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    function urlBase(profileId, code) {
        return '/profiles/' + profileId + '/courses/' + encodeURIComponent(code) + '/guide';
    }

    function showGuide(profileId, code) {
        overlay.hidden = false;
        meta.textContent = '';
        body.innerHTML = '<p>Loading...</p>';
        downloadLink.href = urlBase(profileId, code) + '.pdf';

        fetch(urlBase(profileId, code) + '/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    body.innerHTML = '<p>' + data.error + '</p>';
                    return;
                }
                meta.textContent = 'General guide for ' + data.course_code + ' - generated ' + data.created_at + '. Not an official syllabus.';
                body.innerHTML = data.html;
            })
            .catch(function () {
                body.innerHTML = '<p>Could not load this guide. Try again.</p>';
            });
    }

    function generateGuide(profileId, code, btn) {
        var originalText = btn.textContent;
        btn.textContent = 'Generating...';
        btn.disabled = true;

        fetch(urlBase(profileId, code) + '/generate/', {
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
                btn.textContent = code;
                btn.dataset.hasGuide = 'true';
                showGuide(profileId, code);
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = originalText;
                window.alert('Something went wrong generating this guide. Try again.');
            });
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.course-guide-btn');
        if (!btn) return;
        var profileId = btn.dataset.profileId;
        var code = btn.dataset.courseCode;
        if (btn.dataset.hasGuide === 'true') {
            showGuide(profileId, code);
        } else {
            generateGuide(profileId, code, btn);
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
