# Dashboard architecture

Gnosis serves a FastAPI dashboard with vanilla HTML/CSS/JavaScript, without a frontend framework
or dedicated build. `src/gnosis/static/index.html` loads the four scripts in order;
`tests/frontend.cjs` also checks that obsolete bundles are not shipped.

| File in `src/gnosis/static/` | Responsibility |
|---|---|
| `index.html` | Initial structure, landmarks, CSS and script loading |
| `i18n.js` | Strings and language selection for English, Italian, Spanish, Russian, and Chinese |
| `ui.js` | DOM helpers, fields, messages, and link validation |
| `modules.js` | Chat, digests, platforms, status, and settings pages |
| `shell.js` | Sidebar, hash routing, workspaces, and links to other bots |
| `style.css` | Color tokens, layout, components, and accessible states |

The `GNOSIS_MODULES` registry defines pages and the `bot`, `platforms`, and `system` groups.
The DOM is built with `createElement` and `textContent`: platform content and model output are
untrusted data, not HTML to execute.

## Backend contract

- `GET /api/bots`: current application and bots configured with `GNOSIS_BOTS`.
  The backend checks reachability; the browser opens the supplied link.
- `GET /api/workspaces`: workspaces for the context selector.
- `GET /api/setup`: configuration status, with help text managed by `i18n.js`.

The API, dashboard, and assets require admin authentication; `/health` is public.
The administrator is a globally trusted operator: the workspace selector is a filter,
not privilege separation. The graph also remains global.

## Language contract

Supported locales are `en`, `it`, `es`, `ru`, and `zh`, with English as default/fallback.
On first use, the dashboard negotiates the browser language; an explicit selection is saved
and takes precedence on later visits. Requests carry the selected locale so RAG answers use
that language, independently of the original source-message language. Interactive Discord and
Telegram bot replies also use a supported interaction/user locale, with English fallback.

Archived digests are not dynamically translated when the locale changes: their original
generation language is retained, including existing Italian digests. New scheduled digests
are generated in English. The operator CLI and installer are English-only.

## Links to Doorman and D-View

Both applications use Next.js and Discord OAuth login; they are not Gnosis modules.
`GNOSIS_BOTS` links already existing installations; it does not share sessions, credentials,
or permissions. Switching to another bot opens a new tab.

The dashboard displays instructions for installing a missing bot, but does not execute host
commands or mount the Docker socket. Installation and authorized operations remain documented
in the [README](../README.md) and [operations guide](operations.md).
