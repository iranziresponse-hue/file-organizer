// Persists the open/closed state of any <details data-persist-key="..."> to
// localStorage, matching the app's existing orch-* key convention
// (orch-theme, orch-scroll:*). Used by the dashboard's Tier 3 "More detail"
// disclosure and its nested "Plain status view". Storage is best-effort:
// a private window or blocked storage just means the choice is not
// remembered, never a broken page.
(function () {
    function readBool(key) {
        try {
            return window.localStorage.getItem(key) === '1';
        } catch (err) {
            return null;
        }
    }

    function write(key, isOpen) {
        try {
            window.localStorage.setItem(key, isOpen ? '1' : '0');
        } catch (err) {
            /* storage unavailable -- fine */
        }
    }

    document.querySelectorAll('details[data-persist-key]').forEach(function (el) {
        var key = el.getAttribute('data-persist-key');
        var saved = readBool(key);
        if (saved !== null) {
            el.open = saved;
        }
        el.addEventListener('toggle', function () {
            write(key, el.open);
        });
    });
})();
