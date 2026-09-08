// Live behaviour for the Settings form (settings_edit.html):
//   * progressive disclosure -- an integration's credentials / a category's
//     routing fields only show while its toggle is on, which is what keeps
//     the page from being one long scroll
//   * a sticky save bar that wakes up the moment anything changes, so the
//     Save button can't be scrolled past and forgotten, plus a matching
//     "you have unsaved changes" guard on navigating away
//   * inline required / invalid field states instead of a silent browser
//     bubble
// The owner-mode toggle saves itself over AJAX and is deliberately left out
// of the dirty tracking below.
(function () {
    var form = document.querySelector('[data-settings-form]');
    if (!form) {
        return;
    }

    var savebar = form.querySelector('[data-savebar]');
    var statusEl = form.querySelector('[data-savebar-status]');
    var discardBtn = form.querySelector('[data-savebar-discard]');

    function inputByName(name) {
        return form.querySelector('[name="' + name + '"]');
    }

    // --- progressive disclosure --------------------------------------
    function syncReveal(el) {
        var checkbox = inputByName(el.getAttribute('data-reveal-for'));
        if (checkbox) {
            el.hidden = !checkbox.checked;
        }
    }
    function syncDetail(details) {
        var checkbox = inputByName(details.getAttribute('data-detail-for'));
        if (checkbox) {
            details.open = checkbox.checked;
        }
    }
    function syncCaption(span) {
        var sw = span.closest('.setting-switch');
        var checkbox = sw && sw.querySelector('input[type="checkbox"]');
        if (checkbox) {
            span.textContent = checkbox.checked
                ? (span.getAttribute('data-on') || span.textContent)
                : (span.getAttribute('data-off') || span.textContent);
        }
    }

    form.querySelectorAll('[data-reveal-for]').forEach(function (el) {
        var checkbox = inputByName(el.getAttribute('data-reveal-for'));
        if (checkbox) {
            checkbox.addEventListener('change', function () { syncReveal(el); });
        }
    });
    form.querySelectorAll('[data-detail-for]').forEach(function (details) {
        var checkbox = inputByName(details.getAttribute('data-detail-for'));
        if (checkbox) {
            checkbox.addEventListener('change', function () { syncDetail(details); });
        }
    });
    form.querySelectorAll('[data-toggle-caption]').forEach(function (span) {
        var sw = span.closest('.setting-switch');
        var checkbox = sw && sw.querySelector('input[type="checkbox"]');
        if (checkbox) {
            checkbox.addEventListener('change', function () { syncCaption(span); });
        }
    });

    // --- dirty tracking + sticky save bar ---------------------------
    function trackedControls() {
        return Array.prototype.filter.call(
            form.querySelectorAll('input[name], select[name], textarea[name]'),
            function (el) {
                return el.type !== 'hidden' && el.id !== 'owner-mode-toggle';
            }
        );
    }

    function valueOf(el) {
        if (el.type === 'checkbox' || el.type === 'radio') {
            return el.checked ? '1' : '0';
        }
        return el.value;
    }

    var baseline = {};
    function snapshot() {
        baseline = {};
        trackedControls().forEach(function (el, i) {
            baseline[el.name + '#' + i] = valueOf(el);
        });
    }

    function countChanges() {
        var n = 0;
        trackedControls().forEach(function (el, i) {
            if (baseline[el.name + '#' + i] !== valueOf(el)) {
                n += 1;
            }
        });
        return n;
    }

    var submitting = false;

    function refreshSavebar() {
        if (!savebar) return;
        var n = submitting ? 0 : countChanges();
        savebar.setAttribute('data-dirty', n > 0 ? 'true' : 'false');
        if (statusEl) {
            statusEl.textContent = n > 0
                ? (n + ' unsaved change' + (n === 1 ? '' : 's'))
                : 'All changes saved';
        }
    }

    snapshot();
    refreshSavebar();

    form.addEventListener('input', refreshSavebar);
    form.addEventListener('change', refreshSavebar);

    if (discardBtn) {
        discardBtn.addEventListener('click', function () {
            if (countChanges() === 0) return;
            if (!window.confirm('Discard your unsaved settings changes?')) return;
            submitting = true; // suppress the navigate-away guard
            window.location.reload();
        });
    }

    window.addEventListener('beforeunload', function (e) {
        if (!submitting && countChanges() > 0) {
            e.preventDefault();
            e.returnValue = '';
            return '';
        }
    });

    // --- inline validation on submit ------------------------------
    function fieldWrap(el) {
        return el.closest('.field') || el.parentElement;
    }

    function clearError(el) {
        var wrap = fieldWrap(el);
        if (!wrap) return;
        wrap.classList.remove('is-invalid');
        var msg = wrap.querySelector('.field-error');
        if (msg) msg.remove();
    }

    function showError(el, message) {
        var wrap = fieldWrap(el);
        if (!wrap) return;
        wrap.classList.add('is-invalid');
        if (!wrap.querySelector('.field-error')) {
            var span = document.createElement('span');
            span.className = 'field-error';
            span.textContent = message;
            wrap.appendChild(span);
        }
        // If the field sits inside a collapsed section, open it so the
        // error is actually visible.
        var reveal = el.closest('.reveal[hidden]');
        if (reveal) reveal.hidden = false;
        var details = el.closest('details:not([open])');
        if (details) details.open = true;
    }

    form.addEventListener('input', function (e) {
        if (e.target && (e.target.matches('input') || e.target.matches('select'))) {
            clearError(e.target);
        }
    });

    form.addEventListener('submit', function (e) {
        var invalid = [];
        form.querySelectorAll('input, select, textarea').forEach(function (el) {
            if (el.disabled || el.type === 'hidden') return;
            if (el.hasAttribute('required') && !el.value.trim()) {
                showError(el, 'This is required.');
                invalid.push(el);
                return;
            }
            if (el.type === 'number' && el.value !== '') {
                var num = parseInt(el.value, 10);
                var min = el.getAttribute('min');
                if (isNaN(num) || (min !== null && num < parseInt(min, 10))) {
                    showError(el, min ? ('Enter a whole number of ' + min + ' or more.') : 'Enter a whole number.');
                    invalid.push(el);
                }
            }
        });

        if (invalid.length) {
            e.preventDefault();
            var first = invalid[0];
            try {
                first.scrollIntoView({ block: 'center', behavior: 'smooth' });
            } catch (err) {
                first.scrollIntoView();
            }
            first.focus({ preventScroll: true });
            return;
        }

        submitting = true;
        refreshSavebar();
    });
})();
