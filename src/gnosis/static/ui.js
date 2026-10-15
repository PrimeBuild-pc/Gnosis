// Shared DOM helpers. Third-party content and model output are always text, never HTML.

const request = async (url, options = {}) => {
  let response;
  try {
    response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  } catch (error) {
    error.localeKey = 'error.network';
    throw error;
  }
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    const error = new Error(typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : response.statusText);
    const keys = {400: 'validation', 401: 'auth', 403: 'forbidden', 404: 'notFound',
      409: 'conflict', 422: 'validation', 429: 'rateLimit'};
    error.localeKey = `error.${keys[response.status] || (response.status >= 500 ? 'server' : 'unexpected')}`;
    throw error;
  }
  try { return await response.json(); }
  catch (error) { error.localeKey = 'error.response'; throw error; }
};

const bindLocale = (node, update) => {
  node.setAttribute('data-i18n-live', '');
  node.localize = update;
  update();
};

const setText = (node, text) => {
  const content = document.createTextNode('');
  node.replaceChildren(content);
  node.removeAttribute('data-i18n-live');
  if (typeof text === 'function') bindLocale(node, () => { content.textContent = text(); });
  else content.textContent = text;
};

const el = (tag, options = {}) => {
  const node = document.createElement(tag);
  if (options.text !== undefined) setText(node, options.text);
  if (options.className) node.className = options.className;
  if (options.id) node.id = options.id;
  if (options.type) node.type = options.type;
  if (tag === 'p' && options.className === 'hint') node.setAttribute('role', 'status');
  if (options.html === true) throw new Error('HTML strings are not allowed');
  return node;
};

const showError = (element, error) => {
  const message = el('p', {className: 'error', text: () => `${t('error')}: ${t(error.localeKey || 'error.unexpected')}`});
  message.setAttribute('role', 'alert');
  element.removeAttribute('data-i18n-live');
  element.replaceChildren(message);
  if (error.message) {
    const details = el('details');
    details.append(el('summary', {text: () => t('error.details')}), el('pre', {text: error.message}));
    element.append(details);
  }
};

/** Module heading and a short explanation. */
const moduleHead = (titleKey, introKey) => {
  const head = el('div', {className: 'module-head'});
  head.append(el('h2', {text: () => t(titleKey)}));
  if (introKey) head.append(el('p', {text: () => t(introKey)}));
  return head;
};

const card = (titleKey, introKey) => {
  const node = el('div', {className: 'card'});
  if (titleKey) node.append(el('h3', {text: () => t(titleKey)}));
  if (introKey) node.append(el('p', {className: 'hint', text: () => t(introKey)}));
  return node;
};

/** Field with contextual help: purpose, setup and consequences of missing values. */
const field = ({id, labelKey, helpKey, value = '', secret = false, placeholder = ''}) => {
  const wrapper = el('div', {className: 'field'});
  const header = el('div', {className: 'field-header'});

  const label = el('label', {text: () => t(labelKey)});
  label.htmlFor = id;
  header.append(label);

  const help = el('p', {className: 'hint help', text: () => helpKey ? t(helpKey) : ''});
  help.hidden = true;

  if (helpKey) {
    const info = el('button', {className: 'info', text: 'i', type: 'button'});
    bindLocale(info, () => {
      info.title = t('settings.info');
      info.setAttribute('aria-label', t('settings.info'));
    });
    help.id = `${id}-help`;
    info.setAttribute('aria-controls', help.id);
    info.setAttribute('aria-expanded', 'false');
    info.addEventListener('click', () => {
      help.hidden = !help.hidden;
      info.setAttribute('aria-expanded', String(!help.hidden));
    });
    header.append(info);
  }

  const input = el('input', {id});
  input.dataset.key = id.replace(/^config-/, '');
  input.placeholder = placeholder || value || '—';
  if (secret) { input.type = 'password'; input.autocomplete = 'new-password'; }
  if (helpKey) input.setAttribute('aria-describedby', help.id);

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

const safeSourceURL = value => {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
};

const emptyState = key => el('p', {className: 'empty', text: () => t(key)});

// Native validation follows the app language rather than the browser UI language.
const localizeValidation = input => {
  input.setCustomValidity('');
  const validity = input.validity;
  if (validity.valid) return;
  const key = validity.valueMissing ? 'required' : validity.badInput ? 'number'
    : validity.rangeUnderflow ? 'minimum' : validity.rangeOverflow ? 'maximum' : 'invalid';
  input.setCustomValidity(t(`validation.${key}`, {min: input.min, max: input.max}));
};
document.addEventListener('invalid', event => {
  event.target.dataset.validationShown = 'true';
  localizeValidation(event.target);
}, true);
for (const eventName of ['input', 'change']) {
  document.addEventListener(eventName, event => {
    if (event.target.setCustomValidity) {
      event.target.setCustomValidity('');
      delete event.target.dataset.validationShown;
    }
  });
}
document.addEventListener('gnosis:language', () => {
  document.querySelectorAll('[data-validation-shown]').forEach(localizeValidation);
});

/** The shell owns the selected context; modules use it to scope API requests. */
const AppState = {
  workspaces: [],
  activeWorkspace: readPreference('gnosis-workspace') || 'all',
  workspaceId() {
    const raw = this.activeWorkspace;
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
