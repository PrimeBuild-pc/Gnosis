// Guscio della dashboard: barra laterale, selettore del server, routing, cambio lingua.
// Non contiene nulla di specifico di Gnosis. I moduli arrivano da un registro esterno
// (GNOSIS_MODULES) e i bot affiancati da /api/bots, cosi' lo stesso guscio puo' essere
// servito anche da Doorman e D-View cambiando solo il registro.

const Shell = {
  bots: [],
  modules: typeof GNOSIS_MODULES !== 'undefined' ? GNOSIS_MODULES : [],
  readiness: {},

  current() {
    const id = location.hash.replace(/^#\/?/, '');
    return this.modules.find(module => module.id === id) || this.modules[0];
  },

  async reloadWorkspaces() {
    try {
      AppState.workspaces = await request('/api/workspaces');
    } catch {
      AppState.workspaces = [];
    }
    renderServerPicker();
    renderRail();
  },

  async reloadReadiness() {
    try {
      const steps = await request('/api/setup');
      this.readiness = Object.fromEntries(steps.map(step => [step.key, step]));
    } catch {
      this.readiness = {};
    }
  },

  async reloadBots() {
    try {
      this.bots = await request('/api/bots');
    } catch {
      // Endpoint assente (installazione vecchia): resta solo il bot corrente.
      this.bots = [{id: 'gnosis', name: 'Gnosis', icon: '🧠', installed: true, current: true}];
    }
  },
};

// ---------------------------------------------------------------- selettore server

const renderServerPicker = () => {
  const select = document.getElementById('workspace-select');
  const current = localStorage.getItem('gnosis-workspace') || 'all';
  const options = [{id: 'all', name: t('workspace.all')}, ...AppState.workspaces];
  select.replaceChildren(...options.map(item => {
    const option = el('option', {text: item.name});
    option.value = String(item.id);
    option.selected = String(item.id) === current;
    return option;
  }));
};

document.getElementById('workspace-select').addEventListener('change', event => {
  localStorage.setItem('gnosis-workspace', event.target.value);
  renderRail();
  renderModule();
});

// ---------------------------------------------------------------- lingua

const languageSelect = document.getElementById('language-select');
languageSelect.replaceChildren(...LANGUAGES.map(([code, label]) => {
  const option = el('option', {text: label});
  option.value = code;
  option.selected = code === currentLanguage;
  return option;
}));
languageSelect.addEventListener('change', event => setLanguage(event.target.value));

document.addEventListener('gnosis:language', () => {
  renderServerPicker();
  renderRail();
  renderModule();
});

// ---------------------------------------------------------------- barra laterale

const railItem = ({icon, label, active, current, onClick, dot, locked, badge}) => {
  const item = el('button', {className: 'rail-item', type: 'button'});
  // "active" e' il modulo aperto, "current" il bot su cui siamo: due cose diverse, due
  // stili diversi, altrimenti due righe risultano evidenziate insieme.
  if (active) item.classList.add('active');
  if (current) item.classList.add('current');
  if (locked) item.classList.add('locked');
  item.append(el('span', {className: 'rail-icon', text: icon}));
  item.append(el('span', {className: 'rail-label', text: label}));
  if (dot) item.append(el('span', {className: `dot ${dot}`}));
  if (badge) item.append(el('span', {className: 'rail-badge', text: badge}));
  if (onClick) item.addEventListener('click', onClick);
  return item;
};

const railGroup = titleKey => {
  const group = el('div', {className: 'rail-group'});
  group.append(el('div', {className: 'rail-title', text: t(titleKey)}));
  return group;
};

const renderRail = () => {
  const rail = document.getElementById('rail');
  const active = Shell.current();
  rail.replaceChildren();

  // --- bot affiancati ---
  const bots = railGroup('bots.title');
  Shell.bots.forEach(bot => {
    bots.append(railItem({
      icon: bot.icon || '●',
      label: bot.name,
      current: bot.current,
      active: location.hash === `#/install-${bot.id}`,
      locked: !bot.installed,
      badge: bot.installed ? null : t('bots.notInstalled'),
      dot: bot.installed && !bot.current ? 'on' : null,
      onClick: () => {
        if (bot.current) { location.hash = '#/overview'; return; }
        if (bot.installed && bot.url) { window.open(bot.url, '_blank', 'noopener'); return; }
        location.hash = `#/install-${bot.id}`;
      },
    }));
  });
  rail.append(bots);

  // --- moduli del bot corrente, raggruppati ---
  const groups = [
    ['bot', 'rail.group.bot'],
    ['platforms', 'rail.group.platforms'],
    ['system', 'rail.group.system'],
  ];
  groups.forEach(([name, titleKey]) => {
    const modules = Shell.modules.filter(module => module.group === name);
    if (!modules.length) return;
    const group = railGroup(titleKey);
    modules.forEach(module => {
      const step = module.platform ? Shell.readiness[module.platform] : null;
      let dot = null;
      if (step) dot = step.ready ? (step.sources ? 'on' : 'warn') : 'off';
      group.append(railItem({
        icon: module.icon,
        label: t(module.labelKey),
        active: module.id === active.id && !location.hash.startsWith('#/install-'),
        dot,
        onClick: () => { location.hash = `#/${module.id}`; },
      }));
    });
    rail.append(group);
  });
};

// ---------------------------------------------------------------- bot da installare

const renderInstall = (container, botId) => {
  const bot = Shell.bots.find(item => item.id === botId);
  if (!bot) { container.append(el('p', {className: 'empty', text: t('bots.unknown')})); return; }

  container.append(el('div', {className: 'module-head'}));
  const head = container.firstChild;
  head.append(el('h2', {text: `${bot.icon || ''} ${bot.name}`.trim()}));
  head.append(el('p', {text: bot.description || ''}));

  const box = el('div', {className: 'card install-card'});
  box.append(el('h3', {text: t('bots.installTitle')}));
  box.append(el('p', {className: 'hint', text: t('bots.installIntro')}));
  const command = el('code', {text: bot.install || `git clone ${bot.repo} && cd ${bot.name} && ./install.sh`});
  box.append(command);
  box.append(el('p', {className: 'hint faint', text: t('bots.installWhy')}));

  const actions = el('div', {className: 'row actions'});
  if (bot.repo) {
    const link = el('a', {text: t('bots.openRepo')});
    link.href = bot.repo;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    actions.append(link);
  }
  box.append(actions);
  container.append(box);

  const already = el('div', {className: 'card'});
  already.append(el('h3', {text: t('bots.alreadyTitle')}));
  already.append(el('p', {className: 'hint', text: t('bots.alreadyIntro')}));
  already.append(el('code', {text: 'GNOSIS_BOTS=doorman=http://127.0.0.1:3000,dview=http://127.0.0.1:3001'}));
  container.append(already);
};

// ---------------------------------------------------------------- modulo attivo

const renderModule = async () => {
  const container = document.getElementById('module');
  container.replaceChildren();

  const hash = location.hash.replace(/^#\/?/, '');
  if (hash.startsWith('install-')) {
    renderInstall(container, hash.slice('install-'.length));
    return;
  }

  const module = Shell.current();
  if (!module) return;
  document.getElementById('brand-name').textContent = 'Gnosis';
  try {
    await module.render(container);
  } catch (error) {
    showError(container, error);
  }
};

window.addEventListener('hashchange', () => { renderRail(); renderModule(); });

// ---------------------------------------------------------------- avvio

(async () => {
  document.documentElement.lang = currentLanguage;
  applyTranslations();
  await Promise.all([Shell.reloadBots(), Shell.reloadReadiness()]);
  await Shell.reloadWorkspaces();
  if (!location.hash) location.hash = '#/overview';
  renderRail();
  renderModule();
})();
