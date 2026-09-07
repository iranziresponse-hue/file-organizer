(function () {
    var FADE_AFTER_MS = 3200;
    var FADE_DURATION_MS = 200;

    function getList() {
        var list = document.getElementById("page-messages");
        if (!list) {
            list = document.createElement("ul");
            list.className = "messages";
            list.id = "page-messages";
            document.body.appendChild(list);
        }
        // WCAG: the toast list is a live region so a screen reader hears
        // "file moved", "undone", "approved" etc. instead of them being a
        // purely visual event. Set here too (not just in base.html) for the
        // JS-created list on pages that had no server-rendered messages.
        list.setAttribute("role", "status");
        list.setAttribute("aria-live", "polite");
        return list;
    }

    function isError(li) {
        return li.classList.contains("error");
    }

    function addProgressBar(li) {
        // No shrinking progress bar for errors -- they never auto-dismiss,
        // so a countdown animation would be a lie.
        if (isError(li)) {
            return;
        }
        var bar = document.createElement("span");
        bar.className = "toast-progress";
        bar.style.setProperty("--toast-duration", FADE_AFTER_MS + "ms");
        li.appendChild(bar);
    }

    function addDismissButton(li) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "toast-dismiss";
        btn.setAttribute("aria-label", "Dismiss");
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>';
        btn.addEventListener("click", function () {
            leave(li);
        });
        li.appendChild(btn);
    }

    function leave(li) {
        if (li.dataset.leaving === "1") {
            return;
        }
        li.dataset.leaving = "1";
        if (li._dismissTimer) {
            clearTimeout(li._dismissTimer);
            li._dismissTimer = null;
        }
        li.classList.remove("is-visible");
        li.classList.add("is-leaving");
        setTimeout(function () { li.remove(); }, FADE_DURATION_MS);
    }

    function armDismiss(li) {
        // Errors must be dismissed deliberately (WCAG 2.2.1) -- no timer.
        if (isError(li) || li.dataset.leaving === "1") {
            return;
        }
        if (li._dismissTimer) {
            clearTimeout(li._dismissTimer);
        }
        li._paused = false;
        li.classList.remove("is-paused");
        li._dismissTimer = setTimeout(function () { leave(li); }, li._remainingMs || FADE_AFTER_MS);
        li._timerStartedAt = Date.now();
    }

    function pauseDismiss(li) {
        // Pointer or keyboard focus is on the toast -- freeze the countdown
        // so it can be read, and freeze the progress bar with it.
        if (isError(li) || li.dataset.leaving === "1" || li._paused) {
            return;
        }
        li._paused = true;
        li.classList.add("is-paused");
        if (li._dismissTimer) {
            clearTimeout(li._dismissTimer);
            li._dismissTimer = null;
        }
        var elapsed = Date.now() - (li._timerStartedAt || Date.now());
        li._remainingMs = Math.max(400, (li._remainingMs || FADE_AFTER_MS) - elapsed);
    }

    function activate(li) {
        addDismissButton(li);
        li._remainingMs = FADE_AFTER_MS;

        // The shrinking progress bar starts immediately (it's a CSS
        // animation set the moment the element exists), but the entrance
        // transition needs the state change on a separate frame -- adding
        // .is-visible in the same tick the element is inserted would let
        // the browser coalesce the opacity:0 -> opacity:1 change into a
        // single paint with no transition to actually play.
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                li.classList.add("is-visible");
            });
        });

        li.addEventListener("mouseenter", function () { pauseDismiss(li); });
        li.addEventListener("mouseleave", function () { armDismiss(li); });
        // focusin/out rather than focus/blur so tabbing to the dismiss
        // button inside the toast counts as "still hovering".
        li.addEventListener("focusin", function () { pauseDismiss(li); });
        li.addEventListener("focusout", function () { armDismiss(li); });

        armDismiss(li);
    }

    function activateServerRendered() {
        // Toasts Django's messages framework already rendered (after a
        // form's post/redirect/get) get the same run-and-fade treatment as
        // ones added here by JS -- one visual language for "this action
        // just happened" whether the page reloaded or an AJAX call updated
        // something in place.
        getList();
        document.querySelectorAll("#page-messages li").forEach(function (li) {
            addProgressBar(li);
            activate(li);
        });
    }

    // This script tag sits before <main> (and #page-messages) in base.html,
    // so running this at the top level -- before the rest of the page has
    // even been parsed -- always found zero <li> elements: the progress
    // bar silently never got attached to a real page action's toast, only
    // to ones created later via showToast(). Waiting for DOMContentLoaded
    // makes this work regardless of where the script tag ends up.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", activateServerRendered);
    } else {
        activateServerRendered();
    }

    window.showToast = function (message, tag) {
        var li = document.createElement("li");
        li.className = tag || "info";
        li.textContent = message;
        addProgressBar(li);
        getList().appendChild(li);
        activate(li);
    };
})();
