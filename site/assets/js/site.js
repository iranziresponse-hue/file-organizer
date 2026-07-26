(function () {
    var targets = document.querySelectorAll('[data-reveal]');
    if (!('IntersectionObserver' in window) || !targets.length) {
        targets.forEach(function (el) { el.classList.add('is-visible'); });
        return;
    }
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    targets.forEach(function (el) { observer.observe(el); });
})();

(function () {
    var groups = [
        { root: '.hub-grid', item: '.hub-card' },
        { root: '.pain-grid', item: '.pain-card' },
        { root: '.steps', item: '.step' },
        { root: '.feature-grid', item: '.feature-card' },
        { root: '.showcase-grid', item: ':scope > div' },
        { root: '.cta-steps', item: ':scope > li' }
    ];

    function ensureArrow(card) {
        var arrow = card.querySelector(':scope > .flow-arrow');
        if (!arrow) {
            arrow = document.createElement('span');
            arrow.className = 'flow-arrow';
            arrow.setAttribute('aria-hidden', 'true');
            card.appendChild(arrow);
        }
    }

    function placeFlow() {
        groups.forEach(function (group) {
            document.querySelectorAll(group.root).forEach(function (root) {
                var cards = Array.prototype.slice.call(root.querySelectorAll(group.item));
                cards.forEach(function (card, index) {
                    ensureArrow(card);
                    card.classList.add('flow-card');
                    card.classList.toggle('is-flow-last', index === cards.length - 1);
                    card.classList.remove('is-flow-down');

                    var next = cards[index + 1];
                    if (!next) return;

                    var cardTop = Math.round(card.getBoundingClientRect().top);
                    var nextTop = Math.round(next.getBoundingClientRect().top);
                    if (nextTop > cardTop + 12) {
                        card.classList.add('is-flow-down');
                    }
                });
            });
        });
    }

    var resizeTimer;
    function scheduleFlow() {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(placeFlow, 120);
    }

    placeFlow();
    window.addEventListener('resize', scheduleFlow);
})();
