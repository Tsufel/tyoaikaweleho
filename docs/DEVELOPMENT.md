# Development notes

How to work on Työaikaweleho without breaking the Python ⇄ JS contract or
anyone's timesheet. The README covers setup and running from source.

## Keep real data out of it

- Run the app with `WELEHO_DATA_DIR` set to a scratch folder. Without it the app
  reads and writes the real `data.json`, `session.json`, `shifts.txt` and backups.
- `python main.py --smoke-test` always uses a temporary folder unless
  `WELEHO_DATA_DIR` is set.
- Tests redirect every data path to temp folders (`tests/conftest.py`). They
  also block outside network connections. A test that really needs the network
  must be marked `@pytest.mark.network`. Loopback servers work without the mark.
- `.gitignore` keeps personal files (`data.json`, backups, `shifts.txt`,
  `session.json`, damaged copies) out of commits. `tests/test_safety_nets.py`
  checks that.

## Checks

Run the same checks as CI before pushing:

```bash
ruff check .                 # lint (config in pyproject.toml)
pytest --cov                 # tests + coverage; fails under fail_under in pyproject.toml

cd frontend
npm run check                # svelte-check + TypeScript (noUnusedLocals is on)
npm test                     # vitest
npm run build
```

- CI (`.github/workflows/tests.yml`) runs these on every push and on pull
  requests to `main`. It also builds the frontend and runs `main.py --smoke-test`.
- Vitest files that need no DOM start with `// @vitest-environment node`, which
  makes them faster. Leave it off for anything that touches `document` or
  `window`.
- `npm run test:watch` re-runs tests as you edit.

## Adding an API method, end to end

The page calls Python through `window.pywebview.api`. A method exists in five
places, and the tests fail until all five agree.

1. **`webapp/controller.py`**: the logic. Return an envelope from
   `webapp/results.py` (`R.ok(...)`, `R.error(code, ...)`, `R.invalid(...)`,
   `R.needs_confirm(...)`). Take the controller lock and do no network or
   dialogs under it.
2. **`webapp/api.py`**: a thin `@_guarded` method that calls the controller.
   Use `_guarded` so an exception becomes an `internal` error result instead of
   a rejected Promise. Give trailing parameters a `None` default, because the
   bridge drops trailing `undefined` args.
3. **`frontend/src/lib/api/types.ts`**: add it to `interface Api`, along with
   any new payload interface.
4. **`frontend/src/lib/api/mock.ts`**: a mock implementation for `?mock`, so
   the browser-only UI keeps working.
5. **`docs/V2_UI_API.md` §5**: add a row to the right method table.

Then add a call to the `calls` list in
`tests/test_api_contract.py::test_every_method_returns_json`, and to `CALLS` in
`frontend/tests/mock.test.ts` if it needs arguments.

These tests check the contract:

| Test | Checks |
|------|--------|
| `tests/test_api_contract.py` | Api methods = `interface Api`; every method returns a JSON-safe envelope |
| `tests/test_literal_contract.py` | §5 tables = Api methods; emitted events, `data:changed` reasons, `R.error` codes and confirm kinds/option ids are declared in `types.ts` and listed in the doc |
| `tests/test_types_contract.py` | Bootstrap, Settings, UiPrefs, TimerState, DlcStatus and MonthData payloads have the fields `types.ts` declares; the doc names every bootstrap field and UI pref |
| `frontend/tests/mock.test.ts` | every mock method returns a JSON-safe envelope |

### Also new: an event, error code, confirm kind or UI pref

- **Event**: add it to `EventMap` in `types.ts` and to the table in doc §11.
  Emit it only through the `EventBus` (`self._emit` in `api.py`), never by
  calling `evaluate_js` directly.
- **Error code**: add it to `ErrorCode` and to the list in doc §2.
- **Confirm kind**: add it to `ConfirmKind` and `ConfirmChoices` (with exactly
  the option ids Python offers) and to doc §3.
- **UI pref**: add it to `storage.UI_PREF_DEFAULTS`, to `UiPrefs` in
  `types.ts`, to the `ui_prefs` defaults in doc §8, and to the mock's seeded
  settings. `merge_ui_prefs` rejects unknown keys, so the frontend and backend
  must ship together.

## Line endings

`.gitattributes` stores text files with LF and checks out `.bat`, `.cmd` and
`.iss` files with CRLF, which `cmd.exe` and Inno Setup need. Don't add
`eol=lf` overrides for those.

## Releasing

Bump `version.py` and `frontend/package.json`, add notes to `changelog.py`,
commit, and push a `vX.Y.Z` tag. `.github/workflows/release.yml` does the rest.
See the README.
