(() => {
  const target = document.getElementById('x-timeline');
  const status = document.getElementById('x-timeline-status');
  if (!target || !status) return;
  const unavailable = () => { status.textContent = 'X posts are unavailable here. Open the curated list on X below.'; };
  const timeout = setTimeout(unavailable, 15000);
  const script = document.createElement('script');
  script.src = 'https://platform.twitter.com/widgets.js';
  script.async = true;
  script.onerror = unavailable;
  script.onload = async () => {
    try {
      const frame = await window.twttr.widgets.createTimeline(
        {sourceType: 'list', id: '2110824549948264866'}, target,
        {height: 900, chrome: 'noheader nofooter', dnt: true}
      );
      clearTimeout(timeout);
      if (frame && frame.clientHeight > 0) status.hidden = true;
      else unavailable();
    } catch (_) { unavailable(); }
  };
  document.head.appendChild(script);
})();
