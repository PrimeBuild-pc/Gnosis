const request = async (url, options = {}) => {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText);
  return response.json();
};

const showError = (element, error) => {
  element.textContent = `Errore: ${error.message}`;
  element.className = 'error';
};

document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('nav button, .view').forEach(node => node.classList.remove('active'));
  button.classList.add('active');
  document.getElementById(button.dataset.view).classList.add('active');
}));

document.getElementById('question-form').addEventListener('submit', async event => {
  event.preventDefault();
  const answer = document.getElementById('answer');
  answer.className = '';
  answer.textContent = 'Ricerca in corso…';
  try {
    const data = await request('/api/chat', {method: 'POST', body: JSON.stringify({question: document.getElementById('question').value})});
    answer.textContent = data.answer;
    if (data.sources.length) {
      const list = document.createElement('ul');
      data.sources.forEach(source => {
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = source.url || '#';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = `${source.id} — ${source.platform}/${source.community}, ${source.author}`;
        item.append(link);
        list.append(item);
      });
      answer.append(list);
    }
  } catch (error) { showError(answer, error); }
});

const loadDigests = async () => {
  const target = document.getElementById('digest-list');
  try {
    const data = await request('/api/digests');
    target.replaceChildren(...data.map(digest => {
      const article = document.createElement('article');
      article.textContent = `${new Date(digest.period_start).toLocaleDateString()} – ${new Date(digest.period_end).toLocaleDateString()}\n\n${digest.markdown}`;
      return article;
    }));
  } catch (error) { showError(target, error); }
};

const loadSources = async () => {
  const target = document.getElementById('source-list');
  try {
    const data = await request('/api/sources');
    target.replaceChildren(...data.map(source => {
      const item = document.createElement('div');
      item.className = 'source';
      item.textContent = `${source.platform} — ${source.name} (${source.enabled ? 'attiva' : 'disattivata'})`;
      return item;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('refresh-digests').addEventListener('click', loadDigests);
document.getElementById('refresh-sources').addEventListener('click', loadSources);
