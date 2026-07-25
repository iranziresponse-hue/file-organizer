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
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var heroFigure = document.querySelector('.hero-figure');
    var tilt = document.querySelector('.laptop-tilt');
    if (prefersReducedMotion || !heroFigure || !tilt) return;

    heroFigure.addEventListener('mousemove', function (event) {
        var bounds = heroFigure.getBoundingClientRect();
        var relX = (event.clientX - bounds.left) / bounds.width - 0.5;
        var relY = (event.clientY - bounds.top) / bounds.height - 0.5;
        tilt.style.transform = 'rotateY(' + (relX * 8) + 'deg) rotateX(' + (relY * -8) + 'deg)';
    });
    heroFigure.addEventListener('mouseleave', function () {
        tilt.style.transform = '';
    });
})();
