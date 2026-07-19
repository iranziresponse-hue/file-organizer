function fetchSubfolderNames(path, callback) {
    if (!path) { callback([]); return; }
    fetch('/api/browse-folders/?path=' + encodeURIComponent(path))
        .then(function (r) { return r.json(); })
        .then(function (data) { callback((data.folders || []).map(function (f) { return f.name; })); })
        .catch(function () { callback([]); });
}

(function () {
    var overlay = document.getElementById('browser-overlay');
    if (!overlay) return;

    var pathLabel = document.getElementById('browser-current-path');
    var list = document.getElementById('browser-list');
    var closeBtn = document.getElementById('browser-close');
    var upBtn = document.getElementById('browser-up');
    var selectBtn = document.getElementById('browser-select');

    var state = { path: '', parent: null, targetInputId: null };

    function fetchFolders(path, onDone) {
        list.innerHTML = '<p class="help-text">Loading...</p>';
        fetch('/api/browse-folders/?path=' + encodeURIComponent(path || ''))
            .then(function (r) { return r.json(); })
            .then(onDone)
            .catch(function () {
                list.innerHTML = '<p class="help-text">Could not read this folder.</p>';
            });
    }

    function render(data) {
        state.path = data.path || '';
        state.parent = data.parent || null;
        pathLabel.textContent = state.path || 'This PC';
        upBtn.disabled = !state.parent;
        selectBtn.disabled = !state.path;
        list.innerHTML = '';

        if (data.error) {
            var msg = document.createElement('p');
            msg.className = 'help-text';
            msg.textContent = data.error;
            list.appendChild(msg);
            return;
        }

        var folders = data.folders || [];
        if (!folders.length) {
            var empty = document.createElement('p');
            empty.className = 'help-text';
            empty.textContent = 'No subfolders here.';
            list.appendChild(empty);
        }
        folders.forEach(function (folder) {
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'browser-item';
            item.textContent = folder.name;
            item.addEventListener('click', function () {
                fetchFolders(folder.path, render);
            });
            list.appendChild(item);
        });
    }

    function hide() { overlay.hidden = true; }

    window.openFolderBrowser = function (targetInputId) {
        state.targetInputId = targetInputId;
        var input = document.getElementById(targetInputId);
        var startPath = input && input.value ? input.value : '';
        overlay.hidden = false;
        fetchFolders(startPath, render);
    };

    closeBtn.addEventListener('click', hide);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) hide();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !overlay.hidden) hide();
    });
    upBtn.addEventListener('click', function () {
        if (state.parent) fetchFolders(state.parent, render);
    });
    selectBtn.addEventListener('click', function () {
        if (state.targetInputId && state.path) {
            var input = document.getElementById(state.targetInputId);
            input.value = state.path;
            input.dispatchEvent(new Event('change'));
        }
        hide();
    });
})();
