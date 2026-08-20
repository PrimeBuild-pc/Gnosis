// Helper condivisi fra guscio e moduli. Nessun nodo viene costruito da stringhe HTML:
// Gnosis ingerisce contenuti di terze parti (autori, nomi di canale, entita' estratte da un
// LLM) e nulla di tutto cio' deve poter essere interpretato come markup.

const request = async (url, options = {}) => {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    throw new Error(detail || response.statusText);
  }
  return response.json();
};

const el = (tag, options = {}) => {
  const node = document.createElement(tag);
  if (options.text !== undefined) node.textContent = options.text;
  if (options.className) node.className = options.className;
  if (options.id) node.id = options.id;
  if (options.type) node.type = options.type;
  if (options.html === true) throw new Error('mai HTML da stringa');
  return node;
};

const showError = (element, error) => {
  element.replaceChildren(el('p', {className: 'error', text: `${t('error')}: ${error.message}`}));
};

/** Intestazione del modulo: titolo e una riga che dice a cosa serve la pagina. */
const moduleHead = (titleKey, introKey) => {
  const head = el('div', {className: 'module-head'});
  head.append(el('h2', {text: t(titleKey)}));
  if (introKey) head.append(el('p', {text: t(introKey)}));
  return head;
};

const card = (titleKey, introKey) => {
  const node = el('div', {className: 'card'});
  if (titleKey) node.append(el('h3', {text: t(titleKey)}));
  if (introKey) node.append(el('p', {className: 'hint', text: t(introKey)}));
  return node;
};

/** Campo con pulsante informativo: cosa fa, dove si prende, cosa succede se manca. */
const field = ({id, labelKey, helpKey, value = '', secret = false, placeholder = ''}) => {
  const wrapper = el('div', {className: 'field'});
  const header = el('div', {className: 'field-header'});

  const label = el('label', {text: t(labelKey)});
  label.htmlFor = id;
  header.append(label);

  const help = el('p', {className: 'hint help', text: t(helpKey)});
  help.hidden = true;

  if (helpKey) {
    const info = el('button', {className: 'info', text: 'i', type: 'button'});
    info.title = t('settings.info');
    info.setAttribute('aria-label', t('settings.info'));
    info.addEventListener('click', () => { help.hidden = !help.hidden; });
    header.append(info);
  }

  const input = el('input', {id});
  input.dataset.key = id.replace(/^config-/, '');
  input.placeholder = placeholder || value || '—';
  if (secret) input.type = 'password';

  wrapper.append(header);
  if (helpKey) wrapper.append(help);
  wrapper.append(input);
  return wrapper;
};

const listRow = (title, detail) => {
  const row = el('div', {className: 'list-row'});
  const grow = el('div', {className: 'grow'});
  grow.append(el('strong', {text: title}));
  if (detail) grow.append(el('p', {className: 'hint', text: detail}));
  row.append(grow);
  return row;
};

const emptyState = key => el('p', {className: 'empty', text: t(key)});

/** Contesto selezionato: lo legge il guscio, lo usano i moduli per interrogare l'API. */
const AppState = {
  workspaces: [],
  workspaceId() {
    const raw = localStorage.getItem('gnosis-workspace');
    return raw && raw !== 'all' ? Number(raw) : null;
  },
  scopeQuery(prefix = '?') {
    const id = this.workspaceId();
    return id === null ? '' : `${prefix}workspace_id=${id}`;
  },
  currentWorkspace() {
    return this.workspaces.find(w => w.id === this.workspaceId()) || null;
  },
};
