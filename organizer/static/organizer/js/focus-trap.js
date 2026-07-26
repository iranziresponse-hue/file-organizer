(function () {
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    var lastActive = null;

    function focusableIn(panel) {
        return Array.prototype.slice.call(panel.querySelectorAll(FOCUSABLE)).filter(function (el) {
            return el.offsetParent !== null;
        });
    }

    function openOverlay() {
        return document.querySelector('.guide-overlay:not([hidden])');
    }

    document.querySelectorAll('.guide-overlay').forEach(function (overlay) {
        var observer = new MutationObserver(function () {
            var isOpen = !overlay.hidden;
            if (isOpen) {
                lastActive = document.activeElement;
                var panel = overlay.querySelector('.guide-panel');
                var focusable = panel ? focusableIn(panel) : [];
                if (focusable.length) {
                    focusable[0].focus();
                }
            } else if (lastActive && document.body.contains(lastActive)) {
                lastActive.focus();
                lastActive = null;
            }
        });
        observer.observe(overlay, { attributes: true, attributeFilter: ['hidden'] });
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Tab') return;
        var overlay = openOverlay();
        if (!overlay) return;
        var panel = overlay.querySelector('.guide-panel');
        if (!panel) return;
        var focusable = focusableIn(panel);
        if (!focusable.length) return;

        var first = focusable[0];
        var last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        } else if (!panel.contains(document.activeElement)) {
            // Focus drifted outside the open panel (e.g. background scroll
            // handling stole it) -- pull it back in rather than let Tab
            // continue into the page behind the modal.
            event.preventDefault();
            first.focus();
        }
    });
})();
