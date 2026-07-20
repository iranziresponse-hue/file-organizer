// Universal "did my click register" feedback: disables the button that
// submitted a form and swaps its label for a spinner. Applies to every
// form automatically -- the page still navigates normally afterward, this
// only fixes the dead-looking gap between click and page load. Opt out of
// a specific form with data-no-spinner.
(function () {
    function onSubmit(e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || form.dataset.noSpinner) return;

        var submitter = e.submitter || form.querySelector('button[type="submit"]');
        if (!submitter || submitter.disabled) return;

        submitter.setAttribute('aria-busy', 'true');
        submitter.dataset.originalHtml = submitter.innerHTML;
        submitter.innerHTML =
            '<span class="btn-spinner" aria-hidden="true"></span>' +
            (submitter.dataset.busyText || submitter.textContent.trim() || 'Working...');

        // Disabling the submitter synchronously, inside its own submit
        // handler, risks the browser dropping its name/value pair from the
        // form data it's about to send (some buttons carry meaningful
        // values, e.g. the admin action buttons). Deferring to the next
        // tick lets this submission's data get captured first.
        setTimeout(function () {
            submitter.disabled = true;
        }, 0);
    }

    document.addEventListener('submit', onSubmit, true);
})();
