(function () {
    function play(frame) {
        if (frame.classList.contains('is-playing')) return;
        var videoId = frame.dataset.videoId;
        if (!videoId) return;

        var iframe = document.createElement('iframe');
        iframe.src = 'https://www.youtube.com/embed/' + encodeURIComponent(videoId) + '?autoplay=1&rel=0';
        iframe.title = frame.getAttribute('aria-label') || 'YouTube video';
        iframe.allow = 'autoplay; encrypted-media; picture-in-picture';
        iframe.allowFullscreen = true;
        iframe.loading = 'lazy';

        frame.appendChild(iframe);
        frame.classList.add('is-playing');
        frame.removeAttribute('role');
        frame.removeAttribute('tabindex');
    }

    // The whole frame is the tap target -- thumbnail, play badge, or empty
    // corner all start playback, same as tapping a video card in YouTube's
    // own app instead of hunting for a tiny button.
    document.addEventListener('click', function (event) {
        var frame = event.target.closest('.video-frame');
        if (frame) play(frame);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        var frame = event.target.closest('.video-frame');
        if (!frame || frame.classList.contains('is-playing')) return;
        event.preventDefault();
        play(frame);
    });
})();
