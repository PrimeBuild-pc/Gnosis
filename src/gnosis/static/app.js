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

document.getElementById('source-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('source-form-result');
  result.className = '';
  try {
    const topics = document.getElementById('source-topics').value
      .split(',').map(topic => topic.trim()).filter(Boolean);
    await request('/api/sources', {method: 'POST', body: JSON.stringify({
      platform: document.getElementById('source-platform').value,
      external_id: document.getElementById('source-id').value,
      name: document.getElementById('source-name').value,
      enabled: document.getElementById('source-enabled').checked,
      topics,
    })});
    result.textContent = 'Sorgente salvata.';
    document.getElementById('source-form').reset();
    document.getElementById('source-enabled').checked = true;
    loadSources();
  } catch (error) { showError(result, error); }
});

const CONFIG_LABELS = {
  GNOSIS_CHAT_API_KEY: 'Chiave API chat',
  GNOSIS_CHAT_BASE_URL: 'Base URL chat (OpenAI-compatibile)',
  OPENAI_CHAT_MODEL: 'Modello chat',
  OPENAI_API_KEY: 'Chiave API OpenAI (embedding/fallback)',
  OPENAI_BASE_URL: 'Base URL OpenAI',
  GNOSIS_EMBEDDING_PROVIDER: 'Provider embedding (local/openai)',
  TELEGRAM_API_ID: 'Telegram API ID',
  TELEGRAM_API_HASH: 'Telegram API hash',
  TELEGRAM_BOT_TOKEN: 'Token bot Telegram',
  GNOSIS_TELEGRAM_ALLOWED_USERS: 'ID utenti Telegram autorizzati (virgola)',
  DISCORD_BOT_TOKEN: 'Token bot Discord',
  GNOSIS_DISCORD_ALLOWED_ROLE_IDS: 'ID ruoli Discord autorizzati (virgola)',
  REDDIT_CLIENT_ID: 'Reddit client ID',
  REDDIT_CLIENT_SECRET: 'Reddit client secret',
  GNOSIS_DIGEST_TELEGRAM_CHAT_ID: 'Chat Telegram per il digest automatico (facoltativo)',
  GNOSIS_DIGEST_DISCORD_WEBHOOK: 'Webhook Discord per il digest automatico (facoltativo)',
};

const loadSetup = async () => {
  const target = document.getElementById('setup-steps');
  try {
    const steps = await request('/api/setup');
    target.replaceChildren(...steps.map(step => {
      const card = document.createElement('div');
      card.className = step.ready ? 'setup-step ready' : 'setup-step';

      const title = document.createElement('div');
      title.className = 'setup-title';
      title.textContent = `${step.ready ? '✓' : '○'} ${step.label}`;
      if (step.required) title.textContent += ' (obbligatorio)';
      card.append(title);

      const state = document.createElement('p');
      if (!step.ready) {
        state.textContent = `Da configurare: ${step.fields.join(', ')}`;
      } else if (step.sources === 0) {
        state.textContent = 'Credenziali presenti, ma nessuna sorgente attiva: aggiungine una nel tab Sorgenti.';
        state.className = 'hint';
      } else if (step.sources) {
        state.textContent = `Attiva su ${step.sources} sorgent${step.sources === 1 ? 'e' : 'i'}.`;
        state.className = 'hint';
      } else {
        state.textContent = 'Configurato.';
        state.className = 'hint';
      }
      card.append(state);

      const hint = document.createElement('p');
      hint.className = 'hint';
      hint.textContent = `${step.hint} `;
      const link = document.createElement('a');
      link.href = step.docs;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Apri';
      hint.append(link);
      card.append(hint);
      return card;
    }));
  } catch (error) { showError(target, error); }
};

const loadConfig = async () => {
  const target = document.getElementById('config-fields');
  try {
    const data = await request('/api/config');
    target.replaceChildren(...Object.entries(data).map(([key, current]) => {
      const wrapper = document.createElement('label');
      wrapper.textContent = CONFIG_LABELS[key] || key;
      const input = document.createElement('input');
      input.dataset.key = key;
      input.placeholder = current ? `attuale: ${current}` : 'non impostato';
      wrapper.append(input);
      return wrapper;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('config-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('config-result');
  result.className = '';
  const values = {};
  document.querySelectorAll('#config-fields input').forEach(input => {
    if (input.value.trim()) values[input.dataset.key] = input.value.trim();
  });
  if (!Object.keys(values).length) {
    result.textContent = 'Nessuna modifica da salvare.';
    return;
  }
  try {
    const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
    result.textContent = saved.restart_required
      ? 'Configurazione salvata. Riavvia lo stack (docker compose restart) per applicarla.'
      : 'Configurazione salvata e applicata subito.';
    loadConfig();
    loadSetup();
  } catch (error) { showError(result, error); }
});

const loadRetention = async () => {
  try {
    const data = await request('/api/settings/retention');
    document.getElementById('retention-days').value = data.days ?? '';
  } catch (error) { showError(document.getElementById('retention-result'), error); }
};

document.getElementById('retention-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('retention-result');
  result.className = '';
  const raw = document.getElementById('retention-days').value;
  try {
    await request('/api/settings/retention', {method: 'POST', body: JSON.stringify({
      days: raw ? parseInt(raw, 10) : null,
    })});
    result.textContent = 'Conservazione aggiornata.';
  } catch (error) { showError(result, error); }
});

document.getElementById('wipe-button').addEventListener('click', async () => {
  const result = document.getElementById('wipe-result');
  result.className = '';
  const confirmation = prompt('Questa azione è irreversibile. Scrivi WIPE per confermare la cancellazione di tutti i messaggi raccolti.');
  if (confirmation !== 'WIPE') {
    result.textContent = 'Annullato.';
    return;
  }
  try {
    await request('/api/wipe', {method: 'POST', body: JSON.stringify({confirm: confirmation})});
    result.textContent = 'Memoria cancellata.';
  } catch (error) { showError(result, error); }
});

const loadIgnored = async () => {
  const target = document.getElementById('ignored-list');
  try {
    const data = await request('/api/ignored-authors');
    if (!data.length) {
      target.textContent = 'Nessun utente ignorato.';
      return;
    }
    target.replaceChildren(...data.map(entry => {
      const item = document.createElement('div');
      item.className = 'source';
      item.textContent = `${entry.platform} — ${entry.author_id} `;
      const removeButton = document.createElement('button');
      removeButton.textContent = 'Rimuovi';
      removeButton.addEventListener('click', async () => {
        await request(`/api/ignored-authors/${entry.platform}/${entry.author_id}`, {method: 'DELETE'});
        loadIgnored();
      });
      item.append(removeButton);
      return item;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('ignore-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    await request('/api/ignored-authors', {method: 'POST', body: JSON.stringify({
      platform: document.getElementById('ignore-platform').value,
      author_id: document.getElementById('ignore-author').value,
    })});
    document.getElementById('ignore-form').reset();
    loadIgnored();
  } catch (error) { showError(document.getElementById('ignored-list'), error); }
});

const loadStatus = async () => {
  const workerTarget = document.getElementById('worker-status');
  const sourceTarget = document.getElementById('source-status');
  try {
    const data = await request('/api/status');
    workerTarget.replaceChildren(...(data.workers.length ? data.workers.map(w => {
      const item = document.createElement('div');
      item.className = 'source';
      item.textContent = `${w.component}: ${w.status}${w.detail ? ' — ' + w.detail : ''} (${new Date(w.updated_at).toLocaleString()})`;
      return item;
    }) : [Object.assign(document.createElement('div'), {textContent: 'Nessun dato ancora (il worker non ha ancora fatto un ciclo).'})]));
    sourceTarget.replaceChildren(...data.sources.map(s => {
      const item = document.createElement('div');
      item.className = 'source';
      const last = s.last_processed_at ? new Date(s.last_processed_at).toLocaleString() : 'mai';
      item.textContent = `${s.platform} — ${s.name} (${s.enabled ? 'attiva' : 'disattivata'}), ultimo messaggio: ${last}, in coda: ${s.pending}`;
      return item;
    }));
  } catch (error) { showError(workerTarget, error); }
};

const loadUsage = async () => {
  const target = document.getElementById('usage-status');
  try {
    const data = await request('/api/usage');
    if (!data.length) {
      target.textContent = 'Nessun utilizzo registrato negli ultimi 30 giorni.';
      return;
    }
    target.replaceChildren(...data.map(row => {
      const item = document.createElement('div');
      item.className = 'source';
      item.textContent = `${row.kind}/${row.model}: ${row.requests} richieste, ${row.prompt_tokens} token prompt, ${row.completion_tokens} token risposta`;
      return item;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('refresh-status').addEventListener('click', () => { loadStatus(); loadUsage(); });

const textEl = (tag, text, className) => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
};

const loadEntityDetail = async entityId => {
  const target = document.getElementById('entity-detail');
  target.className = '';
  try {
    const data = await request(`/api/entities/${entityId}`);

    const heading = document.createElement('h3');
    heading.append(`${data.entity.name} `, textEl('span', `(${data.entity.type})`, 'hint'));

    const relationsHeading = textEl('h4', 'Relazioni');
    const relationsBody = data.relations.length
      ? (() => {
          const list = document.createElement('ul');
          list.append(...data.relations.map(r =>
            textEl('li', `${r.source_name} — ${r.relation} — ${r.target_name}`)
          ));
          return list;
        })()
      : textEl('p', 'Nessuna relazione registrata.', 'hint');

    const mentionsHeading = textEl('h4', 'Menzioni');
    const mentionsBody = data.mentions.length
      ? (() => {
          const list = document.createElement('ul');
          list.append(...data.mentions.map(m => {
            const date = new Date(m.sent_at).toLocaleString();
            const item = document.createElement('li');
            if (m.url) {
              const link = document.createElement('a');
              link.href = m.url;
              link.target = '_blank';
              link.rel = 'noopener noreferrer';
              link.textContent = `${m.platform}/${m.source_name}`;
              item.append(link, `, ${m.author}, ${date}`);
            } else {
              item.textContent = `${m.platform}/${m.source_name}, ${m.author}, ${date}`;
            }
            return item;
          }));
          return list;
        })()
      : textEl('p', 'Nessuna menzione registrata.', 'hint');

    target.replaceChildren(heading, relationsHeading, relationsBody, mentionsHeading, mentionsBody);
  } catch (error) { showError(target, error); }
};

const loadEntities = async (search = '') => {
  const target = document.getElementById('entity-list');
  try {
    const data = await request(`/api/entities?search=${encodeURIComponent(search)}`);
    if (!data.length) {
      target.textContent = 'Nessuna entità trovata.';
      return;
    }
    target.replaceChildren(...data.map(entity => {
      const item = document.createElement('div');
      item.className = 'source';
      item.textContent = `${entity.name} (${entity.type}) — ${entity.mentions} menzioni`;
      item.style.cursor = 'pointer';
      item.addEventListener('click', () => loadEntityDetail(entity.id));
      return item;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('entity-search-form').addEventListener('submit', event => {
  event.preventDefault();
  loadEntities(document.getElementById('entity-search').value.trim());
});

loadConfig();
loadSetup();
loadRetention();
loadIgnored();
loadEntities();
