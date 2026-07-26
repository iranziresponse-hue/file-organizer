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
    var VISIBLE_COUNT = 3;
    document.querySelectorAll('.feature-grid').forEach(function (grid) {
        var cards = Array.prototype.slice.call(grid.querySelectorAll('.feature-card'));
        if (cards.length <= VISIBLE_COUNT) return;

        var extra = cards.slice(VISIBLE_COUNT);
        extra.forEach(function (card) { card.hidden = true; });

        var moreCount = extra.length;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-ghost feature-grid-toggle mt-16';
        button.textContent = 'Show ' + moreCount + ' more';
        button.setAttribute('aria-expanded', 'false');
        grid.insertAdjacentElement('afterend', button);

        button.addEventListener('click', function () {
            var expanded = button.getAttribute('aria-expanded') === 'true';
            extra.forEach(function (card) { card.hidden = expanded; });
            button.setAttribute('aria-expanded', String(!expanded));
            button.textContent = expanded ? 'Show ' + moreCount + ' more' : 'Show fewer';
        });
    });
})();

(function () {
    var toggle = document.getElementById('nav-toggle');
    var nav = document.getElementById('main-nav');
    if (!toggle || !nav) return;

    function closeMenu() {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
    }

    function openMenu() {
        nav.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
    }

    toggle.addEventListener('click', function () {
        if (nav.classList.contains('is-open')) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    nav.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', closeMenu);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && nav.classList.contains('is-open')) {
            closeMenu();
            toggle.focus();
        }
    });

    document.addEventListener('click', function (event) {
        if (!nav.classList.contains('is-open')) return;
        if (nav.contains(event.target) || toggle.contains(event.target)) return;
        closeMenu();
    });
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
            '    <h2 id="support-title">Contact Orch Support</h2>',
            '    <p>Share your question, issue, missing course detail, or feedback. This site has no server of its own. The next step opens your email app with the message already filled in, and you send it from there.</p>',
            '    <form class="support-form">',
            '        <label for="support-subject">Subject</label>',
            '        <input id="support-subject" name="subject" type="text" placeholder="Example: MUELE courses are not showing" required>',
            '        <label for="support-body">Message</label>',
            '        <textarea id="support-body" name="body" rows="7" placeholder="Include the page, the action you tried, what you expected, and what happened." required></textarea>',
            '        <button type="submit" class="btn btn-primary">Open in your email app</button>',
            '    </form>',
            '</div>'
        ].join('');
        document.body.appendChild(overlay);
        return overlay;
    }

    var lastFocused = null;

    function focusableElements(overlay) {
        return Array.prototype.slice.call(
            overlay.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')
        );
    }

    function openSupport(overlay) {
        lastFocused = document.activeElement;
        overlay.hidden = false;
        document.body.classList.add('support-open');
        var subject = overlay.querySelector('#support-subject');
        if (subject) subject.focus();
    }

    function closeSupport(overlay) {
        overlay.hidden = true;
        document.body.classList.remove('support-open');
        if (lastFocused && typeof lastFocused.focus === 'function') {
            lastFocused.focus();
        }
        lastFocused = null;
    }

    function trapFocus(overlay, event) {
        if (event.key !== 'Tab' || overlay.hidden) return;
        var focusable = focusableElements(overlay);
        if (!focusable.length) return;
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
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
            trapFocus(overlay, event);
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
