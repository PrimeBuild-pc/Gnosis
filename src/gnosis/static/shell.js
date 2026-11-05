// Shared dashboard shell: navigation, context, routing and language selection.
// Modules come from GNOSIS_MODULES. Each Prime Build bot has its own dashboard.

const Shell = {
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

};

// ---------------------------------------------------------------- server picker

const renderServerPicker = () => {
  const select = document.getElementById('workspace-select');
  const current = AppState.activeWorkspace;
  const options = [{id: 'all', name: t('workspace.all')}, ...AppState.workspaces];
  select.replaceChildren(...options.map(item => {
    const option = el('option', {text: item.name});
    option.value = String(item.id);
    option.selected = String(item.id) === current;
    return option;
  }));
};

document.getElementById('workspace-select').addEventListener('change', event => {
  AppState.activeWorkspace = event.target.value;
  writePreference('gnosis-workspace', AppState.activeWorkspace);
  renderRail();
  renderModule();
});

// ---------------------------------------------------------------- language

const languageSelect = document.getElementById('language-select');
languageSelect.replaceChildren(...LANGUAGES.map(([code, label]) => {
  const option = el('option', {text: label});
  option.value = code;
  option.selected = code === currentLanguage;
  return option;
}));
languageSelect.addEventListener('change', event => setLanguage(event.target.value));

document.addEventListener('gnosis:language', () => {
  languageSelect.value = currentLanguage;
  renderServerPicker();
  renderRail();
});

// ---------------------------------------------------------------- navigation rail

const railItem = ({icon, label, active, onClick, dot}) => {
  const item = el('button', {className: 'rail-item', type: 'button'});
  if (active) { item.classList.add('active'); item.setAttribute('aria-current', 'page'); }
  item.append(el('span', {className: 'rail-icon', text: icon}));
  item.append(el('span', {className: 'rail-label', text: label}));
  if (dot) item.append(el('span', {className: `dot ${dot}`}));
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

  // --- modules, grouped ---
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
        active: module.id === active.id,
        dot,
        onClick: () => { location.hash = `#/${module.id}`; },
      }));
    });
    rail.append(group);
  });
};

// ---------------------------------------------------------------- active module

const renderModule = async () => {
  if (location.hash === '#main') return;
  const host = document.getElementById('module');
  const container = el('div');
  host.replaceChildren(container); // Late responses from the previous context stay detached.

  const module = Shell.current();
  if (!module) return;
  document.getElementById('brand-name').textContent = 'Gnosis';
  try {
    await module.render(container);
  } catch (error) {
    showError(container, error);
  }
};

document.querySelector('.skip-link').addEventListener('click', event => {
  event.preventDefault();
  document.getElementById('main').focus();
});

window.addEventListener('hashchange', () => { renderRail(); renderModule(); });

// ---------------------------------------------------------------- startup

(async () => {
  document.documentElement.lang = currentLanguage;
  applyTranslations();
  await Shell.reloadReadiness();
  await Shell.reloadWorkspaces();
  if (!location.hash) location.hash = '#/overview';
  renderRail();
  renderModule();
})();
