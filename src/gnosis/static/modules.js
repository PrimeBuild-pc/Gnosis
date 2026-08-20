// Moduli di Gnosis. Ognuno disegna una pagina intera dentro il contenitore del guscio.
// Il guscio non sa nulla di cosa facciano: conosce solo id, gruppo, icona ed etichetta.

const PLATFORMS = ['discord', 'telegram', 'reddit'];

// ---------------------------------------------------------------- panoramica

const renderOverview = async container => {
  container.append(moduleHead('nav.overview', 'settings.setupIntro'));
  const box = el('div');
  container.append(box);
  try {
    const [steps, stats] = await Promise.all([
      request('/api/setup'),
      request(`/api/stats${AppState.scopeQuery()}`),
    ]);

    const summary = card('overview.collected');
    const workspace = AppState.currentWorkspace();
    summary.append(el('p', {
      className: 'hint',
      text: t('overview.counts', {
        sources: stats.sources, messages: stats.messages, digests: stats.digests,
      }),
    }));
    summary.append(el('p', {
      className: 'hint faint',
      text: workspace ? t('overview.scoped', {name: workspace.name}) : t('overview.global'),
    }));
    box.append(summary);

    const checklist = card('settings.setupTitle');
    steps.forEach(step => {
      const row = el('div', {className: step.ready ? 'step ready' : 'step'});
      row.append(el('span', {className: 'step-mark', text: step.ready ? '✓' : '○'}));
      const body = el('div', {className: 'step-body'});
      body.append(el('strong', {
        text: t(`setup.${step.key}`) + (step.required ? ` · ${t('settings.required')}` : ''),
      }));
      let state;
      if (!step.ready) state = `${t('settings.missing')} ${step.fields.join(', ')}`;
      else if (step.sources === 0) state = t('settings.noSources');
      else if (step.sources) state = t('settings.sourcesActive', {n: step.sources});
      else state = t('settings.ready');
      body.append(el('p', {className: 'hint', text: state}));
      body.append(el('p', {className: 'hint faint', text: t(`setup.${step.key}.hint`)}));
      row.append(body);
      checklist.append(row);
    });
    box.append(checklist);
  } catch (error) { showError(box, error); }
};

// ---------------------------------------------------------------- chat

const renderChat = async container => {
  container.append(moduleHead('nav.chat', 'chat.intro'));

  const form = el('form');
  const label = el('label', {text: t('chat.question')});
  const textarea = el('textarea');
  textarea.maxLength = 4000;
  textarea.required = true;
  textarea.placeholder = t('chat.placeholder');
  label.append(textarea);
  const submit = el('button', {className: 'primary', text: t('chat.submit'), type: 'submit'});
  form.append(label, submit);

  const answer = el('div', {className: 'card answer'});
  answer.hidden = true;
  container.append(form, answer);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    answer.hidden = false;
    answer.replaceChildren(el('p', {className: 'hint', text: t('chat.searching')}));
    try {
      const data = await request('/api/chat', {
        method: 'POST',
        body: JSON.stringify({question: textarea.value, workspace_id: AppState.workspaceId()}),
      });
      answer.replaceChildren(el('p', {text: data.answer}));
      if (data.sources.length) {
        const list = el('ul', {className: 'citation-list'});
        data.sources.forEach(source => {
          const item = el('li');
          const text = `[M${source.id}] ${source.platform} · ${source.community} — ${source.author}`;
          if (source.url) {
            const link = el('a', {text});
            link.href = source.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            item.append(link);
          } else item.textContent = text;
          list.append(item);
        });
        answer.append(list);
      } else {
        answer.append(el('p', {className: 'hint faint', text: t('chat.noSources')}));
      }
    } catch (error) { showError(answer, error); }
  });
};

// ---------------------------------------------------------------- digest

const renderDigests = async container => {
  container.append(moduleHead('nav.digests', 'digests.intro'));

  const actions = el('div', {className: 'row actions'});
  const run = el('button', {className: 'primary', text: t('digests.run')});
  const refresh = el('button', {className: 'ghost', text: t('digests.refresh')});
  actions.append(run, refresh);
  const status = el('p', {className: 'hint'});
  const list = el('div');
  container.append(actions, status, list);

  const load = async () => {
    try {
      const data = await request(`/api/digests${AppState.scopeQuery()}`);
      if (!data.length) { list.replaceChildren(emptyState('digests.empty')); return; }
      list.replaceChildren(...data.map(digest => {
        const article = el('article');
        const period = new Date(digest.period_start).toLocaleDateString(currentLanguage);
        article.append(el('strong', {
          text: digest.workspace_name ? `${period} · ${digest.workspace_name}` : period,
        }));
        article.append(el('p', {text: digest.markdown}));
        return article;
      }));
    } catch (error) { showError(list, error); }
  };

  refresh.addEventListener('click', load);
  run.addEventListener('click', async () => {
    status.textContent = t('digests.running');
    try {
      const data = await request(`/api/digests/run${AppState.scopeQuery()}`, {method: 'POST'});
      status.textContent = data.id ? '' : t('digests.noMessages');
      load();
    } catch (error) { showError(status, error); }
  });
  load();
};

// ---------------------------------------------------------------- piattaforma

/** Una pagina per piattaforma: credenziali, impostazioni del server scelto, canali seguiti. */
const renderPlatform = platform => async container => {
  container.append(moduleHead(`section.${platform}`, `section.${platform}.intro`));

  const credentials = card('platform.credentials');
  const sourcesCard = card('platform.sources', `platform.sources.${platform}`);
  const serverCard = card('platform.serverSettings');
  container.append(credentials);
  if (platform === 'discord') container.append(serverCard);
  container.append(sourcesCard);

  // --- credenziali della sola piattaforma ---
  try {
    const fields = (await request('/api/config')).filter(item => item.section === platform);
    const form = el('form');
    fields.forEach(item => form.append(field({
      id: `config-${item.key}`,
      labelKey: `field.${item.key}.label`,
      helpKey: `field.${item.key}.help`,
      value: item.value,
      secret: item.secret,
    })));
    const save = el('button', {className: 'primary', text: t('settings.save'), type: 'submit'});
    const result = el('p', {className: 'hint'});
    form.append(save);
    credentials.append(el('p', {className: 'hint faint', text: t('settings.maskNote')}), form, result);

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = {};
      form.querySelectorAll('input').forEach(input => {
        if (input.value.trim()) values[input.dataset.key] = input.value.trim();
      });
      if (!Object.keys(values).length) { result.textContent = t('settings.noChange'); return; }
      try {
        const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
        result.textContent = saved.restart_required
          ? t('settings.savedRestart') : t('settings.savedLive');
        form.querySelectorAll('input').forEach(input => { input.value = ''; });
      } catch (error) { showError(result, error); }
    });
  } catch (error) { showError(credentials, error); }

  // --- impostazioni del server selezionato (solo Discord: ruoli e digest) ---
  if (platform === 'discord') {
    const workspace = AppState.currentWorkspace();
    if (!workspace) {
      serverCard.append(el('p', {className: 'hint callout', text: t('platform.pickServer')}));
    } else {
      serverCard.querySelector('h3').textContent =
        `${t('platform.serverSettings')} · ${workspace.name}`;
      const form = el('form');
      const roles = field({
        id: 'ws-roles', labelKey: 'workspace.roles', helpKey: 'workspace.rolesHelp',
      });
      const webhook = field({
        id: 'ws-webhook', labelKey: 'workspace.webhook', helpKey: 'workspace.webhookHelp',
      });
      const external = field({
        id: 'ws-external', labelKey: 'workspace.externalId', helpKey: 'workspace.externalIdHelp',
      });
      roles.querySelector('input').value = (workspace.allowed_role_ids || []).join(',');
      webhook.querySelector('input').value = workspace.digest_webhook || '';
      external.querySelector('input').value = workspace.external_id || '';
      const save = el('button', {className: 'primary', text: t('workspace.save'), type: 'submit'});
      const result = el('p', {className: 'hint'});
      form.append(external, roles, webhook, save);
      serverCard.append(form, result);

      form.addEventListener('submit', async event => {
        event.preventDefault();
        try {
          await request('/api/workspaces', {
            method: 'POST',
            body: JSON.stringify({
              name: workspace.name,
              platform: 'discord',
              external_id: external.querySelector('input').value.trim() || null,
              allowed_role_ids: roles.querySelector('input').value
                .split(',').map(v => v.trim()).filter(Boolean),
              digest_webhook: webhook.querySelector('input').value.trim(),
            }),
          });
          result.textContent = t('settings.savedRestart');
          Shell.reloadWorkspaces();
        } catch (error) { showError(result, error); }
      });
    }
  }

  // --- canali seguiti su questa piattaforma ---
  const list = el('div');
  sourcesCard.append(el('p', {className: 'hint callout accent', text: t('sources.commandNote')}));
  sourcesCard.append(list);

  const loadSources = async () => {
    try {
      const all = await request('/api/sources');
      const mine = all.filter(source => source.platform === platform)
        .filter(source => AppState.workspaceId() === null
          || source.workspace_id === AppState.workspaceId());
      if (!mine.length) { list.replaceChildren(emptyState('sources.none')); return; }
      list.replaceChildren(...mine.map(source => {
        const detail = [
          source.workspace_name || t('workspace.all'),
          (source.topics || []).join(', ') || t('sources.noTopics'),
        ].join(' · ');
        const row = listRow(source.name, detail);
        const toggle = el('button', {
          className: 'small ghost',
          text: source.enabled ? t('sources.disable') : t('sources.enable'),
        });
        toggle.addEventListener('click', async () => {
          await request('/api/sources', {
            method: 'POST',
            body: JSON.stringify({
              platform: source.platform,
              external_id: source.external_id,
              name: source.name,
              enabled: !source.enabled,
              workspace: source.workspace_name || '',
              topics: source.topics || [],
            }),
          });
          loadSources();
        });
        row.append(el('span', {className: source.enabled ? 'dot on' : 'dot off'}), toggle);
        return row;
      }));
    } catch (error) { showError(list, error); }
  };

  // --- aggiunta guidata: tendina dei canali che il bot vede davvero ---
  const form = el('form');
  const pickLabel = el('label', {text: t('sources.pick')});
  const pick = el('select');
  pickLabel.append(pick);
  const pickHint = el('p', {className: 'hint'});

  const idField = field({id: 'src-id', labelKey: 'sources.id', helpKey: 'sources.idHelp'});
  const nameField = field({id: 'src-name', labelKey: 'sources.name'});
  const wsField = field({id: 'src-workspace', labelKey: 'sources.workspace', helpKey: 'sources.workspaceHelp'});
  const topicsField = field({id: 'src-topics', labelKey: 'sources.topics', helpKey: 'sources.topicsHelp'});
  topicsField.querySelector('input').placeholder = 'AI, security';

  const save = el('button', {className: 'primary', text: t('sources.save'), type: 'submit'});
  const result = el('p', {className: 'hint'});
  form.append(pickLabel, pickHint, idField, nameField, wsField, topicsField, save);
  sourcesCard.append(el('h3', {text: t('sources.addTitle')}), form, result);

  if (platform !== 'reddit') {
    request(`/api/available-sources?platform=${platform}`).then(rows => {
      const manual = el('option', {text: t('sources.pickManual')});
      manual.value = '';
      if (!rows.length) {
        pick.replaceChildren(manual);
        pickHint.textContent = t('sources.pickEmpty');
        return;
      }
      const placeholder = el('option', {text: t('sources.pickPlaceholder')});
      placeholder.value = '';
      pick.replaceChildren(placeholder, ...rows.map(row => {
        const option = el('option', {
          text: row.workspace_name ? `${row.name} — ${row.workspace_name}` : row.name,
        });
        option.value = row.external_id;
        option.dataset.name = row.name;
        option.dataset.workspace = row.workspace_name || '';
        return option;
      }), manual);
      pickHint.textContent = t('sources.pickFound', {n: rows.length});
    }).catch(error => showError(pickHint, error));
  } else {
    pickLabel.hidden = true;
    pickHint.textContent = t('sources.redditManual');
  }

  pick.addEventListener('change', () => {
    const option = pick.selectedOptions[0];
    if (!option || !option.value) return;
    idField.querySelector('input').value = option.value;
    nameField.querySelector('input').value = option.dataset.name || '';
    if (option.dataset.workspace) wsField.querySelector('input').value = option.dataset.workspace;
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/sources', {
        method: 'POST',
        body: JSON.stringify({
          platform,
          external_id: idField.querySelector('input').value.trim(),
          name: nameField.querySelector('input').value.trim(),
          enabled: true,
          workspace: wsField.querySelector('input').value.trim(),
          topics: topicsField.querySelector('input').value
            .split(',').map(v => v.trim()).filter(Boolean),
        }),
      });
      result.textContent = t('sources.saved');
      form.querySelectorAll('input').forEach(input => { input.value = ''; });
      loadSources();
      Shell.reloadWorkspaces();
    } catch (error) { showError(result, error); }
  });

  loadSources();
};

// ---------------------------------------------------------------- stato

const renderStatus = async container => {
  container.append(moduleHead('nav.status', 'status.intro'));
  const connectors = card('status.connectors');
  const sources = card('status.sources');
  const usage = card('status.usage', 'status.usageNote');
  container.append(connectors, sources, usage);
  try {
    const data = await request('/api/status');
    data.workers.forEach(worker => {
      const row = listRow(worker.component, worker.detail || t(`status.${worker.status}`));
      row.prepend(el('span', {className: worker.status === 'ok' ? 'dot on' : 'dot warn'}));
      connectors.append(row);
    });
    if (!data.workers.length) connectors.append(emptyState('status.noWorkers'));

    const visible = data.sources.filter(source => {
      const workspace = AppState.currentWorkspace();
      return !workspace || source.workspace_name === workspace.name;
    });
    if (!visible.length) sources.append(emptyState('sources.none'));
    visible.forEach(source => {
      const last = source.last_processed_at
        ? new Date(source.last_processed_at).toLocaleString(currentLanguage)
        : t('status.never');
      sources.append(listRow(
        `${source.platform} · ${source.name}`,
        `${t('status.lastActivity')}: ${last} — ${source.pending} ${t('status.pending')}`,
      ));
    });

    const entries = await request('/api/usage');
    if (!entries.length) usage.append(emptyState('status.noUsage'));
    entries.forEach(entry => usage.append(listRow(
      entry.model, `${entry.prompt_tokens} + ${entry.completion_tokens} token`,
    )));
  } catch (error) { showError(connectors, error); }
};

// ---------------------------------------------------------------- grafo

const renderGraph = async container => {
  container.append(moduleHead('nav.graph', 'graph.intro'));
  container.append(el('p', {className: 'hint callout', text: t('graph.globalNote')}));

  const form = el('form');
  const input = el('input');
  input.placeholder = t('graph.search');
  form.append(input, el('button', {className: 'primary', text: t('graph.submit'), type: 'submit'}));
  const list = el('div');
  const detail = el('div');
  container.append(form, list, detail);

  const load = async (search = '') => {
    try {
      const data = await request(`/api/entities?search=${encodeURIComponent(search)}`);
      if (!data.length) { list.replaceChildren(emptyState('graph.none')); return; }
      list.replaceChildren(...data.map(entity => {
        const row = listRow(entity.name, `${entity.type} · ${entity.mentions} ${t('graph.mentions')}`);
        row.style.cursor = 'pointer';
        row.addEventListener('click', async () => {
          try {
            const full = await request(`/api/entities/${entity.id}`);
            detail.replaceChildren(card());
            const box = detail.firstChild;
            box.append(el('h3', {text: `${full.name} · ${full.type}`}));
            (full.mentions || []).forEach(m => box.append(listRow(m.text, m.source_name || '')));
          } catch (error) { showError(detail, error); }
        });
        return row;
      }));
    } catch (error) { showError(list, error); }
  };
  form.addEventListener('submit', event => { event.preventDefault(); load(input.value.trim()); });
  load();
};

// ---------------------------------------------------------------- impostazioni

const renderSettings = async container => {
  container.append(moduleHead('nav.settings', 'settings.intro'));

  // --- modello linguistico ---
  const llm = card('section.llm', 'section.llm.intro');
  container.append(llm);
  try {
    const fields = (await request('/api/config')).filter(item => item.section === 'llm');
    const form = el('form');
    fields.forEach(item => form.append(field({
      id: `config-${item.key}`,
      labelKey: `field.${item.key}.label`,
      helpKey: `field.${item.key}.help`,
      value: item.value,
      secret: item.secret,
    })));
    const result = el('p', {className: 'hint'});
    form.append(el('button', {className: 'primary', text: t('settings.save'), type: 'submit'}));
    llm.append(form, result);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = {};
      form.querySelectorAll('input').forEach(input => {
        if (input.value.trim()) values[input.dataset.key] = input.value.trim();
      });
      if (!Object.keys(values).length) { result.textContent = t('settings.noChange'); return; }
      try {
        const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
        result.textContent = saved.restart_required
          ? t('settings.savedRestart') : t('settings.savedLive');
        form.querySelectorAll('input').forEach(input => { input.value = ''; });
      } catch (error) { showError(result, error); }
    });
  } catch (error) { showError(llm, error); }

  // --- server ---
  const servers = card('section.workspaces', 'section.workspaces.intro');
  container.append(servers);
  const serverList = el('div');
  servers.append(serverList);

  const renderServers = () => {
    if (!AppState.workspaces.length) {
      serverList.replaceChildren(emptyState('workspace.none'));
      return;
    }
    serverList.replaceChildren(...AppState.workspaces.map(workspace => {
      const row = listRow(workspace.name, [
        workspace.platform || '—',
        `${workspace.active_sources} ${t('workspace.activeSources')}`,
        workspace.digest_webhook ? t('workspace.hasWebhook') : t('workspace.noWebhook'),
      ].join(' · '));
      const remove = el('button', {className: 'small danger', text: t('workspace.delete')});
      remove.addEventListener('click', async () => {
        if (!confirm(t('workspace.deleteConfirm'))) return;
        await request(`/api/workspaces/${workspace.id}`, {method: 'DELETE'});
        Shell.reloadWorkspaces();
      });
      row.append(remove);
      return row;
    }));
  };
  renderServers();

  const addForm = el('form');
  const nameField = field({id: 'new-ws-name', labelKey: 'workspace.name', helpKey: 'workspace.nameHelp'});
  const extField = field({id: 'new-ws-external', labelKey: 'workspace.externalId', helpKey: 'workspace.externalIdHelp'});
  const addResult = el('p', {className: 'hint'});
  addForm.append(nameField, extField,
    el('button', {className: 'primary', text: t('workspace.create'), type: 'submit'}));
  servers.append(el('h3', {text: t('workspace.create')}), addForm, addResult);
  addForm.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/workspaces', {
        method: 'POST',
        body: JSON.stringify({
          name: nameField.querySelector('input').value.trim(),
          platform: 'discord',
          external_id: extField.querySelector('input').value.trim() || null,
        }),
      });
      addForm.querySelectorAll('input').forEach(input => { input.value = ''; });
      addResult.textContent = '';
      Shell.reloadWorkspaces();
    } catch (error) { showError(addResult, error); }
  });

  // --- conservazione ---
  const retention = card('retention.title');
  container.append(retention);
  const retentionForm = el('form');
  const days = el('input');
  days.type = 'number';
  days.min = '1';
  days.placeholder = t('retention.placeholder');
  const daysLabel = el('label', {text: t('retention.label')});
  daysLabel.append(days);
  const retentionResult = el('p', {className: 'hint'});
  retentionForm.append(daysLabel,
    el('button', {className: 'primary', text: t('retention.save'), type: 'submit'}));
  retention.append(retentionForm, retentionResult);
  request('/api/settings/retention').then(data => { days.value = data.days ?? ''; }).catch(() => {});
  retentionForm.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/settings/retention', {
        method: 'POST',
        body: JSON.stringify({days: days.value.trim() ? Number(days.value) : null}),
      });
      retentionResult.textContent = t('retention.saved');
    } catch (error) { showError(retentionResult, error); }
  });

  // --- autori ignorati ---
  const ignored = card('ignored.title', 'ignored.intro');
  container.append(ignored);
  const ignoredList = el('div');
  ignored.append(ignoredList);
  const loadIgnored = async () => {
    try {
      const data = await request('/api/ignored-authors');
      if (!data.length) { ignoredList.replaceChildren(emptyState('ignored.none')); return; }
      ignoredList.replaceChildren(...data.map(entry => {
        const row = listRow(`${entry.platform} · ${entry.author_id}`);
        const remove = el('button', {className: 'small ghost', text: t('ignored.remove')});
        remove.addEventListener('click', async () => {
          await request(`/api/ignored-authors/${entry.platform}/${entry.author_id}`, {method: 'DELETE'});
          loadIgnored();
        });
        row.append(remove);
        return row;
      }));
    } catch (error) { showError(ignoredList, error); }
  };
  const ignoreForm = el('form');
  const ignorePlatform = el('select');
  PLATFORMS.forEach(name => {
    const option = el('option', {text: t(`section.${name}`)});
    option.value = name;
    ignorePlatform.append(option);
  });
  const platformLabel = el('label', {text: t('ignored.platform')});
  platformLabel.append(ignorePlatform);
  const authorField = field({id: 'ignore-author', labelKey: 'ignored.author'});
  ignoreForm.append(platformLabel, authorField,
    el('button', {text: t('ignored.add'), type: 'submit'}));
  ignored.append(ignoreForm);
  ignoreForm.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/ignored-authors', {
        method: 'POST',
        body: JSON.stringify({
          platform: ignorePlatform.value,
          author_id: authorField.querySelector('input').value.trim(),
        }),
      });
      authorField.querySelector('input').value = '';
      loadIgnored();
    } catch (error) { showError(ignoredList, error); }
  });
  loadIgnored();

  // --- cancellazione ---
  const wipe = card('wipe.title', 'wipe.note');
  const wipeButton = el('button', {className: 'danger', text: t('wipe.button')});
  const wipeResult = el('p', {className: 'hint'});
  wipe.append(wipeButton, wipeResult);
  container.append(wipe);
  wipeButton.addEventListener('click', async () => {
    if (!confirm(t('wipe.confirm'))) return;
    try {
      await request('/api/wipe', {method: 'POST', body: JSON.stringify({confirm: 'WIPE'})});
      wipeResult.textContent = t('wipe.done');
    } catch (error) { showError(wipeResult, error); }
  });
};

// ---------------------------------------------------------------- registro

const GNOSIS_MODULES = [
  {id: 'overview', group: 'bot', icon: '◎', labelKey: 'nav.overview', render: renderOverview},
  {id: 'chat', group: 'bot', icon: '💬', labelKey: 'nav.chat', render: renderChat},
  {id: 'digests', group: 'bot', icon: '📰', labelKey: 'nav.digests', render: renderDigests},
  {id: 'graph', group: 'bot', icon: '🕸', labelKey: 'nav.graph', render: renderGraph},
  {id: 'discord', group: 'platforms', icon: '🎮', labelKey: 'section.discord', platform: 'discord', render: renderPlatform('discord')},
  {id: 'telegram', group: 'platforms', icon: '✈', labelKey: 'section.telegram', platform: 'telegram', render: renderPlatform('telegram')},
  {id: 'reddit', group: 'platforms', icon: '👽', labelKey: 'section.reddit', platform: 'reddit', render: renderPlatform('reddit')},
  {id: 'status', group: 'system', icon: '📊', labelKey: 'nav.status', render: renderStatus},
  {id: 'settings', group: 'system', icon: '⚙', labelKey: 'nav.settings', render: renderSettings},
];
