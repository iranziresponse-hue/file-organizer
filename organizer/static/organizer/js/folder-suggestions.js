function initFolderSuggestions() {
    var rootInput = document.getElementById('root_path');
    var primaryInput = document.getElementById('primary_value');
    var secondaryInput = document.getElementById('secondary_value');
    var groupsContainer = document.getElementById('groups-tag-input');
    var suggestionsBox = document.getElementById('groups-suggestions');
    if (!rootInput || !primaryInput || !secondaryInput) return;

    function fillDatalist(id, names) {
        var el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = '';
        names.forEach(function (name) {
            var opt = document.createElement('option');
            opt.value = name;
            el.appendChild(opt);
        });
    }

    function fillSuggestions(names) {
        if (!suggestionsBox) return;
        suggestionsBox.innerHTML = '';
        names.forEach(function (name) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'suggestion-token';
            btn.textContent = name;
            btn.addEventListener('click', function () {
                if (groupsContainer && groupsContainer.addTag) groupsContainer.addTag(name);
            });
            suggestionsBox.appendChild(btn);
        });
    }

    function joinPath() {
        var parts = Array.prototype.slice.call(arguments).filter(Boolean);
        return parts.join('\\');
    }

    function refreshPrimaryPresets() {
        fetchSubfolderNames(rootInput.value, function (names) {
            fillDatalist('primary-value-presets', names);
        });
    }

    function refreshSecondaryPresets() {
        if (!rootInput.value || !primaryInput.value) {
            fillDatalist('secondary-value-presets', []);
            return;
        }
        fetchSubfolderNames(joinPath(rootInput.value, primaryInput.value), function (names) {
            fillDatalist('secondary-value-presets', names);
        });
    }

    function refreshGroupSuggestions() {
        if (!rootInput.value || !primaryInput.value || !secondaryInput.value) {
            fillSuggestions([]);
            return;
        }
        fetchSubfolderNames(joinPath(rootInput.value, primaryInput.value, secondaryInput.value), fillSuggestions);
    }

    rootInput.addEventListener('change', function () {
        refreshPrimaryPresets();
        refreshSecondaryPresets();
        refreshGroupSuggestions();
    });
    primaryInput.addEventListener('change', function () {
        refreshSecondaryPresets();
        refreshGroupSuggestions();
    });
    secondaryInput.addEventListener('change', refreshGroupSuggestions);

    refreshPrimaryPresets();
    refreshSecondaryPresets();
    refreshGroupSuggestions();
}
