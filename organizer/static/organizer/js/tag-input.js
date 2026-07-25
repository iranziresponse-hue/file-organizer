function initTagInput(containerId, entryId, hiddenId, initial, addLabel, labelFor) {
    var container = document.getElementById(containerId);
    var entry = document.getElementById(entryId);
    var hidden = document.getElementById(hiddenId);
    if (!container || !entry || !hidden) return;

    var tags = (initial || '').split(',').map(function (t) { return t.trim(); }).filter(Boolean);

    function render() {
        container.querySelectorAll('.tag-chip').forEach(function (el) { el.remove(); });
        tags.forEach(function (tag, index) {
            var chip = document.createElement('span');
            chip.className = 'tag-chip';

            var label = document.createElement('span');
            label.textContent = labelFor ? labelFor(tag) : tag;

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.setAttribute('aria-label', 'Remove ' + (labelFor ? labelFor(tag) : tag));
            remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
            remove.addEventListener('click', function () {
                tags.splice(index, 1);
                render();
            });

            chip.appendChild(label);
            chip.appendChild(remove);
            container.insertBefore(chip, entry);
        });
        hidden.value = tags.join(', ');
    }

    function addFromEntry() {
        var value = entry.value;
        entry.value = '';
        value.split(',').forEach(function (part) {
            var t = part.trim();
            if (t && tags.indexOf(t) === -1) tags.push(t);
        });
        render();
    }

    entry.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            addFromEntry();
        } else if (e.key === 'Backspace' && !entry.value && tags.length) {
            tags.pop();
            render();
        }
    });
    entry.addEventListener('blur', addFromEntry);

    // Explicit button so adding an entry isn't only discoverable by typing
    // into the box and pressing Enter -- some users expect a clickable action.
    var addButton = document.createElement('button');
    addButton.type = 'button';
    addButton.className = 'tag-add-button';
    addButton.textContent = addLabel || '+ Add';
    addButton.addEventListener('click', function () {
        addFromEntry();
        entry.focus();
    });
    container.appendChild(addButton);

    // Lets external code (e.g. a "this folder already exists" suggestion
    // chip) add a tag without simulating keyboard events.
    container.addTag = function (value) {
        var t = (value || '').trim();
        if (t && tags.indexOf(t) === -1) {
            tags.push(t);
            render();
        }
    };

    render();
}
