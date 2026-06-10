# Työaikaweleho v2.0 — Secure local user sign-in (design plan)

> Status: **planning** — nothing in this document is implemented yet.
> Scope constraint: v2 must keep working **fully locally and offline**. No server, no
> network authentication, no telemetry.

## Why

Today the app is single-user: anyone who opens it sees and can edit the timesheet,
and `data.json` sits unprotected next to the exe. v2 adds named user accounts with
password sign-in so that (a) multiple people can share one machine with separate
timesheets, and (b) a user's data can optionally be encrypted at rest.

## Goals / non-goals

| Goals | Non-goals (v2) |
|-------|----------------|
| Local username + password sign-in | Cloud accounts / OAuth / SSO |
| Per-user timesheet data and settings | Syncing between machines |
| Industry-standard password hashing with stdlib only | Protecting against an attacker with admin rights and a debugger |
| Migration of existing single-user data | Multi-user *concurrent* use (one session at a time is fine) |
| Optional at-rest encryption (phase 2) | Password recovery via email |

## Account storage

`%APPDATA%/Tyoaikaweleho/users.json` (atomic writes + `.bak`, same pattern as
`storage._save_raw`):

```json
{
  "format": 1,
  "users": [
    {
      "id": "9f3c…(uuid4)",
      "username": "exampleuser",
      "salt": "<base64, 32 bytes from secrets.token_bytes(32)>",
      "pwd_hash": "<base64 PBKDF2-HMAC-SHA256, 600_000 iterations>",
      "iterations": 600000,
      "created": "2026-06-10T12:00:00",
      "failed_attempts": 0,
      "locked_until": null
    }
  ]
}
```

Security decisions:

- **Hashing**: `hashlib.pbkdf2_hmac("sha256", password, salt, iterations)` —
  pure stdlib, no new dependencies. 600k iterations matches current OWASP
  guidance for PBKDF2-SHA256. Store `iterations` per user so it can be raised
  later and old hashes upgraded transparently on next successful sign-in.
- **Verification**: `hmac.compare_digest` (constant-time).
- **Throttling**: after 5 consecutive failures, lock the account for 30 s,
  doubling per subsequent failure (cap 15 min). Persist `failed_attempts` /
  `locked_until` so restarting the app doesn't reset the counter.
- **Username rules**: case-insensitive unique, 1–32 chars, no path separators
  (the id — not the username — names the data directory, so usernames never
  touch the filesystem).
- **Password rules**: minimum 8 characters; show a strength hint but don't
  block beyond the minimum (local app, user is protecting their own data).

## Per-user data

```
%APPDATA%/Tyoaikaweleho/
  users.json
  users/
    <user-id>/
      data.json        (+ .bak)
      shifts.txt
      session.json     (crash-recovery timer session)
```

- `storage.py` gains `set_active_user(data_dir: str)` called once after
  sign-in, before the main window opens; all existing accessors keep their
  signatures, so the rest of the app and the OCR DLC (`import storage`) are
  untouched.
- `timer.py` session file moves into the user dir the same way.

## Sign-in flow

New modules (following the v1.1 layout):

- `services/auth.py` — account CRUD, hash/verify, lockout logic. Pure logic,
  fully unit-testable without a display.
- `ui/login_window.py` — small CTk window shown by `main.py` before `App`:
  - user picker (dropdown of existing usernames) + password field
  - "Create account" view (username, password, confirm)
  - "Change password" from the signed-in App's Settings (requires current
    password)
  - Enter submits; errors shown inline, generic "wrong username or password"
    (don't reveal which was wrong)
- `main.py` sequence: `login_window.run()` → returns the authenticated user →
  `storage.set_active_user(...)` → `App().mainloop()`.
- Sign-out menu item in App closes the main window and returns to the login
  window (timer must be stopped or saved first, reusing the existing
  close-handler logic).

## Migration

First launch of v2 with an existing `data.json` next to the exe:

1. Login window shows "Set up your account" (create the first user).
2. After creation, move `data.json`, `shifts.txt`, and `session.json` into
   `users/<id>/` (copy + verify + delete, never delete-first).
3. Leave a `data.json.migrated-to-v2` marker so a downgrade doesn't silently
   start a second data file.

## Phase 2 (optional, separate release): encryption at rest

- Encrypt `users/<id>/data.json` with **Fernet** (AES-128-CBC + HMAC) from the
  `cryptography` package — the only new dependency, added only when this
  phase ships.
- Key = PBKDF2(password, per-user `enc_salt`, 600k) — derived at sign-in,
  held in memory only; **never written to disk**.
- Opt-in per user ("Encrypt my data" checkbox at account creation or in
  Settings), because the trade-off is real: **forgotten password = lost
  data**.
- Mitigation: on enabling encryption, generate a one-time recovery key
  (base64 of the raw data key), show it once, and tell the user to store it
  somewhere safe; accept it in a "Forgot password" flow to re-key.
- Export to Excel remains plaintext by definition — warn in the UI.

## Out-of-scope hardening noted for later

- Code-signing the installer (removes the SmartScreen warning and makes the
  updater's checksum verification redundant rather than primary).
- Auto-lock the app after N minutes idle (cheap once sign-in exists).

## Testing plan

- `tests/test_auth.py`: hash round-trip, wrong password, constant-time path,
  lockout schedule, username normalization, iteration-upgrade on sign-in.
- `tests/test_migration.py`: v1 → v2 data move, marker file, idempotency.
- UI flows verified manually (login, create, change password, sign-out)
  plus the existing storage suite re-run against a per-user data dir.

## Implementation order

1. `services/auth.py` + tests (no UI).
2. `storage.set_active_user` + per-user dirs + migration + tests.
3. `ui/login_window.py` + `main.py` wiring.
4. Sign-out + change-password in Settings.
5. (Later release) Phase 2 encryption.
