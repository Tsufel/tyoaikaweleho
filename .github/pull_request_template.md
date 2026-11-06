## What and why

## Checklist

- [ ] `ruff check .` and `pytest --cov` pass
- [ ] `npm run check`, `npm test` and `npm run build` pass in `frontend/`
- [ ] API changes go end to end: controller → `api.py` → `types.ts` → `mock.ts` → `docs/V2_UI_API.md` (see `docs/DEVELOPMENT.md`)
- [ ] No way to lose data in `data.json`, backups, `session.json` or `shifts.txt`
- [ ] Tried in the app with `WELEHO_DATA_DIR` set to a scratch folder, not the real data
