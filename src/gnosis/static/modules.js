// Each Gnosis module renders a page; the shell only knows its ID, group, icon and label.

const PLATFORMS = ['discord', 'telegram', 'reddit'];

/** Native disclosure: secondary or long content stays one click away. */
const collapsible = (summaryKey, open = false) => {
  const box = el('details', {className: 'disclosure'});
  box.open = open;
  box.append(el('summary', {text: () => t(summaryKey)}));
  return box;
};

// ---------------------------------------------------------------- overview

const renderOverview = async container => {
  container.append(moduleHead('nav.overview', 'settings.setupIntro'));
  const box = el('div');
  container.append(box);
  try {
    const [steps, stats] = await Promise.all([
      request('/api/setup'),
      request(`/api/stats${AppState.scopeQuery()}`),
    ]);

    const workspace = AppState.currentWorkspace();
    const tiles = el('div', {className: 'tiles'});
    [['sources', 'overview.tile.sources'], ['messages', 'overview.tile.messages'],
      ['digests', 'overview.tile.digests']].forEach(([key, labelKey]) => {
      const tile = el('div', {className: 'tile'});
      tile.append(el('strong', {text: Number(stats[key] || 0).toLocaleString(currentLanguage)}),
        el('span', {text: () => t(labelKey)}));
      tiles.append(tile);
    });
    box.append(tiles, el('p', {
      className: 'hint faint scope-note',
      text: () => workspace ? t('overview.scoped', {name: workspace.name}) : t('overview.global'),
    }));

    const checklist = card('settings.setupTitle');
    steps.forEach(step => {
      const row = el('div', {className: step.ready ? 'step ready' : 'step'});
      row.append(el('span', {className: 'step-mark', text: step.ready ? '✓' : '○'}));
      const body = el('div', {className: 'step-body'});
      body.append(el('strong', {
        text: () => step.required ? t('setup.requiredLabel', {name: t(`setup.${step.key}`)}) : t(`setup.${step.key}`),
      }));
      body.append(el('p', {className: 'hint', text: () => {
        if (!step.ready) return t('setup.missingFields', {
          fields: step.fields.map(key => t(`field.${key}.label`)).join(', '),
        });
        if (step.sources === 0) return t('settings.noSources');
        if (step.sources) return t('settings.sourcesActive', {n: step.sources});
        return t('settings.ready');
      }}));
      body.append(el('p', {className: 'hint faint', text: () => t(`setup.${step.key}.hint`)}));
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
  const label = el('label', {text: () => t('chat.question')});
  const textarea = el('textarea');
  textarea.maxLength = 4000;
  textarea.required = true;
  bindLocale(textarea, () => { textarea.placeholder = t('chat.placeholder'); });
  label.append(textarea);
  const submit = el('button', {className: 'primary', text: () => t('chat.submit'), type: 'submit'});
  form.append(label, submit);

  const answer = el('div', {className: 'card answer'});
  answer.setAttribute('role', 'status');
  answer.setAttribute('aria-live', 'polite');
  answer.hidden = true;
  container.append(form, answer);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    submit.disabled = true;
    answer.setAttribute('aria-busy', 'true');
    answer.hidden = false;
    answer.replaceChildren(el('p', {className: 'hint', text: () => t('chat.searching')}));
    try {
      const data = await request('/api/chat', {
        method: 'POST',
        body: JSON.stringify({question: textarea.value, workspace_id: AppState.workspaceId(), locale: currentLanguage}),
      });
      answer.replaceChildren(el('p', {text: data.answer}));
      if (data.sources.length) {
        const list = el('ul', {className: 'citation-list'});
        data.sources.forEach(source => {
          const item = el('li');
          const text = `[${source.id}] ${source.platform} · ${source.community} — ${source.author}`;
          const url = safeSourceURL(source.url);
          if (url) {
            const link = el('a', {text});
            link.href = url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            item.append(link);
          } else item.textContent = text;
          list.append(item);
        });
        answer.append(list);
      } else {
        answer.append(el('p', {className: 'hint faint', text: () => t('chat.noSources')}));
      }
    } catch (error) { showError(answer, error); }
    finally { submit.disabled = false; answer.setAttribute('aria-busy', 'false'); }
  });
};

// ---------------------------------------------------------------- digest

const renderDigests = async container => {
  container.append(moduleHead('nav.digests', 'digests.intro'));

  const actions = el('div', {className: 'row actions'});
  const run = el('button', {className: 'primary', text: () => t('digests.run')});
  const refresh = el('button', {className: 'ghost', text: () => t('digests.refresh')});
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
        article.append(el('strong', {
          text: () => {
            const period = formatDate(digest.period_date || digest.period_start, true);
            return digest.workspace_name ? `${period} · ${digest.workspace_name}` : period;
          },
        }));
        article.append(el('p', {text: digest.markdown}));
        return article;
      }));
    } catch (error) { showError(list, error); }
  };

  refresh.addEventListener('click', load);
  run.addEventListener('click', async () => {
    run.disabled = true;
    setText(status, () => t('digests.running'));
    try {
      const data = await request(`/api/digests/run${AppState.scopeQuery()}`, {method: 'POST'});
      setText(status, () => data.id ? '' : t('digests.noMessages'));
      load();
    } catch (error) { showError(status, error); }
    finally { run.disabled = false; }
  });
  load();
};

// ---------------------------------------------------------------- platform

/** One page per platform: credentials, selected server settings and collected channels. */
const renderPlatform = platform => async container => {
  container.append(moduleHead(`section.${platform}`, `section.${platform}.intro`));

  // Order: the selected server first (what admins change most), then what is read,
  // then bot credentials, which are set once.
  const serverCard = card('platform.serverSettings');
  const sourcesCard = card('platform.sources', `platform.sources.${platform}`);
  const credentials = card('platform.credentials');
  if (platform === 'discord') {
    container.append(serverCard);
    const invite = el('a', {className: 'button primary', text: () => t('platform.invite')});
    invite.target = '_blank';
    invite.rel = 'noopener noreferrer';
    invite.hidden = true;
    credentials.append(el('p', {className: 'hint', text: () => t('platform.inviteHint')}), invite);
    request('/api/discord/invite').then(({url}) => { invite.href = url; invite.hidden = false; })
      .catch(() => {});
  }
  container.append(sourcesCard, credentials);

  // --- platform credentials ---
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
    const save = el('button', {className: 'primary', text: () => t('settings.save'), type: 'submit'});
    const result = el('p', {className: 'hint'});
    form.append(save);
    const credentialDetails = collapsible('platform.credentialsEdit');
    credentialDetails.append(el('p', {className: 'hint faint', text: () => t('settings.maskNote')}), form, result);
    credentials.append(credentialDetails);

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = {};
      form.querySelectorAll('input').forEach(input => {
        if (input.value.trim()) values[input.dataset.key] = input.value.trim();
      });
      if (!Object.keys(values).length) { setText(result, () => t('settings.noChange')); return; }
      try {
        const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
        setText(result, () => t(saved.restart_required ? 'settings.savedRestart' : 'settings.savedLive'));
        form.querySelectorAll('input').forEach(input => { input.value = ''; });
      } catch (error) { showError(result, error); }
    });
  } catch (error) { showError(credentials, error); }

  // --- selected Discord server: roles and digest ---
  if (platform === 'discord') {
    const workspace = AppState.currentWorkspace();
    if (!workspace) {
      serverCard.append(el('p', {className: 'hint callout', text: () => t('platform.pickServer')}));
    } else {
      setText(serverCard.querySelector('h3'), () => t('platform.serverTitle', {name: workspace.name}));
      const form = el('form');
      const roles = field({
        id: 'ws-roles', labelKey: 'workspace.roles', helpKey: 'workspace.rolesHelp',
      });
      const webhook = field({
        id: 'ws-webhook', labelKey: 'workspace.webhook', helpKey: 'workspace.webhookHelp',
        value: workspace.digest_webhook || '', secret: true,
      });
      const external = field({
        id: 'ws-external', labelKey: 'workspace.externalId', helpKey: 'workspace.externalIdHelp',
      });
      roles.querySelector('input').value = (workspace.allowed_role_ids || []).join(',');
      external.querySelector('input').value = workspace.external_id || '';
      const save = el('button', {className: 'primary', text: () => t('workspace.save'), type: 'submit'});
      const result = el('p', {className: 'hint'});
      form.append(external, roles, webhook, save);
      serverCard.append(serverModeForm(workspace));
      const advanced = collapsible('workspace.advanced');
      advanced.append(form, result);
      serverCard.append(advanced);

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
              ...(webhook.querySelector('input').value.trim()
                ? {digest_webhook: webhook.querySelector('input').value.trim()} : {}),
            }),
          });
          setText(result, () => t('settings.savedLive'));
          Shell.reloadWorkspaces();
        } catch (error) { showError(result, error); }
      });
    }
  }

  // --- collected channels on this platform ---
  const list = el('div', {className: 'source-list'});
  const listBox = collapsible('sources.listTitle');
  const filter = el('input', {type: 'search'});
  bindLocale(filter, () => {
    filter.placeholder = t('sources.filter');
    filter.setAttribute('aria-label', t('sources.filter'));
  });
  filter.addEventListener('input', () => {
    const needle = filter.value.trim().toLowerCase();
    list.querySelectorAll('.list-row').forEach(row => {
      row.hidden = Boolean(needle) && !row.textContent.toLowerCase().includes(needle);
    });
  });
  listBox.append(filter, list);
  sourcesCard.append(el('p', {className: 'hint callout accent', text: () => t('sources.commandNote')}), listBox);

  const loadSources = async () => {
    try {
      const all = await request('/api/sources');
      const mine = all.filter(source => source.platform === platform)
        .filter(source => AppState.workspaceId() === null
          || source.workspace_id === AppState.workspaceId());
      const active = mine.filter(source => source.enabled).length;
      setText(listBox.querySelector('summary'), () => t('sources.listSummary', {n: mine.length, active}));
      if (!mine.length) { list.replaceChildren(emptyState('sources.none')); return; }
      list.replaceChildren(...mine.map(source => {
        const detail = () => [
          source.workspace_name || t('workspace.all'),
          (source.topics || []).join(', ') || t('sources.noTopics'),
        ].join(' · ');
        const row = listRow(source.name, detail);
        const toggle = el('button', {
          className: 'small ghost',
          text: () => t(source.enabled ? 'sources.disable' : 'sources.enable'),
        });
        toggle.addEventListener('click', async () => {
          try {
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
          } catch (error) { showError(result, error); }
        });
        row.append(el('span', {className: source.enabled ? 'dot on' : 'dot off'}), toggle);
        return row;
      }));
    } catch (error) { showError(list, error); }
  };

  // --- discovery dropdown: only channels actually visible to the bot ---
  const form = el('form');
  const pickLabel = el('label', {text: () => t('sources.pick')});
  const pick = el('select');
  pickLabel.append(pick);
  const pickHint = el('p', {className: 'hint'});

  const idField = field({id: 'src-id', labelKey: 'sources.id', helpKey: 'sources.idHelp'});
  const nameField = field({id: 'src-name', labelKey: 'sources.name'});
  const wsField = field({id: 'src-workspace', labelKey: 'sources.workspace', helpKey: 'sources.workspaceHelp'});
  const topicsField = field({id: 'src-topics', labelKey: 'sources.topics', helpKey: 'sources.topicsHelp'});
  bindLocale(topicsField.querySelector('input'), () => {
    topicsField.querySelector('input').placeholder = t('sources.topicsPlaceholder');
  });

  const save = el('button', {className: 'primary', text: () => t('sources.save'), type: 'submit'});
  const result = el('p', {className: 'hint'});
  form.append(pickLabel, pickHint, idField, nameField, wsField, topicsField, save);
  const addBox = collapsible('sources.addTitle');
  addBox.append(form, result);
  sourcesCard.append(addBox);

  if (platform !== 'reddit') {
    request(`/api/available-sources?platform=${platform}`).then(rows => {
      const manual = el('option', {text: () => t('sources.pickManual')});
      manual.value = '';
      if (!rows.length) {
        pick.replaceChildren(manual);
        setText(pickHint, () => t('sources.pickEmpty'));
        return;
      }
      const placeholder = el('option', {text: () => t('sources.pickPlaceholder')});
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
      setText(pickHint, () => t('sources.pickFound', {n: rows.length}));
    }).catch(error => showError(pickHint, error));
  } else {
    pickLabel.hidden = true;
    setText(pickHint, () => t('sources.redditManual'));
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
      setText(result, () => t('sources.saved'));
      form.querySelectorAll('input').forEach(input => { input.value = ''; });
      loadSources();
      Shell.reloadWorkspaces();
    } catch (error) { showError(result, error); }
  });

  loadSources();
};

// ---------------------------------------------------------------- status

const renderStatus = async container => {
  container.append(moduleHead('nav.status', 'status.intro'));
  const connectors = card('status.connectors');
  const sources = card('status.sources');
  const usage = card('status.usage', 'status.usageNote');
  container.append(connectors, sources, usage);
  try {
    const data = await request('/api/status');
    data.workers.forEach(worker => {
      const title = () => {
        if (PLATFORMS.includes(worker.component)) return t(`section.${worker.component}`);
        if (['pipeline', 'digest', 'retention', 'telegram_bot'].includes(worker.component)) {
          return t(`status.component.${worker.component}`);
        }
        return worker.component;
      };
      const row = listRow(title, () => {
        const state = t(['ok', 'error'].includes(worker.status) ? `status.${worker.status}` : 'status.unknown');
        return worker.detail ? `${state} · ${worker.detail}` : state;
      });
      row.prepend(el('span', {className: worker.status === 'ok' ? 'dot on' : 'dot warn'}));
      row.classList.add('compact');
      connectors.append(row);
    });
    if (!data.workers.length) connectors.append(emptyState('status.noWorkers'));

    const visible = data.sources.filter(source => {
      const workspace = AppState.currentWorkspace();
      return !workspace || source.workspace_name === workspace.name;
    });
    const pending = visible.reduce((sum, source) => sum + (source.pending || 0), 0);
    const sourceBox = collapsible('status.sources');
    setText(sourceBox.querySelector('summary'),
      () => t('status.sourcesSummary', {n: visible.length, pending}));
    sources.append(sourceBox);
    if (!visible.length) sourceBox.append(emptyState('sources.none'));
    visible.forEach(source => {
      sourceBox.append(listRow(
        `${source.platform} · ${source.name}`,
        () => t('status.activity', {
          date: source.last_processed_at ? formatDate(source.last_processed_at) : t('status.never'),
          n: source.pending,
        }),
      ));
    });

    const entries = await request('/api/usage');
    if (!entries.length) usage.append(emptyState('status.noUsage'));
    entries.forEach(entry => usage.append(listRow(
      entry.model, () => t('status.tokens', {input: entry.prompt_tokens, output: entry.completion_tokens}),
    )));
  } catch (error) { showError(connectors, error); }
};

// ---------------------------------------------------------------- graph

const renderGraph = async container => {
  container.append(moduleHead('nav.graph', 'graph.intro'));
  container.append(el('p', {className: 'hint callout', text: () => t('graph.globalNote')}));

  const form = el('form');
  const input = el('input');
  bindLocale(input, () => {
    input.placeholder = t('graph.search');
    input.setAttribute('aria-label', t('graph.search'));
  });
  form.append(input, el('button', {className: 'primary', text: () => t('graph.submit'), type: 'submit'}));
  const list = el('div');
  const detail = el('div');
  container.append(form, list, detail);

  const load = async (search = '') => {
    try {
      const data = await request(`/api/entities?search=${encodeURIComponent(search)}`);
      if (!data.length) { list.replaceChildren(emptyState('graph.none')); return; }
      list.replaceChildren(...data.map(entity => {
        const row = listRow(entity.name, () => t('graph.entitySummary', {type: entity.type, n: entity.mentions}));
        const open = el('button', {className: 'ghost', text: entity.name, type: 'button'});
        row.append(open);
        open.addEventListener('click', async () => {
          try {
            const full = await request(`/api/entities/${entity.id}`);
            detail.replaceChildren(card());
            const box = detail.firstChild;
            box.append(el('h3', {text: `${full.entity.name} · ${full.entity.type}`}));
            (full.mentions || []).forEach(m => {
              const mention = listRow(m.source_name, () => `${m.author} · ${formatDate(m.sent_at)}`);
              const url = safeSourceURL(m.url);
              if (url) {
                const link = el('a', {text: `M${m.id}`});
                link.href = url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                mention.append(link);
              }
              box.append(mention);
            });
          } catch (error) { showError(detail, error); }
        });
        return row;
      }));
    } catch (error) { showError(list, error); }
  };
  form.addEventListener('submit', event => { event.preventDefault(); load(input.value.trim()); });
  load();
};

// ---------------------------------------------------------------- settings

const renderSettings = async container => {
  container.append(moduleHead('nav.settings', 'settings.intro'));

  // --- language model ---
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
    form.append(el('button', {className: 'primary', text: () => t('settings.save'), type: 'submit'}));
    llm.append(el('p', {className: 'hint faint', text: () => t('settings.maskNote')}), form, result);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = {};
      form.querySelectorAll('input').forEach(input => {
        if (input.value.trim()) values[input.dataset.key] = input.value.trim();
      });
      if (!Object.keys(values).length) { setText(result, () => t('settings.noChange')); return; }
      try {
        const saved = await request('/api/config', {method: 'POST', body: JSON.stringify({values})});
        setText(result, () => t(saved.restart_required ? 'settings.savedRestart' : 'settings.savedLive'));
        form.querySelectorAll('input').forEach(input => { input.value = ''; });
      } catch (error) { showError(result, error); }
    });
  } catch (error) { showError(llm, error); }

  // --- automatic AI usage ---
  const aiCard = card('ai.title', 'ai.intro');
  container.append(aiCard);
  const aiToggle = el('input', {type: 'checkbox', id: 'ai-processing'});
  const aiRow = el('label', {className: 'checkbox-row'});
  aiRow.append(aiToggle, el('span', {text: () => t('ai.toggle')}));
  const aiResult = el('p', {className: 'hint'});
  aiCard.append(aiRow, el('p', {className: 'hint', text: () => t('ai.digestNote')}), aiResult);
  request('/api/settings/ai-processing').then(data => { aiToggle.checked = data.enabled; })
    .catch(error => showError(aiResult, error));
  aiToggle.addEventListener('change', async () => {
    try {
      await request('/api/settings/ai-processing', {
        method: 'POST', body: JSON.stringify({enabled: aiToggle.checked}),
      });
      setText(aiResult, () => t('settings.savedLive'));
    } catch (error) { showError(aiResult, error); }
  });

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
      const row = listRow(workspace.name, () => `${workspace.platform || '—'} · ${t('workspace.summary', {
        n: workspace.active_sources,
        destination: t(workspace.digest_webhook ? 'workspace.hasWebhook' : 'workspace.noWebhook'),
      })}`);
      const remove = el('button', {className: 'small danger', text: () => t('workspace.delete')});
      remove.addEventListener('click', async () => {
        if (!confirm(t('workspace.deleteConfirm'))) return;
        try {
          await request(`/api/workspaces/${workspace.id}`, {method: 'DELETE'});
          await Shell.reloadWorkspaces();
          renderServers();
        } catch (error) { showError(addResult, error); }
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
    el('button', {className: 'primary', text: () => t('workspace.create'), type: 'submit'}));
  const addServer = collapsible('workspace.addManual');
  addServer.append(addForm, addResult);
  servers.append(addServer);
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
      setText(addResult, () => t('settings.savedLive'));
      await Shell.reloadWorkspaces();
      renderServers();
    } catch (error) { showError(addResult, error); }
  });

  // --- retention ---
  const retention = card('retention.title');
  container.append(retention);
  const retentionForm = el('form');
  const days = el('input');
  days.type = 'number';
  days.min = '1';
  bindLocale(days, () => { days.placeholder = t('retention.placeholder'); });
  const daysLabel = el('label', {text: () => t('retention.label')});
  daysLabel.append(days);
  const retentionResult = el('p', {className: 'hint'});
  retentionForm.append(daysLabel,
    el('button', {className: 'primary', text: () => t('retention.save'), type: 'submit'}));
  retention.append(retentionForm, retentionResult);
  request('/api/settings/retention').then(data => { days.value = data.days ?? ''; })
    .catch(error => showError(retentionResult, error));
  retentionForm.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/settings/retention', {
        method: 'POST',
        body: JSON.stringify({days: days.value.trim() ? Number(days.value) : null}),
      });
      setText(retentionResult, () => t('retention.saved'));
    } catch (error) { showError(retentionResult, error); }
  });

  // --- ignored authors ---
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
        const remove = el('button', {className: 'small ghost', text: () => t('ignored.remove')});
        remove.addEventListener('click', async () => {
          try {
            await request(`/api/ignored-authors/${entry.platform}/${entry.author_id}`, {method: 'DELETE'});
            loadIgnored();
          } catch (error) { showError(ignoredList, error); }
        });
        row.append(remove);
        return row;
      }));
    } catch (error) { showError(ignoredList, error); }
  };
  const ignoreForm = el('form');
  const ignorePlatform = el('select');
  PLATFORMS.forEach(name => {
    const option = el('option', {text: () => t(`section.${name}`)});
    option.value = name;
    ignorePlatform.append(option);
  });
  const platformLabel = el('label', {text: () => t('ignored.platform')});
  platformLabel.append(ignorePlatform);
  const authorField = field({id: 'ignore-author', labelKey: 'ignored.author'});
  ignoreForm.append(platformLabel, authorField,
    el('button', {text: () => t('ignored.add'), type: 'submit'}));
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

  // --- erasure ---
  const wipe = card('wipe.title', 'wipe.note');
  wipe.classList.add('danger-zone');
  const wipeButton = el('button', {className: 'danger', text: () => t('wipe.button')});
  const wipeResult = el('p', {className: 'hint'});
  wipe.append(wipeButton, wipeResult);
  container.append(wipe);
  wipeButton.addEventListener('click', async () => {
    if (!confirm(t('wipe.confirm'))) return;
    try {
      await request('/api/wipe', {method: 'POST', body: JSON.stringify({confirm: 'WIPE'})});
      setText(wipeResult, () => t('wipe.done'));
    } catch (error) { showError(wipeResult, error); }
  });
};

// ---------------------------------------------------------------- registry

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

// Read-all channels, exclusions and digest channel/frequency for one Discord server.
const serverModeForm = workspace => {
  const wrap = el('div', {className: 'server-mode'});
  wrap.dataset.layout = 'plain';
  const form = el('form');
  const label = (key, control) => {
    const node = el('label', {className: 'checkbox-row'});
    node.append(control, el('span', {text: () => t(key)}));
    return node;
  };
  const memberCommands = el('input', {type: 'checkbox', id: 'ws-member-commands'});
  memberCommands.checked = workspace.member_commands_enabled !== false;
  const readAll = el('input', {type: 'checkbox', id: 'ws-read-all'});
  readAll.checked = workspace.read_all_channels !== false;
  const excludedBox = el('fieldset', {className: 'channel-list'});
  const excludedLegend = el('legend', {text: () => t('workspace.excluded')});
  const digestChannel = el('select', {id: 'ws-digest-channel'});
  const createChannel = el('button', {className: 'small', text: () => t('workspace.createDigestChannel'), type: 'button'});
  const frequency = el('select', {id: 'ws-frequency'});
  ['weekly', 'daily', 'off'].forEach(value => {
    const option = el('option', {text: () => t(`workspace.frequency.${value}`)});
    option.value = value;
    frequency.append(option);
  });
  frequency.value = workspace.digest_frequency || 'weekly';
  const language = el('select', {id: 'ws-digest-locale'});
  LANGUAGES.forEach(([code, name]) => {
    const option = el('option', {text: name});
    option.value = code;
    language.append(option);
  });
  language.value = workspace.digest_locale || 'en';

  const labelled = (key, control, id) => {
    const node = el('div', {className: 'field'});
    const caption = el('label', {text: () => t(key)});
    caption.htmlFor = id;
    node.append(caption, control);
    return node;
  };
  const channelRow = el('div', {className: 'inline'});
  channelRow.append(digestChannel, createChannel);
  const save = el('button', {className: 'primary', text: () => t('workspace.save'), type: 'submit'});
  const result = el('p', {className: 'hint'});
  excludedBox.append(excludedLegend);
  form.append(
    el('h4', {text: () => t('workspace.serverMode')}),
    label('workspace.readAll', readAll),
    excludedBox,
    labelled('workspace.digestChannel', channelRow, 'ws-digest-channel'),
    labelled('workspace.frequency', frequency, 'ws-frequency'),
    labelled('workspace.digestLanguage', language, 'ws-digest-locale'),
    label('workspace.memberCommands', memberCommands),
    el('p', {className: 'hint', text: () => t('workspace.memberCommandsHint')}),
    save,
  );
  wrap.append(form, result);

  const fillChannels = rows => {
    const channels = rows.filter(row => row.workspace_external_id === workspace.external_id);
    const excluded = new Set(workspace.excluded_channel_ids || []);
    excludedBox.replaceChildren(excludedLegend, ...channels.map(row => {
      const box = el('input', {type: 'checkbox'});
      box.value = row.external_id;
      box.checked = excluded.has(row.external_id);
      const node = el('label', {className: 'checkbox-row'});
      node.append(box, el('span', {text: row.name}));
      return node;
    }));
    if (!channels.length) excludedBox.append(el('p', {className: 'empty', text: () => t('workspace.noChannelsYet')}));
    const none = el('option', {text: () => t('workspace.noDigestChannel')});
    none.value = '';
    digestChannel.replaceChildren(none, ...channels.map(row => {
      const option = el('option', {text: row.name});
      option.value = row.external_id;
      return option;
    }));
    digestChannel.value = workspace.digest_channel_id || '';
  };
  const syncDisabled = () => { excludedBox.disabled = !readAll.checked; };
  readAll.addEventListener('change', syncDisabled);
  syncDisabled();
  request('/api/available-sources?platform=discord').then(fillChannels)
    .catch(error => showError(result, error));

  createChannel.addEventListener('click', async () => {
    try {
      const created = await request(`/api/workspaces/${workspace.id}/digest-channel`, {method: 'POST'});
      workspace.digest_channel_id = created.channel_id;
      const option = el('option', {text: '#gnosis-digest'});
      option.value = created.channel_id;
      digestChannel.append(option);
      digestChannel.value = created.channel_id;
      setText(result, () => t('workspace.digestChannelCreated'));
    } catch (error) { showError(result, error); }
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await request('/api/workspaces', {
        method: 'POST',
        body: JSON.stringify({
          name: workspace.name,
          read_all_channels: readAll.checked,
          excluded_channel_ids: [...excludedBox.querySelectorAll('input:checked')].map(box => box.value),
          digest_channel_id: digestChannel.value,
          digest_frequency: frequency.value,
          digest_locale: language.value,
          member_commands_enabled: memberCommands.checked,
        }),
      });
      setText(result, () => t('settings.savedLive'));
      Shell.reloadWorkspaces();
    } catch (error) { showError(result, error); }
  });
  return wrap;
};
