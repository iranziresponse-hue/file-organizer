(function () {
    var targets = document.querySelectorAll('[data-reveal]');
    if (!('IntersectionObserver' in window) || !targets.length) {
        targets.forEach(function (el) { el.classList.add('is-visible'); });
        return;
    }
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    targets.forEach(function (el) { observer.observe(el); });
})();

(function () {
    var encodedInbox = 'aXJhbnppcmVzcG9uc2VAZ21haWwuY29t';

    function supportInbox() {
        return atob(encodedInbox);
    }

    function buildSupportDialog() {
        var overlay = document.createElement('div');
        overlay.className = 'support-overlay';
        overlay.hidden = true;
        overlay.innerHTML = [
            '<div class="support-dialog" role="dialog" aria-modal="true" aria-labelledby="support-title">',
            '    <button type="button" class="support-close" aria-label="Close support form">Close</button>',
            '    <span class="eyebrow">Support</span>',
            '    <h2 id="support-title">Tell us what is going on</h2>',
            '    <p>Write the question, bug, missing course detail, or confusing part. When you send, your email app opens with the message ready.</p>',
            '    <form class="support-form">',
            '        <label for="support-subject">Subject</label>',
            '        <input id="support-subject" name="subject" type="text" placeholder="Example: MUELE courses are not showing" required>',
            '        <label for="support-body">Message</label>',
            '        <textarea id="support-body" name="body" rows="7" placeholder="Add the page, what you clicked, what you expected, and what happened." required></textarea>',
            '        <button type="submit" class="btn btn-primary">Send message</button>',
            '    </form>',
            '</div>'
        ].join('');
        document.body.appendChild(overlay);
        return overlay;
    }

    function openSupport(overlay) {
        overlay.hidden = false;
        document.body.classList.add('support-open');
        var subject = overlay.querySelector('#support-subject');
        if (subject) subject.focus();
    }

    function closeSupport(overlay) {
        overlay.hidden = true;
        document.body.classList.remove('support-open');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var overlay = buildSupportDialog();
        var form = overlay.querySelector('.support-form');
        var close = overlay.querySelector('.support-close');

        document.querySelectorAll('[data-support-open]').forEach(function (trigger) {
            trigger.addEventListener('click', function (event) {
                event.preventDefault();
                openSupport(overlay);
            });
        });

        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) closeSupport(overlay);
        });

        close.addEventListener('click', function () {
            closeSupport(overlay);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !overlay.hidden) closeSupport(overlay);
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var subject = form.querySelector('#support-subject').value.trim();
            var body = form.querySelector('#support-body').value.trim();
            if (!subject || !body) return;
            var pageLine = '\n\nPage: ' + window.location.href;
            window.location.href = 'mailto:' + supportInbox()
                + '?subject=' + encodeURIComponent('[Orch] ' + subject)
                + '&body=' + encodeURIComponent(body + pageLine);
            closeSupport(overlay);
        });
    });
})();
