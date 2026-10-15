// Dependency-free DOM and locale contracts; no server, browser or model downloads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const staticDir = path.join(__dirname, '../src/gnosis/static');
const source = file => fs.readFileSync(path.join(staticDir, file), 'utf8');
const dataKey = key => key.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
// Exercise calendar dates in a browser timezone behind UTC.
process.env.TZ = 'America/Los_Angeles';

class Node {
  constructor(tag) {
    this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.dataset = {};
    this.className = ''; this.hidden = false; this._value = ''; this.customMessage = '';
    this.classList = {add: name => { this.className += ` ${name}`; }};
  }
  append(...nodes) {
    for (const node of nodes) { node.parentNode = this; this.children.push(node); }
  }
  prepend(node) { node.parentNode = this; this.children.unshift(node); }
  replaceChildren(...nodes) {
    this.children.forEach(node => { node.parentNode = null; });
    this.children = []; this.append(...nodes);
  }
  setAttribute(key, value) {
    this.attrs[key] = String(value);
    if (key.startsWith('data-')) this.dataset[dataKey(key)] = String(value);
  }
  getAttribute(key) { return this.attrs[key] ?? null; }
  removeAttribute(key) {
    delete this.attrs[key];
    if (key.startsWith('data-')) delete this.dataset[dataKey(key)];
  }
  addEventListener(key, callback) { this.events[key] = callback; }
  get firstChild() { return this.children[0]; }
  get textContent() { return this.tag === '#text' ? this.text || '' : this.children.map(n => n.textContent).join(''); }
  set textContent(value) {
    if (this.tag === '#text') this.text = String(value);
    else {
      const node = new Node('#text'); node.text = String(value);
      this.replaceChildren(node);
    }
  }
  get value() {
    if (this.tag === 'select') return this.selectedOptions[0]?.value || '';
    return this._value;
  }
  set value(value) {
    this._value = String(value);
    if (this.tag === 'select') this.children.forEach(option => { option.selected = option.value === this._value; });
  }
  get selectedOptions() {
    const selected = this.children.filter(node => node.selected);
    return selected.length ? selected : this.children.slice(0, 1);
  }
  querySelectorAll(selector) {
    const matches = node => selector.split(',').some(part => {
      part = part.trim();
      if (part.startsWith('[')) {
        const attr = part.slice(1, -1);
        return attr.startsWith('data-') ? Object.hasOwn(node.dataset, dataKey(attr)) : Object.hasOwn(node.attrs, attr);
      }
      if (part.startsWith('.')) return node.className.split(/\s+/).includes(part.slice(1));
      if (part.startsWith('#')) return node.id === part.slice(1);
      return node.tag === part;
    });
    const result = [];
    const visit = node => node.children.forEach(child => {
      if (matches(child)) result.push(child);
      visit(child);
    });
    visit(this);
    return result;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  setCustomValidity(message) { this.customMessage = message; }
  get validity() {
    const valueMissing = Boolean(this.required && !this.value);
    const badInput = this.type === 'number' && this.value !== '' && Number.isNaN(Number(this.value));
    const rangeUnderflow = this.type === 'number' && this.value !== '' && this.min !== undefined && Number(this.value) < Number(this.min);
    const rangeOverflow = this.type === 'number' && this.value !== '' && this.max !== undefined && Number(this.value) > Number(this.max);
    return {valueMissing, badInput, rangeUnderflow, rangeOverflow,
      valid: !valueMissing && !badInput && !rangeUnderflow && !rangeOverflow && !this.customMessage};
  }
  focus() { this.focused = true; }
}

function harness({saved, languages = [], language = 'en', blocked = false, fetcher} = {}) {
  const root = new Node('body');
  const events = {};
  const document = {
    documentElement: {}, root,
    createElement: tag => new Node(tag),
    createTextNode: value => { const node = new Node('#text'); node.textContent = value; return node; },
    querySelectorAll: selector => root.querySelectorAll(selector),
    querySelector: selector => root.querySelector(selector),
    getElementById: id => root.querySelector(`#${id}`),
    addEventListener: (name, callback) => { (events[name] ||= []).push(callback); },
    dispatchEvent: event => { (events[event.type] || []).forEach(callback => callback(event)); },
  };
  const storage = new Map(saved === undefined ? [] : [['gnosis-lang', saved]]);
  const calls = [];
  const context = vm.createContext({
    document, URL, navigator: {languages, language},
    CustomEvent: class { constructor(type) { this.type = type; } },
    localStorage: {
      getItem: key => { if (blocked) throw new Error('blocked'); return storage.get(key) ?? null; },
      setItem: (key, value) => { if (blocked) throw new Error('blocked'); storage.set(key, value); },
    },
    fetch: async (url, options) => {
      calls.push({url, options});
      return fetcher ? fetcher(url, options) : {ok: true, json: async () => []};
    },
    location: {hash: '#/chat'}, window: {addEventListener() {}, open() {}},
    confirm: () => true,
  });
  const evaluate = code => vm.runInContext(code, context);
  const load = file => vm.runInContext(source(file), context, {filename: file});
  load('i18n.js');
  return {context, evaluate, load, document, storage, calls};
}
const settle = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
const submitEvent = {preventDefault() {}};

(async () => {
  // Saved preferences win, region tags normalize, and browser preferences are tried in order.
  for (const [options, expected] of [
    [{}, 'en'], [{language: 'fr'}, 'en'], [{language: 'it-IT'}, 'it'],
    [{languages: ['fr-FR', 'es-MX', 'it']}, 'es'],
    [{languages: ['zh-Hant-TW', 'en']}, 'zh'],
    [{saved: 'ru', languages: ['it']}, 'ru'],
    [{saved: 'IT_it', languages: ['es']}, 'it'],
    [{saved: 'unsupported', languages: ['ru-RU']}, 'ru'],
    [{saved: 'constructor', languages: ['__proto__']}, 'en'],
    [{saved: 'it', blocked: true, languages: ['es']}, 'es'],
  ]) {
    const h = harness(options);
    assert.equal(h.evaluate('currentLanguage'), expected);
    assert.equal(h.document.documentElement.lang, expected);
  }
  const h = harness();
  h.load('ui.js'); h.load('modules.js');
  const dictionaries = h.evaluate('I18N');
  assert.deepEqual(Object.keys(dictionaries).sort(), ['en', 'es', 'it', 'ru', 'zh']);
  assert.equal(h.evaluate('LANGUAGES.length'), 5);
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
  for (const [locale, dictionary] of Object.entries(dictionaries)) {
    assert.deepEqual(Object.keys(dictionary).sort(), Object.keys(dictionaries.en).sort(), `${locale}: key parity`);
    for (const [key, text] of Object.entries(dictionary)) {
      assert.equal(typeof text, 'string', `${locale}.${key}`);
      assert.ok(text.trim(), `${locale}.${key}: empty translation`);
      assert.deepEqual(placeholders(text), placeholders(dictionaries.en[key]), `${locale}.${key}: placeholders`);
    }
  }
  // Catch newly added literal UI keys without a dictionary entry.
  for (const file of ['ui.js', 'modules.js', 'shell.js']) {
    for (const match of source(file).matchAll(/\bt\('([^']+)'/g)) {
      assert.ok(Object.hasOwn(dictionaries.en, match[1]), `${file}: missing ${match[1]}`);
    }
  }
  h.evaluate(`setLanguage('ru'); delete I18N.ru['chat.submit']`);
  assert.equal(h.evaluate(`t('chat.submit')`), dictionaries.en['chat.submit']);
  assert.equal(h.evaluate(`t('missing.key')`), 'missing.key');
  assert.equal(h.evaluate(`t('constructor')`), 'constructor');
  h.evaluate(`I18N.ru['chat.submit'] = 'Искать в источниках'; setLanguage('it-IT')`);
  assert.equal(h.storage.get('gnosis-lang'), 'it');
  assert.equal(h.document.documentElement.lang, 'it');
  h.evaluate(`setLanguage('unknown')`);
  assert.equal(h.evaluate('currentLanguage'), 'en');
  assert.equal(h.evaluate(`t('overview.counts', {sources: '$& {messages}', messages: 2, digests: 3})`),
    '$& {messages} active sources · 2 messages · 3 digests');
  const blocked = harness({blocked: true});
  blocked.evaluate(`setLanguage('zh')`);
  assert.equal(blocked.evaluate('currentLanguage'), 'zh');
  for (const locale of Object.keys(dictionaries)) {
    h.evaluate(`setLanguage('${locale}')`);
    const date = '2026-02-03T14:05:06Z';
    assert.equal(h.evaluate(`formatDate('${date}')`), new Date(date).toLocaleString(locale));
    assert.equal(h.evaluate(`formatDate('${date}', true)`), new Date(date).toLocaleDateString(locale));
    assert.equal(h.evaluate(`formatDate('2026-02-03', true)`), new Date(2026, 1, 3).toLocaleDateString(locale));
    assert.equal(h.evaluate(`formatDate('invalid')`), dictionaries[locale]['date.unknown']);
    assert.equal(h.evaluate(`formatDate(null)`), dictionaries[locale]['date.unknown']);
  }

  h.evaluate(`globalThis.testField = field({id: 'key', labelKey: 'workspace.name', helpKey: 'workspace.nameHelp', secret: true});
    document.root.append(testField); setLanguage('en');`);
  const field = h.context.testField;
  const [header, help, input] = field.children;
  const [label, info] = header.children;
  assert.equal(label.htmlFor, input.id);
  assert.equal(input.type, 'password');
  assert.equal(input.attrs['aria-describedby'], help.id);
  assert.equal(info.attrs['aria-controls'], help.id);
  assert.equal(info.attrs['aria-expanded'], 'false');
  info.events.click();
  assert.equal(help.hidden, false);
  assert.equal(info.attrs['aria-expanded'], 'true');
  input.value = 'untranslated secret $& {n}';
  h.evaluate(`setLanguage('es')`);
  assert.equal(label.textContent, dictionaries.es['workspace.name']);
  assert.equal(help.textContent, dictionaries.es['workspace.nameHelp']);
  assert.equal(info.attrs['aria-label'], dictionaries.es['settings.info']);
  assert.equal(input.value, 'untranslated secret $& {n}');
  assert.equal(help.hidden, false);
  assert.equal(h.evaluate(`safeSourceURL('https://discord.com/channels/1/2/3')`), 'https://discord.com/channels/1/2/3');
  assert.ok(h.evaluate(`['javascript:alert(1)', 'data:text/html,x', '/relative', 'bad'].map(safeSourceURL).every(value => value === null)`));
  h.evaluate(`globalThis.errorBox = el('div'); document.root.append(errorBox); showError(errorBox, new Error('original <diagnostic>'));`);
  assert.equal(h.context.errorBox.children[0].attrs.role, 'alert');
  h.evaluate(`setLanguage('zh')`);
  assert.equal(h.context.errorBox.querySelector('p').textContent, `${dictionaries.zh.error}: ${dictionaries.zh['error.unexpected']}`);
  assert.equal(h.context.errorBox.querySelector('pre').textContent, 'original <diagnostic>');
  assert.equal(h.context.errorBox.querySelector('summary').textContent, dictionaries.zh['error.details']);

  input.required = true; input.value = '';
  h.document.dispatchEvent({type: 'invalid', target: input});
  assert.equal(input.customMessage, dictionaries.zh['validation.required']);
  h.evaluate(`setLanguage('es')`);
  assert.equal(input.customMessage, dictionaries.es['validation.required']);
  input.type = 'number'; input.required = false; input.min = '1'; input.value = '0';
  h.document.dispatchEvent({type: 'invalid', target: input});
  assert.equal(input.customMessage, dictionaries.es['validation.minimum'].replace('{min}', '1'));
  input.value = '2'; h.document.dispatchEvent({type: 'input', target: input});
  assert.equal(input.customMessage, '');

  // HTTP, malformed responses and network failures have translated UI and untouched diagnostics.
  for (const [status, key, detail] of [
    [400, 'validation', 'bad value'], [401, 'auth'], [403, 'forbidden'], [404, 'notFound'],
    [409, 'conflict'], [422, 'validation', [{loc: ['body', 'name'], msg: 'missing'}]],
    [429, 'rateLimit'], [500, 'server'], [503, 'server'], [418, 'unexpected'],
  ]) {
    const r = harness({fetcher: async () => ({ok: false, status, statusText: 'status', json: async () => ({detail})})});
    r.load('ui.js');
    const error = await r.evaluate(`request('/test').catch(error => error)`);
    assert.equal(error.localeKey, `error.${key}`);
    assert.equal(error.message, typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : 'status');
  }
  for (const [fetcher, key] of [
    [async () => { throw new Error('offline'); }, 'network'],
    [async () => ({ok: true, json: async () => { throw new Error('bad JSON'); }}), 'response'],
  ]) {
    const r = harness({fetcher}); r.load('ui.js');
    assert.equal((await r.evaluate(`request('/test').catch(error => error)`)).localeKey, `error.${key}`);
  }

  // Every chat submission carries the selected locale and workspace; switching in place
  // retains questions, answers, source metadata and the request already in flight.
  for (const locale of Object.keys(dictionaries)) {
    let resolve;
    const r = harness({fetcher: () => new Promise(done => { resolve = done; })});
    r.storage.set('gnosis-workspace', '7');
    r.load('ui.js'); r.load('modules.js');
    r.evaluate(`setLanguage('${locale}'); globalThis.container = el('div'); document.root.append(container); renderChat(container)`);
    const container = r.context.container;
    const textarea = container.querySelector('textarea');
    textarea.value = 'original question <text> $& {n}';
    const pending = container.querySelector('form').events.submit(submitEvent);
    assert.equal(r.calls[0].url, '/api/chat');
    assert.deepEqual(JSON.parse(r.calls[0].options.body), {question: textarea.value, workspace_id: 7, locale});
    assert.equal(container.querySelector('.answer').textContent, dictionaries[locale]['chat.searching']);
    r.evaluate(`setLanguage('ru')`);
    assert.equal(container.querySelector('.answer').textContent, dictionaries.ru['chat.searching']);
    resolve({ok: true, json: async () => ({answer: 'original answer <b> $& {n}', sources: []})});
    await pending;
    assert.equal(container.querySelector('.answer').attrs['aria-busy'], 'false');
    assert.equal(container.querySelector('button').disabled, false);
    r.evaluate(`setLanguage('zh')`);
    assert.equal(textarea.value, 'original question <text> $& {n}');
    assert.equal(container.querySelector('label').children.at(-1), textarea);
    assert.ok(container.querySelector('.answer').textContent.includes('original answer <b> $& {n}'));
    assert.ok(container.querySelector('.answer').textContent.includes(dictionaries.zh['chat.noSources']));
    assert.equal(r.calls.length, 1);
  }

  const fixtures = {
    '/api/setup': [{key: 'chat', ready: false, required: true, fields: ['GNOSIS_CHAT_API_KEY']}],
    '/api/stats': {sources: 1, messages: 2, digests: 3},
    '/api/chat': {answer: 'Scoped answer', sources: []},
    '/api/config': Object.keys(dictionaries.en).filter(key => key.startsWith('field.') && key.endsWith('.label')).map(key => ({
      key: key.slice(6, -6), section: key.includes('DISCORD') ? 'discord' : key.includes('TELEGRAM') ? 'telegram' : key.includes('REDDIT') ? 'reddit' : 'llm', value: 'masked preview', secret: true,
    })),
    '/api/sources': [{platform: 'discord', external_id: '1', name: 'User channel <text>', enabled: true, topics: []}],
    '/api/available-sources': [{name: 'User channel <text>', external_id: '1', workspace_name: 'User server'}],
    '/api/digests': [{id: 1, period_start: '2026-02-02T23:00:00Z', period_date: '2026-02-03', markdown: 'Original digest <text>', workspace_name: 'User server'}],
    '/api/status': {workers: [{component: 'discord', status: 'ok'}, {component: 'pipeline', status: 'error', detail: 'Original diagnostic'}], sources: [{platform: 'discord', name: 'User channel', pending: 4, last_processed_at: '2026-02-03T14:05:06Z'}]},
    '/api/usage': [{model: 'User model', prompt_tokens: 10, completion_tokens: 20}],
    '/api/entities': [{id: 1, name: 'User entity', type: 'User type', mentions: 2}],
    '/api/entities/1': {entity: {name: 'User entity', type: 'User type'}, mentions: [{id: 1, author: 'User author', source_name: 'User channel', sent_at: '2026-02-03T14:05:06Z', url: 'https://example.org/message'}]},
    '/api/settings/retention': {days: 30},
    '/api/ignored-authors': [{platform: 'discord', author_id: 'User author ID'}],
    '/api/workspaces': [{id: 7, name: 'User server'}],
    '/api/bots': [],
  };
  const app = harness({fetcher: async url => ({ok: true, json: async () => fixtures[url.split('?')[0]]})});
  app.context.Shell = {reloadWorkspaces: async () => {}};
  app.load('ui.js'); app.load('modules.js');
  for (const renderer of ['renderOverview', 'renderDigests', "renderPlatform('discord')", "renderPlatform('telegram')", "renderPlatform('reddit')", 'renderStatus', 'renderGraph', 'renderSettings']) {
    app.evaluate(`setLanguage('en'); globalThis.container = el('div'); document.root.replaceChildren(container)`);
    await app.evaluate(`(${renderer})(container)`);
    await settle();
    const container = app.context.container;
    assert.equal(container.querySelector('.error'), null, renderer);
    if (renderer === 'renderGraph') {
      await container.querySelectorAll('button').find(button => button.textContent === 'User entity').events.click();
    }
    const inputs = container.querySelectorAll('input, textarea');
    inputs.forEach((input, index) => { input.value = `User draft ${index} <text>`; });
    for (const locale of ['it', 'es', 'ru', 'zh']) {
      app.evaluate(`setLanguage('${locale}')`);
      inputs.forEach((input, index) => assert.equal(input.value, `User draft ${index} <text>`, `${renderer}: preserve input`));
      assert.equal(container.querySelector('.error'), null, `${renderer}: ${locale}`);
      assert.ok(!container.textContent.includes('[object Object]'), `${renderer}: invalid copy`);
    }
    if (renderer === 'renderOverview') assert.ok(container.textContent.includes(dictionaries.zh['field.GNOSIS_CHAT_API_KEY.label']));
    if (renderer === 'renderDigests') {
      assert.ok(container.textContent.includes('Original digest <text>'));
      assert.equal(container.querySelector('strong').textContent,
        `${new Date(2026, 1, 3).toLocaleDateString('zh')} · User server`);
      assert.equal(new Date(fixtures['/api/digests'][0].period_start).getDate(), 2);
    }
    if (renderer === 'renderStatus') {
      assert.ok(container.textContent.includes(dictionaries.zh['status.component.pipeline']));
      assert.ok(container.textContent.includes('Original diagnostic'));
      assert.ok(container.textContent.includes(dictionaries.zh['status.tokens'].replace('{input}', '10').replace('{output}', '20')));
      assert.ok(container.textContent.includes(new Date('2026-02-03T14:05:06Z').toLocaleString('zh')));
    }
    if (renderer === 'renderGraph') assert.ok(container.textContent.includes('User author'));
  }

  // Shell language changes must not remount the active module or discard its DOM.
  for (const storageBlocked of [false, true]) {
    const shell = harness({blocked: storageBlocked, fetcher: async url => ({ok: true, json: async () => fixtures[url.split('?')[0]]})});
    shell.load('ui.js'); shell.load('modules.js');
    for (const [tag, id] of [['select', 'workspace-select'], ['select', 'language-select'], ['nav', 'rail'], ['div', 'module'], ['span', 'brand-name'], ['main', 'main']]) {
      const node = new Node(tag); node.id = id; shell.document.root.append(node);
    }
    const skip = new Node('a'); skip.className = 'skip-link'; shell.document.root.append(skip);
    const languagePicker = shell.document.getElementById('language-select');
    languagePicker.setAttribute('data-i18n-aria-label', 'language.label');
    shell.load('shell.js'); await settle();
    const chat = shell.document.getElementById('module').firstChild;
    const draft = chat.querySelector('textarea'); draft.value = 'Keep this draft';
    shell.evaluate(`setLanguage('es')`);
    assert.equal(shell.document.getElementById('module').firstChild, chat);
    assert.equal(draft.value, 'Keep this draft');
    assert.equal(languagePicker.value, 'es');
    assert.equal(languagePicker.attrs['aria-label'], dictionaries.es['language.label']);
    assert.equal(languagePicker.children.length, 5);

    // Workspace selection survives blocked storage, locale updates and picker reloads.
    const workspacePicker = shell.document.getElementById('workspace-select');
    workspacePicker.value = '7';
    workspacePicker.events.change({target: workspacePicker});
    assert.equal(shell.evaluate('AppState.workspaceId()'), 7);
    assert.equal(shell.evaluate('AppState.scopeQuery()'), '?workspace_id=7');
    assert.equal(shell.evaluate('AppState.currentWorkspace().name'), 'User server');
    assert.equal(shell.storage.get('gnosis-workspace'), storageBlocked ? undefined : '7');
    shell.evaluate(`setLanguage('it')`);
    await shell.evaluate('Shell.reloadWorkspaces()');
    assert.equal(workspacePicker.value, '7');
    const scopedChat = shell.document.getElementById('module').firstChild;
    scopedChat.querySelector('textarea').value = 'Scoped question';
    await scopedChat.querySelector('form').events.submit(submitEvent);
    assert.deepEqual(JSON.parse(shell.calls.find(call => call.url === '/api/chat').options.body),
      {question: 'Scoped question', workspace_id: 7, locale: 'it'});
    assert.equal(scopedChat.querySelector('.error'), null);
    assert.ok(scopedChat.querySelector('.answer').textContent.includes('Scoped answer'));
    workspacePicker.value = 'all';
    workspacePicker.events.change({target: workspacePicker});
    assert.equal(shell.evaluate('AppState.workspaceId()'), null);
    assert.equal(shell.evaluate('AppState.scopeQuery()'), '');
  }

  const css = source('style.css');
  assert.ok(css.includes(':focus-visible'));
  assert.ok(css.includes('[hidden] { display: none !important; }'));
  assert.equal((css.match(/{/g) || []).length, (css.match(/}/g) || []).length);
  const html = source('index.html');
  assert.ok(html.includes('<html lang="en">'));
  assert.ok(html.includes('class="skip-link"'));
  assert.ok(html.includes('for="workspace-select"'));
  assert.ok(html.includes('data-i18n-aria-label="language.label"'));
  // Scripts are served directly; stale bundles must not ship.
  const scripts = fs.readdirSync(staticDir).filter(file => file.endsWith('.js'));
  const loaded = [...html.matchAll(/<script\b[^>]*\bsrc="\/([^"/]+\.js)"/g)].map(match => match[1]);
  assert.deepEqual(scripts.sort(), loaded.sort());
  console.log('frontend contracts and i18n (en, it, es, ru, zh): OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
