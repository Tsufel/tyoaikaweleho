# Työaikaweleho v2.x — Multi-PC sync (design plan)

> Status: **planning** — nothing in this document is implemented yet.
> Builds on [V2_AUTH_PLAN.md](V2_AUTH_PLAN.md) (local accounts + encryption).
> Constraint: must be **free** for every user, with no server for us to run.

## Why

A user works on more than one PC (e.g. work laptop + home desktop) and wants
the same timesheet on all of them. A handful of people use the app, each with
their **own private** data — nobody reads anyone else's timesheet, and there
is no admin view.

## Key idea: the backend is a dumb, untrusted file store

All data is encrypted on the PC before it leaves (see *Encryption* below), so
wherever the files end up never sees plaintext. That makes the choice of
backend purely about cost, friction and maintenance — the encryption, the
merge logic and the storage refactor are identical for every backend.

## Backend options considered

| # | Backend | Sign-in | Cost / ops | Verdict |
|---|---------|---------|------------|---------|
| A | **Synced folder** — OneDrive (built into Windows 11), Google Drive for Desktop, Dropbox, Syncthing | none (the folder is the sync) | free, nothing to run, no network code | **chosen** |
| B | Personal cloud API — OneDrive Graph `approot`, Dropbox App folder, Google Drive `appDataFolder` | user's own Microsoft/Dropbox/Google OAuth | free; register one OAuth app | not now — OAuth flow + token storage for little gain over A |
| C | Backend-as-a-service — Firebase (Auth + Firestore) / Supabase | app's own email + password | free tiers; Supabase free projects pause after ~7 days idle | **fallback** (Firebase) if in-app accounts are wanted |
| D | Own tiny API — Cloudflare Worker + KV/D1, PocketBase on a VPS | own accounts | Worker free tier, or ~€4/mo VPS; we maintain it | not chosen — we'd operate a service |
| E | LAN / peer-to-peer | device pairing | free | not chosen — can't sync work ↔ home |
| F | GitHub private repo / gist | personal token | free | not chosen — unsuitable for non-developers |

**Why not one shared Drive/cloud account for everyone:** it would require
embedding a service account or token in the exe. Anyone could extract it and
read, delete or flood the storage, Google service accounts no longer have
their own quota, and we would be hosting other people's personal data (GDPR).
Each user syncing through **their own** storage avoids all of that.

## Chosen design: synced folder with per-device files

```
<sync folder>/Tyoaikaweleho/          (e.g. %OneDrive%\Tyoaikaweleho)
  account.json                        plaintext: format, user id, username,
                                      scrypt salt + params, wrapped DEK (password),
                                      wrapped DEK (recovery key)
  devices/
    <device-id>.enc                   AES-GCM(DEK, this device's full state)
    <other-device-id>.enc

%APPDATA%/Tyoaikaweleho/users/<user-id>/
  data.enc                            local encrypted working copy (source of truth offline)
  sync.json                           sync folder path, device id, last merged versions
  session.json                        running timer (per machine, not synced)
```

- **Each PC writes only its own `devices/<device-id>.enc`** and reads all the
  others. No two PCs ever write the same file, so the sync client never makes
  conflict copies and offline edits can't be overwritten.
- `account.json` is written once at setup (and on password change). It lets a
  new PC unlock the data with the same password.
- Any stray conflict copies (`account (1).json`, `… -DESKTOP-X.json`) are
  ignored for devices and reported for `account.json`.

### Setup flow

1. **First PC:** Settings → *Sync* → pick folder (pre-filled with `%OneDrive%`
   when detected) → the existing account's `account.json` is written and this
   device's file is created.
2. **Another PC:** first launch → *"Restore from sync folder"* → pick the same
   folder → enter password → DEK unwrapped → all device files merged into a
   new local copy.
3. Disconnect: stop writing; the device file is left in place (other PCs keep
   its last state; it can be removed from Settings).

### Sync cycle

Runs in a background thread: at startup, ~30 s after a save (debounced), every
5 minutes, and on close. Status shown in the UI: *Synced / Waiting for folder /
Error*.

1. Write own state to `devices/<me>.enc` (atomic temp + `os.replace`, same
   pattern as `storage._save_raw`).
2. For every other device file whose mtime/size changed since last merge:
   decrypt, merge into the local copy.
3. If the merge changed anything, save locally and refresh the open views.

## Data model changes (sync-ready)

- Every entry gains `updated_at` (ISO UTC) set on create/edit.
- Deletes become **tombstones** (`{"id": …, "deleted": true, "updated_at": …}`)
  instead of removing the row; `load_*` hides them. Tombstones older than
  90 days are purged.
- Synced settings get per-key timestamps: `pay_rate`, `default_start_time`,
  `default_job_shift`, `export_format`, `export_include_pay`, and the shift
  list (moved from `shifts.txt` into the payload; `add_job_shift` keeps its
  signature).
- Per-machine keys stay local: `window_geometry`, `last_seen_version`,
  `appearance_mode`, `session.json`.
- **Merge rule:** per entry id and per settings key, the newer `updated_at`
  wins; ties broken by device id so every PC converges to the same result.
  Merge is pure, commutative and idempotent.

## Encryption (shared with V2_AUTH_PLAN phase 2)

- **Envelope encryption.** A random 256-bit data key (DEK) encrypts the data
  with **AES-GCM** (`cryptography` package, the only new dependency).
- The DEK is wrapped by `KEK = hashlib.scrypt(password, salt, n=2**17, r=8, p=1)`.
  A wrong password fails the unwrap — no separate password hash is stored.
- Password change = re-wrap the DEK; data files are untouched.
- A one-time **recovery key** (random, shown once at setup) wraps the DEK a
  second time. Forgotten password *and* lost recovery key = lost data; the UI
  must say so plainly.
- Blob format: `b"TYW1" | 12-byte nonce | ciphertext+tag`, with the device id
  as associated data so files can't be swapped between devices unnoticed.
- The DEK is held in memory only while signed in.

## Fallback: Firebase (if in-app accounts are wanted later)

If users should be able to "create account / sign in" without installing a
sync client, add `services/transport_firebase.py` on the **Spark (free)**
plan — no idle pausing, and a few users are far below the limits:

- Firebase Auth (email + password) via the Identity Toolkit REST API and
  Firestore REST via `urllib` — no SDK.
- Bitwarden-style keys: `master = scrypt(password, email)`,
  `enc_key = HKDF(master, "enc")` never leaves the PC,
  `auth_key = HKDF(master, "auth")` is used as the Firebase password. Google
  can verify logins but can never decrypt data.
- Security rules must restrict every document to
  `request.auth.uid == userId`; the public API key is only safe with them.
- The same per-device encrypted blobs are stored as documents; the core
  (crypto, merge, storage) is unchanged.

## Code impact

| File | Change |
|------|--------|
| `storage.py` | `set_active_user(dir, dek)`; `_load_raw`/`_save_raw` decrypt/encrypt with an in-memory cache; `updated_at`, tombstones, shifts in payload. Public API unchanged, so `ui/*`, `image_ocr.py`, `import_excel.py` are untouched. |
| `timer.py` | Session file in the per-user dir. |
| `services/auth.py` (new) | Account create/unlock, scrypt, DEK wrap/unwrap, recovery key. |
| `services/crypto_box.py` (new) | AES-GCM blob format. |
| `services/sync.py` (new) | Pure merge function + background sync worker. |
| `services/transport_folder.py` (new) | Read/write device files and `account.json` in the sync folder. |
| `ui/login_window.py` (new) | Sign in, create account, restore from sync folder. |
| `ui/settings_view.py` | Sync section: folder, status, devices, change password, recovery key. |
| `main.py` | Login → `storage.set_active_user` → `App()`. |
| `tests/conftest.py` | `tmp_storage` also sets an active user + test DEK. |

## Testing plan

- `tests/test_sync.py`: concurrent edits, tombstones beat older edits and lose
  to newer ones, settings keys, tie-breaking, commutativity, idempotency.
- `tests/test_crypto_box.py`: round-trip, tampered ciphertext / wrong device
  id rejected.
- `tests/test_auth.py`: wrap/unwrap, wrong password, recovery key, password
  change keeps data readable.
- `tests/test_transport_folder.py`: two fake device dirs sharing one folder
  converge; conflict-copy files ignored.
- Manual: two PCs on the same OneDrive — add on A → appears on B; delete on
  B → gone on A; edit both offline, reconnect → both edits kept.

## Implementation order

1. V2_AUTH_PLAN phases 1–2 (local accounts + envelope encryption).
2. Sync-ready data model (`updated_at`, tombstones, settings timestamps) +
   merge function and tests.
3. Folder transport + background worker + Settings sync section.
4. "Restore from sync folder" flow on a new PC.
5. (Only if needed) Firebase transport.
