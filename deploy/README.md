# Subscription Admin Deployment

Subscription Admin is a lightweight customer content subscription console.

Default same-server layout:

- FastAPI backend on `127.0.0.1:8000`
- React frontend built to `/opt/hermes-admin/frontend/dist`
- Nginx serves static files and proxies `/api/` to FastAPI
- SQLite database stored under `/opt/hermes-admin/data`

Hermes integration is no longer required for the core product surface. Keep Hermes CLI installed only if you still use the compatibility endpoints or generated command workflows.

## Layout

Recommended install paths:

- `/opt/hermes-admin/backend`
- `/opt/hermes-admin/frontend`
- `/opt/hermes-admin/deploy`
- `/opt/hermes-admin/data`
- `/opt/hermes-admin/backups`

The backend service assumes:

- virtual environment: `/opt/hermes-admin/backend/.venv`
- database: `/opt/hermes-admin/data/hermes_admin.db`
- service user: the Linux user that owns `/opt/hermes-admin`

## Build And Test

Run on the Linux server:

```bash
cd /opt/hermes-admin/backend
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -v

cd /opt/hermes-admin/frontend
npm install
npm run test
rm -rf dist
npm run build
```

If the page still shows old Hermes Admin text after deployment, the frontend `dist` directory is stale. Run `rm -rf dist && npm run build`, then reload Nginx.

## Backend Service

```bash
sudo cp /opt/hermes-admin/deploy/hermes-admin-api.service /etc/systemd/system/hermes-admin-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-admin-api
sudo systemctl status hermes-admin-api --no-pager
```

Verify the backend:

```bash
curl -fsS http://127.0.0.1:8000/api/health/ping
```

## Nginx

For direct IP access, set `server_name _;` in the Nginx config. For a domain, replace `admin.example.com` with the real domain.

Ubuntu example:

```bash
sudo apt update
sudo apt install -y nginx
sudo mkdir -p /etc/nginx/conf.d
sudo cp /opt/hermes-admin/deploy/hermes-admin.nginx.conf /etc/nginx/conf.d/hermes-admin.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

Check routing:

```bash
curl -I http://127.0.0.1
curl -fsS http://127.0.0.1/api/health/ping
```

If `/api/health/ping` returns 404 through Nginx but works on port 8000, Nginx is serving the default site instead of this config. Disable the default site or make this server block the default server for port 80.

## HTTPS

Only needed when exposing the app on a public domain. Do not expose FastAPI port `8000` directly.

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d admin.example.com
sudo certbot renew --dry-run
```

## SQLite Backup

```bash
sudo install -m 0755 /opt/hermes-admin/deploy/backup-sqlite.sh /usr/local/bin/hermes-admin-backup
sudo HERMES_ADMIN_DB_PATH=/opt/hermes-admin/data/hermes_admin.db hermes-admin-backup
```

Optional daily backup:

```bash
echo '20 3 * * * root HERMES_ADMIN_DB_PATH=/opt/hermes-admin/data/hermes_admin.db /usr/local/bin/hermes-admin-backup' | sudo tee /etc/cron.d/hermes-admin-backup
```

## Sync From Local Machine

From Windows PowerShell:

```powershell
scp -r D:\hermes\backend ubuntu@1.117.58.13:/opt/hermes-admin/
scp -r D:\hermes\frontend ubuntu@1.117.58.13:/opt/hermes-admin/
scp -r D:\hermes\deploy ubuntu@1.117.58.13:/opt/hermes-admin/
```

Then on the server:

```bash
cd /opt/hermes-admin/backend
. .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -v

cd /opt/hermes-admin/frontend
npm install
rm -rf dist
npm run test
npm run build

sudo systemctl restart hermes-admin-api
sudo nginx -t
sudo systemctl reload nginx
```

## Troubleshooting

Backend:

```bash
sudo systemctl status hermes-admin-api --no-pager
sudo journalctl -u hermes-admin-api -n 120 --no-pager
curl -fsS http://127.0.0.1:8000/api/health/ping
```

Nginx:

```bash
sudo nginx -t
sudo tail -n 100 /var/log/nginx/error.log
curl -I http://127.0.0.1
curl -fsS http://127.0.0.1/api/health/ping
```

Login:

- Confirm the admin user exists in SQLite.
- Confirm `HERMES_ADMIN_SECRET_KEY` is stable across restarts.
- A `401` response clears the frontend token; sign in again after password changes.

Security:

- Open only ports 22, 80, and 443 unless there is a clear reason.
- Keep `/opt/hermes-admin/data`, `.env`, and SQLite backups out of the Nginx static root.
- Use HTTPS before sharing public access.
