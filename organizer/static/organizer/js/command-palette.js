(function () {
    // Static "go to page" list -- matched client-side, no round trip needed
    // for a fixed set of destinations. Paths are hardcoded (matching
    // organizer/urls.py) rather than reversed server-side, same convention
    // already used by this app's other page-scoped JS (e.g. the reroute
    // form action built in sorting_inbox.html's inline script).
    var DESTINATIONS = [
        { title: "Dashboard", subtitle: "Home cockpit", url: "/", keywords: "home overview" },
        { title: "Study cockpit", subtitle: "Study", url: "/study/", keywords: "study home" },
        { title: "Career command center", subtitle: "Career", url: "/career/", keywords: "career" },
        { title: "Connections", subtitle: "Integrations", url: "/connections/", keywords: "integrations connect" },
        { title: "Decision inbox", subtitle: "Study", url: "/study/inbox/", keywords: "inbox review approve reroute" },
        { title: "Organization memory", subtitle: "Study", url: "/study/memory/", keywords: "memory learned rules" },
        { title: "Organization DNA", subtitle: "Study", url: "/study/dna/", keywords: "dna patterns" },
        { title: "Profiles", subtitle: "Manage profiles", url: "/profiles/", keywords: "profile switch semester" },
        { title: "New profile", subtitle: "Profiles", url: "/profiles/new/", keywords: "add profile create wizard" },
        { title: "Settings", subtitle: "App-wide", url: "/settings/", keywords: "settings watched folders" },
        { title: "Digests", subtitle: "Study", url: "/study/digests/", keywords: "weekly digest recap" },
        { title: "Timeline", subtitle: "Study", url: "/study/timeline/", keywords: "activity history" },
        { title: "Review queue", subtitle: "Study", url: "/study/reviews/", keywords: "spaced repetition review" },
        { title: "Resource Radar", subtitle: "Study", url: "/study/resources/", keywords: "videos books github repos youtube watch" },
        { title: "Learning routes", subtitle: "Study", url: "/study/routes/", keywords: "weak area sequence" },
        { title: "Makerere timetable", subtitle: "Study", url: "/study/timetable/", keywords: "classes schedule" },
        { title: "Subjects", subtitle: "Study", url: "/study/subjects/", keywords: "subject dashboard courses" },
        { title: "Knowledge exports", subtitle: "Study", url: "/study/exports/", keywords: "knowledge packs export bundle" },
        { title: "First-run setup", subtitle: "Study", url: "/study/setup/", keywords: "checklist onboarding" },
        { title: "Undo recent", subtitle: "Study", url: "/study/undo/", keywords: "undo recent moves" },
        { title: "Notifications", subtitle: "Study", url: "/study/notifications/", keywords: "alerts" },
        { title: "Folder rules", subtitle: "Study", url: "/study/rules/", keywords: "custom sorting rules" },
        { title: "Assignment tracker", subtitle: "Study", url: "/study/assignments/", keywords: "assignments deadlines" },
        { title: "Exam countdown", subtitle: "Study", url: "/study/exams/", keywords: "exams countdown" },
        { title: "Folder imports", subtitle: "Study", url: "/study/import/", keywords: "import existing folder sort" },
        { title: "Weakness radar", subtitle: "Study", url: "/study/weakness/", keywords: "weak topics" },
        { title: "Grade target planner", subtitle: "Study", url: "/study/grades/", keywords: "grades targets gpa" },
        { title: "Flashcards", subtitle: "Study", url: "/study/flashcards/", keywords: "flashcards spaced repetition" },
        { title: "Semester war room", subtitle: "Study", url: "/study/war-room/", keywords: "war room today next action" },
        { title: "Smart study timetable", subtitle: "Study", url: "/study/smart-timetable/", keywords: "study plan timetable" },
        { title: "Project studio", subtitle: "Career", url: "/career/projects/", keywords: "projects portfolio" },
        { title: "Career digest", subtitle: "Career", url: "/career/digest/", keywords: "weekly career digest" },
        { title: "Posts & drafts", subtitle: "Career", url: "/career/posts/", keywords: "content drafts posts publish" },
        { title: "Publishing channels", subtitle: "Career", url: "/career/channels/", keywords: "linkedin github website publish" },
        { title: "MUELE connection", subtitle: "Connections", url: "/integrations/muele/", keywords: "muele moodle" },
        { title: "MUELE courses", subtitle: "Connections", url: "/integrations/muele/courses/", keywords: "muele courses" }
    ];

    var overlay = document.getElementById("palette-overlay");
    var input = document.getElementById("palette-input");
    var resultsEl = document.getElementById("palette-results");
    var emptyEl = document.getElementById("palette-empty");
    var toggle = document.getElementById("palette-toggle");
    if (!overlay || !input || !resultsEl || !emptyEl || !toggle) return;

    var activeIndex = -1;
    var currentItems = [];
    var fetchController = null;
    var fetchTimer = null;

    var NAV_ICON = '<svg viewBox="0 0 24 24" fill="none"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
    var FILE_ICON = '<svg viewBox="0 0 24 24" fill="none"><path d="M6 3.5h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-16a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>';

    function render(items, emptyMessage) {
        currentItems = items;
        activeIndex = items.length ? 0 : -1;
        resultsEl.innerHTML = "";
        emptyEl.hidden = items.length > 0;
        if (!items.length) emptyEl.textContent = emptyMessage;

        var groups = {};
        var order = [];
        items.forEach(function (item) {
            var group = item.group || "Go to";
            if (!groups[group]) { groups[group] = []; order.push(group); }
            groups[group].push(item);
        });

        order.forEach(function (group) {
            var label = document.createElement("div");
            label.className = "palette-group-label";
            label.textContent = group;
            resultsEl.appendChild(label);

            groups[group].forEach(function (item) {
                var index = items.indexOf(item);
                var button = document.createElement("button");
                button.type = "button";
                button.className = "palette-item" + (index === activeIndex ? " is-active" : "");
                button.setAttribute("role", "option");
                button.dataset.index = String(index);
                button.innerHTML =
                    '<span class="palette-item-icon">' + (group === "Files" ? FILE_ICON : NAV_ICON) + "</span>" +
                    '<span class="palette-item-body">' +
                        '<span class="palette-item-title"></span>' +
                        '<span class="palette-item-subtitle"></span>' +
                    "</span>";
                button.querySelector(".palette-item-title").textContent = item.title;
                var subtitleEl = button.querySelector(".palette-item-subtitle");
                if (item.subtitle) subtitleEl.textContent = item.subtitle; else subtitleEl.remove();
                button.addEventListener("click", function () { go(item); });
                resultsEl.appendChild(button);
            });
        });
    }

    function go(item) {
        window.location.href = item.url;
    }

    function matchDestinations(query) {
        var q = query.toLowerCase();
        return DESTINATIONS
            .map(function (d) {
                var haystack = (d.title + " " + (d.keywords || "") + " " + (d.subtitle || "")).toLowerCase();
                return { item: d, score: haystack.indexOf(q) };
            })
            .filter(function (entry) { return entry.score !== -1; })
            .sort(function (a, b) { return a.score - b.score; })
            .slice(0, 6)
            .map(function (entry) {
                return { title: entry.item.title, subtitle: entry.item.subtitle, url: entry.item.url, group: "Go to" };
            });
    }

    function fetchFileResults(query, done) {
        if (fetchController) fetchController.abort();
        fetchController = new AbortController();
        fetch("/api/command-search/?q=" + encodeURIComponent(query), { signal: fetchController.signal })
            .then(function (resp) { return resp.ok ? resp.json() : { results: [] }; })
            .then(function (data) {
                done((data.results || []).map(function (r) {
                    return { title: r.title, subtitle: r.subtitle, url: r.url, group: "Files" };
                }));
            })
            .catch(function () { done([]); });
    }

    function search(query) {
        var trimmed = query.trim();
        if (!trimmed) {
            render([], "Type to jump to a page, file, or summary.");
            return;
        }

        var destinationResults = matchDestinations(trimmed);
        render(destinationResults, "Searching…");

        clearTimeout(fetchTimer);
        fetchTimer = setTimeout(function () {
            fetchFileResults(trimmed, function (fileResults) {
                render(destinationResults.concat(fileResults), "No matches. Try a different word.");
            });
        }, 150);
    }

    function open() {
        overlay.hidden = false;
        input.value = "";
        render([], "Type to jump to a page, file, or summary.");
        input.focus();
    }

    function close() {
        overlay.hidden = true;
        if (fetchController) fetchController.abort();
    }

    function moveActive(direction) {
        if (!currentItems.length) return;
        activeIndex = (activeIndex + direction + currentItems.length) % currentItems.length;
        Array.prototype.forEach.call(resultsEl.querySelectorAll(".palette-item"), function (el) {
            el.classList.toggle("is-active", Number(el.dataset.index) === activeIndex);
        });
        var activeEl = resultsEl.querySelector(".palette-item.is-active");
        if (activeEl) activeEl.scrollIntoView({ block: "nearest" });
    }

    toggle.addEventListener("click", open);

    document.addEventListener("keydown", function (event) {
        var isShortcut = (event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && (event.key === "k" || event.key === "K");
        if (isShortcut) {
            event.preventDefault();
            if (overlay.hidden) open(); else close();
            return;
        }
        if (overlay.hidden) return;

        if (event.key === "Escape") {
            close();
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            moveActive(1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            moveActive(-1);
        } else if (event.key === "Enter") {
            event.preventDefault();
            if (activeIndex >= 0 && currentItems[activeIndex]) go(currentItems[activeIndex]);
        }
    });

    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) close();
    });

    input.addEventListener("input", function () {
        search(input.value);
    });
})();
