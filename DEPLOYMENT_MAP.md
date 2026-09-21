# AEON Deployment Map

## Canonical Roles

- Source tree: `/root/aeon-finale-formv1.2.3.6`
- Live tree: `/var/www/aeon-finale-formv1.2.3.6.5`

Do not treat both as active edit targets. Edit in `/root`, then deploy to `/var/www`.

## Live Traffic Path

- Nginx serves the public frontend from `/var/www/aeon-finale-formv1.2.3.6.5/frontend/build`
- Nginx proxies `/api` and `/ws` to `127.0.0.1:8000`
- PM2 runs `aeon-backend` from `/var/www/aeon-finale-formv1.2.3.6.5/backend`

## Correct Deploy Flow

1. Make code changes in `/root/aeon-finale-formv1.2.3.6`
2. Run `/root/aeon-sync.sh --full`
3. Verify PM2/nginx health

`/root/start-aeon.sh` now delegates to that deploy flow and defaults to `--full`.

## Important Detail

Backend-only sync is not enough when frontend code changed.

Before this cleanup, `aeon-sync.sh --full` rebuilt the frontend in `/var/www` but did not first sync frontend source from `/root`. That created split-brain deploys where backend changes were live but frontend changes were not.

The script now syncs:

- `/root/.../backend` -> `/var/www/.../backend`
- `/root/.../frontend` -> `/var/www/.../frontend` when `--full` is used

## Operational Rule

If a change should be visible on `aeontrading.xyz`, it is not deployed until it exists in `/var/www/aeon-finale-formv1.2.3.6.5`.
