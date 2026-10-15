'use strict';
const all = (selector) => Array.from(document.querySelectorAll(selector));
let interest = 'all';
function updateEdition() {
  const now = Date.now();
  all('[data-published]').forEach((card) => {
    const age = now - Date.parse(card.dataset.published);
    card.hidden = !Number.isFinite(age) || age < 0 || age >= 86400000 || (interest !== 'all' && card.dataset.category !== interest);
  });
  const notice = document.getElementById('filter-empty');
  if (notice) notice.hidden = all('[data-published]').some((s) => !s.hidden);
}
all('[data-filter]').forEach((button) => button.addEventListener('click', () => {
  interest = button.dataset.filter;
  all('[data-filter]').forEach((b) => {
    b.classList.toggle('selected', b === button);
    b.setAttribute('aria-pressed', String(b === button));
  });
  updateEdition();
}));
updateEdition();
setInterval(updateEdition, 60000);
all('time[datetime]').forEach((t) => {
  const d = new Date(t.dateTime);
  if (Number.isFinite(d.getTime())) t.textContent = d.toLocaleString(undefined, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short'});
});
const form = document.getElementById('search-form');
if (form) {
  let cache = null;
  let matches = [];
  let shown = 0;
  let generation = 0;
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const more = document.getElementById('load-more');
  async function getJSON(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error('Archive unavailable');
    return response.json();
  }
  function renderMore() {
    const fragment = document.createDocumentFragment();
    matches.slice(shown, shown + 30).forEach((s) => {
      const row = document.createElement('article');
      row.className = 'archive-result';
      const meta = document.createElement('p');
      meta.className = 'kicker';
      meta.textContent = `${s.category} / ${s.publishers.join(', ')} / ${s.published_at.slice(0, 10)}`;
      const heading = document.createElement('h3');
      const link = document.createElement('a');
      link.href = `./s/${s.id}.html`;
      link.textContent = s.title;
      heading.append(link);
      row.append(meta, heading);
      fragment.append(row);
    });
    results.append(fragment);
    shown += 30;
    more.hidden = shown >= matches.length;
  }
  more.addEventListener('click', renderMore);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const current = ++generation;
    status.textContent = 'Searching all archive months…';
    more.hidden = true;
    try {
      if (!cache) {
        const months = await getJSON('./archive/manifest.json');
        // Sequential loading bounds parallel requests as the archive grows.
        const accumulated = [];
        for (const month of months) accumulated.push(...await getJSON(`./archive/${month}.json`));
        cache = accumulated;
      }
      if (current !== generation) return;
      const terms = document.getElementById('search').value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
      matches = cache.filter((s) => terms.every((term) => `${s.title} ${s.category} ${s.publishers.join(' ')}`.toLocaleLowerCase().includes(term))).sort((a, b) => b.published_at.localeCompare(a.published_at));
      results.replaceChildren();
      shown = 0;
      status.textContent = `${matches.length} ${matches.length === 1 ? 'story' : 'stories'} found across the entire archive.`;
      renderMore();
    } catch (_) {
      if (current === generation) status.textContent = 'The archive could not be loaded. Try again, or browse the monthly pages below.';
    }
  });
}
