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
        return list;
    }

    function addProgressBar(li) {
        var bar = document.createElement("span");
        bar.className = "toast-progress";
        bar.style.setProperty("--toast-duration", FADE_AFTER_MS + "ms");
        li.appendChild(bar);
    }

    function activate(li) {
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
        setTimeout(function () {
            li.classList.remove("is-visible");
            li.classList.add("is-leaving");
            setTimeout(function () { li.remove(); }, FADE_DURATION_MS);
        }, FADE_AFTER_MS);
    }

    function activateServerRendered() {
        // Toasts Django's messages framework already rendered (after a
        // form's post/redirect/get) get the same run-and-fade treatment as
        // ones added here by JS -- one visual language for "this action
        // just happened" whether the page reloaded or an AJAX call updated
        // something in place.
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
