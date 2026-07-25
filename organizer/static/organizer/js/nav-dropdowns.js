        (function () {
            var active = null;

            function getMenu(trigger) {
                var id = trigger.getAttribute('aria-controls');
                return id ? document.getElementById(id) : trigger.nextElementSibling;
            }

            function setExpanded(trigger, expanded) {
                trigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            }

            function focusMenuItem(menu, direction) {
                var items = Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"], button, a'));
                var enabled = items.filter(function (item) {
                    return !item.disabled && item.getAttribute('aria-disabled') !== 'true';
                });
                if (!enabled.length) return;
                var currentIndex = enabled.indexOf(document.activeElement);
                var nextIndex = currentIndex < 0 ? 0 : (currentIndex + direction + enabled.length) % enabled.length;
                enabled[nextIndex].focus();
            }

            function positionMenu(trigger, menu) {
                var margin = 8;
                var gap = 8;
                var rect = trigger.getBoundingClientRect();
                var viewportWidth = document.documentElement.clientWidth;
                var viewportHeight = document.documentElement.clientHeight;

                menu.hidden = false;
                menu.classList.add('is-positioning');
                menu.style.width = '';

                var menuRect = menu.getBoundingClientRect();
                var maxWidth = Math.max(180, viewportWidth - margin * 2);
                if (menuRect.width > maxWidth) {
                    menu.style.width = maxWidth + 'px';
                    menuRect = menu.getBoundingClientRect();
                }

                var left = Math.min(
                    Math.max(margin, rect.right - menuRect.width),
                    viewportWidth - menuRect.width - margin
                );
                var below = rect.bottom + gap;
                var above = rect.top - menuRect.height - gap;
                var top = below;
                var placement = 'bottom';

                if (below + menuRect.height > viewportHeight - margin && above >= margin) {
                    top = above;
                    placement = 'top';
                } else {
                    top = Math.min(below, viewportHeight - menuRect.height - margin);
                }

                menu.style.left = Math.round(left) + 'px';
                menu.style.top = Math.round(Math.max(margin, top)) + 'px';
                menu.dataset.placement = placement;
                menu.classList.remove('is-positioning');
            }

            function close(focusTrigger) {
                if (!active) return;
                active.menu.hidden = true;
                active.menu.classList.remove('is-open');
                setExpanded(active.trigger, false);
                if (focusTrigger) active.trigger.focus();
                active = null;
            }

            function open(trigger, options) {
                var menu = getMenu(trigger);
                if (!menu) return;
                if (active && active.menu === menu) {
                    if (options && options.focusFirst) {
                        focusMenuItem(menu, 1);
                        return;
                    }
                    close(false);
                    return;
                }
                close(false);
                active = { trigger: trigger, menu: menu };
                setExpanded(trigger, true);
                positionMenu(trigger, menu);
                menu.classList.add('is-open');
                if (options && options.focusFirst) focusMenuItem(menu, 1);
            }

            function wire(scope) {
                var root = scope || document;
                root.querySelectorAll('[data-menu-toggle]').forEach(function (trigger) {
                    if (trigger.dataset.menuWired === 'true') return;
                    trigger.dataset.menuWired = 'true';
                    if (!trigger.hasAttribute('aria-haspopup')) trigger.setAttribute('aria-haspopup', 'menu');
                    setExpanded(trigger, false);

                    trigger.addEventListener('click', function (event) {
                        event.stopPropagation();
                        open(trigger);
                    });
                    trigger.addEventListener('keydown', function (event) {
                        if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            open(trigger, { focusFirst: true });
                        }
                    });
                });
            }

            document.addEventListener('click', function (event) {
                if (!active) return;
                if (active.menu.contains(event.target) || active.trigger.contains(event.target)) return;
                close(false);
            });

            document.addEventListener('keydown', function (event) {
                if (!active) return;
                if (event.key === 'Escape') {
                    event.preventDefault();
                    close(true);
                } else if (event.key === 'ArrowDown' && active.menu.contains(document.activeElement)) {
                    event.preventDefault();
                    focusMenuItem(active.menu, 1);
                } else if (event.key === 'ArrowUp' && active.menu.contains(document.activeElement)) {
                    event.preventDefault();
                    focusMenuItem(active.menu, -1);
                }
            });

            window.addEventListener('resize', function () { close(false); });
            window.addEventListener('scroll', function () { close(false); }, true);

            window.OrchDropdowns = {
                close: close,
                wire: wire
            };

            document.addEventListener('DOMContentLoaded', function () {
                wire(document);
            });
        })();

        (function () {
            var premiumSelectCount = 0;

            function enhanceSelect(select) {
                if (select.dataset.premiumSelectReady === 'true') return;
                select.dataset.premiumSelectReady = 'true';

                var wrapper = document.createElement('div');
                wrapper.className = 'premium-select';
                select.parentNode.insertBefore(wrapper, select);
                wrapper.appendChild(select);

                premiumSelectCount += 1;
                var idBase = (select.id || select.name || 'select') + '-' + premiumSelectCount;
                var trigger = document.createElement('button');
                trigger.type = 'button';
                trigger.className = 'premium-select-trigger';
                trigger.setAttribute('data-menu-toggle', '');
                trigger.setAttribute('aria-haspopup', 'menu');
                trigger.setAttribute('aria-expanded', 'false');
                trigger.setAttribute('aria-controls', idBase + '-premium-menu');

                var menu = document.createElement('div');
                menu.className = 'row-actions-menu premium-select-menu';
                menu.id = idBase + '-premium-menu';
                menu.setAttribute('role', 'menu');
                menu.hidden = true;

                function selectedOption() {
                    return select.options[select.selectedIndex] || select.options[0];
                }

                function updateTrigger() {
                    var current = selectedOption();
                    trigger.textContent = current ? current.textContent : 'Choose';
                    Array.prototype.forEach.call(menu.querySelectorAll('[data-select-value]'), function (item) {
                        item.classList.toggle('is-selected', item.dataset.selectValue === select.value);
                    });
                }

                Array.prototype.forEach.call(select.options, function (option) {
                    var item = document.createElement('button');
                    item.type = 'button';
                    item.className = 'row-actions-item premium-select-option';
                    item.setAttribute('role', 'menuitem');
                    item.setAttribute('tabindex', '-1');
                    item.dataset.selectValue = option.value;
                    item.textContent = option.textContent;
                    item.disabled = option.disabled;
                    item.addEventListener('click', function () {
                        select.value = option.value;
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        updateTrigger();
                        if (window.OrchDropdowns) window.OrchDropdowns.close(false);
                        trigger.focus();
                    });
                    menu.appendChild(item);
                });

                wrapper.appendChild(trigger);
                wrapper.appendChild(menu);
                select.addEventListener('change', updateTrigger);
                updateTrigger();
                if (window.OrchDropdowns) window.OrchDropdowns.wire(wrapper);
            }

            document.addEventListener('DOMContentLoaded', function () {
                document.querySelectorAll('select[data-premium-select]').forEach(enhanceSelect);
            });
        })();
