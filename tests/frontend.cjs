// Dependency-free DOM contract checks; no server, browser or model downloads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.dataset = {}; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(key, callback) { this.events[key] = callback; }
}
const context = vm.createContext({
  document: {createElement: tag => new Node(tag)},
  t: key => key, URL,
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/gnosis/static/ui.js'), 'utf8'), context);
vm.runInContext(`
  globalThis.testField = field({id: 'key', labelKey: 'Key', helpKey: 'Help', secret: true});
  globalThis.validURL = safeSourceURL('https://discord.com/channels/1/2/3');
  globalThis.invalidURLs = ['javascript:alert(1)', 'data:text/html,x', '/relative', 'bad'].map(safeSourceURL);
  globalThis.errorBox = el('div');
  showError(errorBox, new Error('failed'));
`, context);
const field = context.testField;
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
assert.equal(context.validURL, 'https://discord.com/channels/1/2/3');
assert.ok(context.invalidURLs.every(value => value === null));
assert.equal(context.errorBox.children[0].attrs.role, 'alert');
const css = fs.readFileSync(path.join(__dirname, '../src/gnosis/static/style.css'), 'utf8');
assert.ok(css.includes(':focus-visible'));
assert.ok(css.includes('[hidden] { display: none !important; }'));
assert.equal((css.match(/{/g) || []).length, (css.match(/}/g) || []).length);
const html = fs.readFileSync(path.join(__dirname, '../src/gnosis/static/index.html'), 'utf8');
assert.ok(html.includes('class="skip-link"'));
assert.ok(html.includes('for="workspace-select"'));
// This frontend loads every script directly from index.html; stale bundles must not ship.
const scripts = fs.readdirSync(path.join(__dirname, '../src/gnosis/static')).filter(file => file.endsWith('.js'));
const loaded = [...html.matchAll(/<script\b[^>]*\bsrc="\/([^"/]+\.js)"/g)].map(match => match[1]);
assert.deepEqual(scripts.sort(), loaded.sort());
console.log('frontend contracts: OK');
