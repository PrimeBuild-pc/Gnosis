// Ogni nodo viene costruito con createElement e textContent: Gnosis ingerisce contenuti di
// terze parti (autori, nomi di canale, entita' estratte dall'LLM) e nulla di tutto cio' deve
// poter finire nel DOM come HTML.

const request = async (url, options = {}) => {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText);
  return response.json();
};

const showError = (element, error) => {
  element.textContent = `${t('error')}: ${error.message}`;
  element.className = 'error';
};

const el = (tag, options = {}) => {
  const node = document.createElement(tag);
  if (options.text !== undefined) node.textContent = options.text;
  if (options.className) node.className = options.className;
  if (options.i18n) node.dataset.i18n = options.i18n;
  return node;
};

// --- contesto selezionato ---------------------------------------------------

let workspaces = [];
const workspaceId = () => {
  const raw = localStorage.getItem('gnosis-workspace');
  return raw && raw !== 'all' ? Number(raw) : null;
};
const scopeQuery = () => (workspaceId() === null ? '' : `?workspace_id=${workspaceId()}`);

const renderWorkspaceSelect = () => {
  const select = document.getElementById('workspace-select');
  const current = localStorage.getItem('gnosis-workspace') || 'all';
  select.replaceChildren(
    ...[{id: 'all', name: t('workspace.all')}, ...workspaces].map(item => {
      const option = el('option', {text: item.name});
      option.value = String(item.id);
      option.selected = String(item.id) === current;
      return option;
    }),
  );
};

const loadWorkspaces = async () => {
  try {
    workspaces = await request('/api/workspaces');
  } catch {
    workspaces = [];
  }
  renderWorkspaceSelect();
  const names = document.getElementById('workspace-names');
  names.replaceChildren(...workspaces.map(w => {
    const option = el('option');
    option.value = w.name;
    return option;
  }));
  renderWorkspaceList();
};

document.getElementById('workspace-select').addEventListener('change', event => {
  localStorage.setItem('gnosis-workspace', event.target.value);
  refreshScopedViews();
});

const refreshScopedViews = () => {
  loadDigests();
  loadSources();
  loadStatus();
  document.getElementById('answer').replaceChildren();
};

// --- lingua -----------------------------------------------------------------

const languageSelect = document.getElementById('language-select');
languageSelect.replaceChildren(...LANGUAGES.map(([code, label]) => {
  const option = el('option', {text: label});
  option.value = code;
  option.selected = code === currentLanguage;
  return option;
}));
languageSelect.addEventListener('change', event => setLanguage(event.target.value));

// Le viste costruite in JavaScript non hanno data-i18n, quindi vanno ridisegnate a mano.
document.addEventListener('gnosis:language', () => {
  renderWorkspaceSelect();
  renderWorkspaceList();
  loadSetup();
  loadConfig();
  loadSources();
  loadDigests();
  loadStatus();
  loadIgnored();
});

// --- navigazione ------------------------------------------------------------

document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('nav button, .view').forEach(node => node.classList.remove('active'));
  button.classList.add('active');
  document.getElementById(button.dataset.view).classList.add('active');
}));

// --- chat -------------------------------------------------------------------

document.getElementById('question-form').addEventListener('submit', async event => {
  event.preventDefault();
  const answer = document.getElementById('answer');
  answer.className = '';
  answer.textContent = t('chat.searching');
  try {
    const data = await request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        question: document.getElementById('question').value,
        workspace_id: workspaceId(),
      }),
    });
    answer.replaceChildren(el('p', {text: data.answer}));
    if (data.sources.length) {
      const list = el('ul');
      data.sources.forEach(source => {
        const item = el('li');
        if (source.url) {
          const link = el('a', {text: `[M${source.id}] ${source.community}`});
          link.href = source.url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          item.append(link);
        } else {
          item.textContent = `[M${source.id}] ${source.community}`;
        }
        list.append(item);
      });
      answer.append(list);
    } else {
      answer.append(el('p', {className: 'hint', text: t('chat.noSources')}));
    }
  } catch (error) { showError(answer, error); }
});

// --- digest -----------------------------------------------------------------

const loadDigests = async () => {
  const target = document.getElementById('digest-list');
  try {
    const data = await request(`/api/digests${scopeQuery()}`);
    if (!data.length) {
      target.textContent = t('digests.empty');
      target.className = 'hint';
      return;
    }
    target.className = '';
    target.replaceChildren(...data.map(digest => {
      const article = el('article');
      const period = new Date(digest.period_start).toLocaleDateString(currentLanguage);
      const title = digest.workspace_name ? `${period} — ${digest.workspace_name}` : period;
      article.append(el('strong', {text: title}), el('p', {text: digest.markdown}));
      return article;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('refresh-digests').addEventListener('click', loadDigests);

document.getElementById('run-digest').addEventListener('click', async () => {
  const result = document.getElementById('digest-result');
  result.className = 'hint';
  result.textContent = t('digests.running');
  try {
    const data = await request(`/api/digests/run${scopeQuery()}`, {method: 'POST'});
    result.textContent = data.id ? '' : t('digests.noMessages');
    loadDigests();
  } catch (error) { showError(result, error); }
});

// --- sorgenti ---------------------------------------------------------------

const loadSources = async () => {
  const target = document.getElementById('source-list');
  try {
    const data = await request('/api/sources');
    const visible = workspaceId() === null
      ? data
      : data.filter(source => source.workspace_id === workspaceId());
    if (!visible.length) {
      target.textContent = t('sources.none');
      target.className = 'hint';
      return;
    }
    target.className = '';
    target.replaceChildren(...visible.map(source => {
      const row = el('div', {className: 'source'});
      const label = `${source.platform} · ${source.name}`;
      row.append(el('strong', {text: label}));
      const detail = [
        source.workspace_name || t('workspace.all'),
        (source.topics || []).join(', '),
        source.enabled ? '✓' : '✗',
      ].filter(Boolean).join(' — ');
      row.append(el('p', {className: 'hint', text: detail}));
      return row;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('refresh-sources').addEventListener('click', loadSources);

const loadAvailableSources = async () => {
  const platform = document.getElementById('source-platform').value;
  const select = document.getElementById('source-pick');
  const hint = document.getElementById('source-pick-hint');
  const manual = el('option', {text: t('sources.pickManual')});
  manual.value = '';
  if (platform === 'reddit') {
    select.replaceChildren(manual);
    hint.textContent = '';
    return;
  }
  try {
    const data = await request(`/api/available-sources?platform=${platform}`);
    if (!data.length) {
      select.replaceChildren(manual);
      hint.textContent = t('sources.pickEmpty');
      return;
    }
    hint.textContent = '';
    const placeholder = el('option', {text: t('sources.pickPlaceholder')});
    placeholder.value = '';
    select.replaceChildren(placeholder, ...data.map(item => {
      const option = el('option', {
        text: item.workspace_name ? `${item.name} — ${item.workspace_name}` : item.name,
      });
      option.value = item.external_id;
      option.dataset.name = item.name;
      option.dataset.workspace = item.workspace_name || '';
      return option;
    }), manual);
  } catch (error) { showError(hint, error); }
};

document.getElementById('source-platform').addEventListener('change', loadAvailableSources);

// Scegliere dalla tendina riempie ID, nome e workspace: restano modificabili a mano.
document.getElementById('source-pick').addEventListener('change', event => {
  const option = event.target.selectedOptions[0];
  if (!option || !option.value) return;
  document.getElementById('source-id').value = option.value;
  document.getElementById('source-name').value = option.dataset.name || '';
  if (option.dataset.workspace) {
    document.getElementById('source-workspace').value = option.dataset.workspace;
  }
});

document.getElementById('source-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('source-form-result');
  result.className = '';
  try {
    await request('/api/sources', {
      method: 'POST',
      body: JSON.stringify({
        platform: document.getElementById('source-platform').value,
        external_id: document.getElementById('source-id').value.trim(),
        name: document.getElementById('source-name').value.trim(),
        enabled: document.getElementById('source-enabled').checked,
        workspace: document.getElementById('source-workspace').value.trim(),
        topics: document.getElementById('source-topics').value
          .split(',').map(value => value.trim()).filter(Boolean),
      }),
    });
    result.textContent = t('sources.save');
    loadSources();
    loadWorkspaces();
  } catch (error) { showError(result, error); }
});

// --- checklist di setup -----------------------------------------------------

const loadSetup = async () => {
  const target = document.getElementById('setup-steps');
  try {
    const steps = await request('/api/setup');
    target.replaceChildren(...steps.map(step => {
      const card = el('div', {className: step.ready ? 'setup-step ready' : 'setup-step'});
      const title = `${step.ready ? '✓' : '○'} ${t(`setup.${step.key}`)}` +
        (step.required ? ` (${t('settings.required')})` : '');
      card.append(el('div', {className: 'setup-title', text: title}));

      const state = el('p', {className: 'hint'});
      if (!step.ready) state.textContent = `${t('settings.missing')} ${step.fields.join(', ')}`;
      else if (step.sources === 0) state.textContent = t('settings.noSources');
      else if (step.sources) state.textContent = t('settings.sourcesActive', {n: step.sources});
      else state.textContent = t('settings.ready');
      card.append(state);

      card.append(el('p', {className: 'hint', text: t(`setup.${step.key}.hint`)}));
      return card;
    }));
  } catch (error) { showError(target, error); }
};

// --- configurazione a sezioni ----------------------------------------------

const SECTION_ORDER = ['llm', 'discord', 'telegram', 'reddit'];

const loadConfig = async () => {
  const target = document.getElementById('config-sections');
  try {
    const fields = await request('/api/config');
    const bySection = new Map(SECTION_ORDER.map(name => [name, []]));
    fields.forEach(field => bySection.get(field.section)?.push(field));

    target.replaceChildren(...SECTION_ORDER.map(section => {
      const block = el('section', {className: 'config-section'});
      block.append(el('h4', {text: t(`section.${section}`)}));
      block.append(el('p', {className: 'hint', text: t(`section.${section}.intro`)}));

      bySection.get(section).forEach(field => {
        const wrapper = el('div', {className: 'field'});
        const header = el('div', {className: 'field-header'});
        const label = el('label', {text: t(`field.${field.key}.label`)});
        label.htmlFor = `config-${field.key}`;
        const info = el('button', {className: 'info', text: 'i'});
        info.type = 'button';
        info.title = t('settings.info');
        header.append(label, info);

        const input = el('input');
        input.id = `config-${field.key}`;
        input.dataset.key = field.key;
        input.placeholder = field.value || '—';
        if (field.secret) input.type = 'password';

        const help = el('p', {className: 'hint help', text: t(`field.${field.key}.help`)});
        help.hidden = true;
        info.addEventListener('click', () => { help.hidden = !help.hidden; });

        wrapper.append(header, input, help);
        block.append(wrapper);
      });
      return block;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('config-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('config-result');
  result.className = '';
  const values = {};
  document.querySelectorAll('#config-sections input').forEach(input => {
    if (input.value.trim()) values[input.dataset.key] = input.value.trim();
  });
  if (!Object.keys(values).length) {
    result.textContent = t('settings.noChange');
    return;
  }
  try {
    const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
    result.textContent = saved.restart_required ? t('settings.savedRestart') : t('settings.savedLive');
    loadConfig();
    loadSetup();
  } catch (error) { showError(result, error); }
});

// --- workspace --------------------------------------------------------------

const renderWorkspaceList = () => {
  const target = document.getElementById('workspace-list');
  if (!workspaces.length) {
    target.textContent = t('workspace.none');
    target.className = 'hint';
    return;
  }
  target.className = '';
  target.replaceChildren(...workspaces.map(workspace => {
    const row = el('div', {className: 'source'});
    row.append(el('strong', {text: workspace.name}));
    const detail = [
      workspace.platform || '',
      `${workspace.active_sources} ${t('workspace.activeSources')}`,
      workspace.digest_webhook ? 'webhook ✓' : '',
    ].filter(Boolean).join(' — ');
    row.append(el('p', {className: 'hint', text: detail}));

    const remove = el('button', {className: 'danger', text: t('workspace.delete')});
    remove.type = 'button';
    remove.addEventListener('click', async () => {
      if (!confirm(t('workspace.deleteConfirm'))) return;
      await request(`/api/workspaces/${workspace.id}`, {method: 'DELETE'});
      loadWorkspaces();
    });
    row.append(remove);

    const edit = el('button', {text: t('workspace.save')});
    edit.type = 'button';
    edit.textContent = '✎';
    edit.addEventListener('click', () => {
      document.getElementById('workspace-name').value = workspace.name;
      document.getElementById('workspace-platform').value = workspace.platform || '';
      document.getElementById('workspace-external').value = workspace.external_id || '';
      document.getElementById('workspace-roles').value = (workspace.allowed_role_ids || []).join(',');
      document.getElementById('workspace-webhook').value = workspace.digest_webhook || '';
      document.getElementById('workspace-telegram-chat').value = workspace.digest_telegram_chat_id || '';
    });
    row.append(edit);
    return row;
  }));
};

document.getElementById('workspace-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('workspace-result');
  result.className = '';
  const roles = document.getElementById('workspace-roles').value
    .split(',').map(value => value.trim()).filter(Boolean);
  try {
    await request('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('workspace-name').value.trim(),
        platform: document.getElementById('workspace-platform').value || null,
        external_id: document.getElementById('workspace-external').value.trim() || null,
        allowed_role_ids: roles,
        digest_webhook: document.getElementById('workspace-webhook').value.trim(),
        digest_telegram_chat_id: document.getElementById('workspace-telegram-chat').value.trim(),
      }),
    });
    result.textContent = t('workspace.save');
    loadWorkspaces();
  } catch (error) { showError(result, error); }
});

// --- retention, wipe, ignorati ---------------------------------------------

const loadRetention = async () => {
  try {
    const data = await request('/api/settings/retention');
    document.getElementById('retention-days').value = data.days ?? '';
  } catch { /* la sezione resta vuota, non vale un errore a schermo */ }
};

document.getElementById('retention-form').addEventListener('submit', async event => {
  event.preventDefault();
  const result = document.getElementById('retention-result');
  result.className = '';
  const raw = document.getElementById('retention-days').value.trim();
  try {
    await request('/api/settings/retention', {
      method: 'POST',
      body: JSON.stringify({days: raw ? Number(raw) : null}),
    });
    result.textContent = t('retention.save');
  } catch (error) { showError(result, error); }
});

document.getElementById('wipe-button').addEventListener('click', async () => {
  const result = document.getElementById('wipe-result');
  result.className = '';
  if (!confirm(t('wipe.confirm'))) return;
  try {
    await request('/api/wipe', {method: 'POST', body: JSON.stringify({confirm: 'WIPE'})});
    result.textContent = t('wipe.button');
    loadSources();
  } catch (error) { showError(result, error); }
});

const loadIgnored = async () => {
  const target = document.getElementById('ignored-list');
  try {
    const data = await request('/api/ignored-authors');
    if (!data.length) {
      target.textContent = t('ignored.none');
      target.className = 'hint';
      return;
    }
    target.className = '';
    target.replaceChildren(...data.map(entry => {
      const row = el('div', {className: 'source'});
      row.append(el('span', {text: `${entry.platform} · ${entry.author_id}`}));
      const remove = el('button', {text: t('ignored.remove')});
      remove.type = 'button';
      remove.addEventListener('click', async () => {
        await request(`/api/ignored-authors/${entry.platform}/${entry.author_id}`, {method: 'DELETE'});
        loadIgnored();
      });
      row.append(remove);
      return row;
    }));
  } catch (error) { showError(target, error); }
};

document.getElementById('ignore-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    await request('/api/ignored-authors', {
      method: 'POST',
      body: JSON.stringify({
        platform: document.getElementById('ignore-platform').value,
        author_id: document.getElementById('ignore-author').value.trim(),
      }),
    });
    document.getElementById('ignore-author').value = '';
    loadIgnored();
  } catch (error) { showError(document.getElementById('ignored-list'), error); }
});

// --- stato ------------------------------------------------------------------

const loadStatus = async () => {
  const workers = document.getElementById('worker-status');
  const sources = document.getElementById('source-status');
  const usage = document.getElementById('usage-status');
  try {
    const data = await request('/api/status');
    workers.replaceChildren(...data.workers.map(worker => {
      const row = el('div', {className: 'source'});
      row.append(el('strong', {text: `${worker.component}: ${worker.status}`}));
      if (worker.detail) row.append(el('p', {className: 'error', text: worker.detail}));
      return row;
    }));

    const visible = workspaceId() === null
      ? data.sources
      : data.sources.filter(source => {
          const workspace = workspaces.find(w => w.id === workspaceId());
          return workspace && source.workspace_name === workspace.name;
        });
    sources.replaceChildren(...visible.map(source => {
      const row = el('div', {className: 'source'});
      row.append(el('strong', {text: `${source.platform} · ${source.name}`}));
      const last = source.last_processed_at
        ? new Date(source.last_processed_at).toLocaleString(currentLanguage)
        : t('status.never');
      row.append(el('p', {
        className: 'hint',
        text: `${t('status.lastActivity')}: ${last} — ${source.pending} ${t('status.pending')}`,
      }));
      return row;
    }));

    const stats = await request(`/api/usage`);
    usage.replaceChildren(...stats.map(entry => el('div', {
      className: 'source',
      text: `${entry.model}: ${entry.prompt_tokens} + ${entry.completion_tokens}`,
    })));
  } catch (error) { showError(workers, error); }
};

document.getElementById('refresh-status').addEventListener('click', loadStatus);

// --- grafo ------------------------------------------------------------------

const loadEntityDetail = async id => {
  const target = document.getElementById('entity-detail');
  try {
    const data = await request(`/api/entities/${id}`);
    target.replaceChildren(el('strong', {text: `${data.name} (${data.type})`}));
    (data.mentions || []).forEach(mention => {
      const row = el('div', {className: 'source', text: mention.text});
      target.append(row);
    });
  } catch (error) { showError(target, error); }
};

const loadEntities = async (search = '') => {
  const target = document.getElementById('entity-list');
  try {
    const data = await request(`/api/entities?search=${encodeURIComponent(search)}`);
    if (!data.length) {
      target.textContent = t('graph.none');
      target.className = 'hint';
      return;
    }
    target.className = '';
    target.replaceChildren(...data.map(entity => {
      const item = el('div', {
        className: 'source',
        text: `${entity.name} (${entity.type}) — ${entity.mentions} ${t('graph.mentions')}`,
      });
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

// --- avvio ------------------------------------------------------------------

document.documentElement.lang = currentLanguage;
applyTranslations();
loadWorkspaces();
loadSetup();
loadConfig();
loadSources();
loadAvailableSources();
loadDigests();
loadRetention();
loadIgnored();
loadEntities();
