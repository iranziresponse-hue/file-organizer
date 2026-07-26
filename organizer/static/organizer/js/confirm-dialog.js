(function () {
    var overlay = document.getElementById("confirm-overlay");
    if (!overlay) return;

    var messageEl = document.getElementById("confirm-message");
    var okBtn = document.getElementById("confirm-ok");
    var cancelBtn = document.getElementById("confirm-cancel");
    var pendingResolve = null;

    function close(result) {
        overlay.hidden = true;
        if (pendingResolve) {
            var resolve = pendingResolve;
            pendingResolve = null;
            resolve(result);
        }
    }

    okBtn.addEventListener("click", function () { close(true); });
    cancelBtn.addEventListener("click", function () { close(false); });
    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) close(false);
    });
    document.addEventListener("keydown", function (event) {
        if (!overlay.hidden && event.key === "Escape") close(false);
    });

    window.orchConfirm = function (message) {
        return new Promise(function (resolve) {
            messageEl.textContent = message;
            pendingResolve = resolve;
            overlay.hidden = false;
            okBtn.focus();
        });
    };

    // Forms opt in via data-confirm="..." instead of the inline
    // onsubmit="return confirm(...)" browser dialog -- that native dialog
    // labels itself with the app's raw local URL ("127.0.0.1:8765 says")
    // and pins itself to the top-left of the window regardless of where
    // the user is looking, both dead giveaways this is a webpage wearing
    // an app's clothes. This intercepts that submit once, shows the app's
    // own centered dialog instead, and actually submits the form for real
    // if confirmed.
    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        var message = form.getAttribute("data-confirm");
        if (!message || form.dataset.confirmed === "true") return;
        event.preventDefault();
        window.orchConfirm(message).then(function (ok) {
            if (!ok) return;
            form.dataset.confirmed = "true";
            if (form.requestSubmit) {
                form.requestSubmit();
            } else {
                form.submit();
            }
        });
    }, true);
})();
