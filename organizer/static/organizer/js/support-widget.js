(function () {
    var overlay = document.getElementById('support-overlay');
    var toggle = document.getElementById('support-toggle');
    var close = document.getElementById('support-close');
    var form = document.getElementById('support-form');
    var feedback = document.getElementById('support-feedback');
    var submitBtn = document.getElementById('support-submit');
    var pageUrlField = document.getElementById('support-page-url');
    if (!overlay || !toggle || !form) return;

    function open() {
        if (pageUrlField) pageUrlField.value = window.location.href;
        overlay.hidden = false;
    }
    function hide() {
        overlay.hidden = true;
    }

    toggle.addEventListener('click', open);
    close.addEventListener('click', hide);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) hide();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !overlay.hidden) hide();
    });

    function setFeedback(text, isError) {
        feedback.textContent = text;
        feedback.style.color = isError ? 'var(--red)' : 'var(--green)';
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (submitBtn.disabled) return;

        var message = document.getElementById('support-message').value.trim();
        if (!message) {
            setFeedback('Write a message before sending.', true);
            return;
        }

        submitBtn.disabled = true;
        setFeedback('Sending...', false);

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.ok) {
                    setFeedback('Message sent. Thanks!', false);
                    form.reset();
                } else {
                    setFeedback(data.error || 'Could not send that. Try again.', true);
                    submitBtn.disabled = false;
                }
            })
            .catch(function () {
                setFeedback('Could not reach Orch to send that. Try again.', true);
                submitBtn.disabled = false;
            });
    });
})();
