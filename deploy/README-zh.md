# Subscription Admin 部署说明

Subscription Admin 是轻量的客户内容订阅管理台，核心功能是客户项目、内容标签、订阅周期和投递地址管理。

默认同机部署：

- FastAPI 后端监听 `127.0.0.1:8000`
- React 前端构建到 `/opt/hermes-admin/frontend/dist`
- Nginx 提供页面访问，并把 `/api/` 反向代理到 FastAPI
- SQLite 数据库放在 `/opt/hermes-admin/data`

核心产品不再要求实时接 Hermes。只有继续使用兼容接口或命令生成流程时，才需要保留 Hermes CLI。

## 目录

推荐路径：

- `/opt/hermes-admin/backend`
- `/opt/hermes-admin/frontend`
- `/opt/hermes-admin/deploy`
- `/opt/hermes-admin/data`
- `/opt/hermes-admin/backups`

## 构建和测试

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

如果访问页面还是旧的 Hermes Admin，说明 `dist` 没有重新构建。执行 `rm -rf dist && npm run build`，然后 reload Nginx。

## 后端服务

```bash
sudo cp /opt/hermes-admin/deploy/hermes-admin-api.service /etc/systemd/system/hermes-admin-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-admin-api
sudo systemctl status hermes-admin-api --no-pager
```

检查后端：

```bash
curl -fsS http://127.0.0.1:8000/api/health/ping
```

## Nginx

不绑定域名、直接 IP 访问时，可以把 Nginx 配置里的 `server_name` 设为 `_`。绑定域名时，把 `admin.example.com` 替换成真实域名。

Ubuntu 示例：

```bash
sudo apt update
sudo apt install -y nginx
sudo mkdir -p /etc/nginx/conf.d
sudo cp /opt/hermes-admin/deploy/hermes-admin.nginx.conf /etc/nginx/conf.d/hermes-admin.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

检查路由：

```bash
curl -I http://127.0.0.1
curl -fsS http://127.0.0.1/api/health/ping
```

如果 `127.0.0.1:8000/api/health/ping` 正常，但 Nginx 下的 `/api/health/ping` 是 404，说明 Nginx 命中了默认站点。禁用默认站点，或把本项目 server block 设为 80 端口默认站点。

## HTTPS

只有公网域名访问时才需要。不要把 FastAPI 的 `8000` 端口直接暴露到公网。

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d admin.example.com
sudo certbot renew --dry-run
```

## SQLite 备份

```bash
sudo install -m 0755 /opt/hermes-admin/deploy/backup-sqlite.sh /usr/local/bin/hermes-admin-backup
sudo HERMES_ADMIN_DB_PATH=/opt/hermes-admin/data/hermes_admin.db hermes-admin-backup
```

每天自动备份：

```bash
echo '20 3 * * * root HERMES_ADMIN_DB_PATH=/opt/hermes-admin/data/hermes_admin.db /usr/local/bin/hermes-admin-backup' | sudo tee /etc/cron.d/hermes-admin-backup
```

## 从本地同步到服务器

Windows PowerShell：

```powershell
scp -r D:\hermes\backend ubuntu@1.117.58.13:/opt/hermes-admin/
scp -r D:\hermes\frontend ubuntu@1.117.58.13:/opt/hermes-admin/
scp -r D:\hermes\deploy ubuntu@1.117.58.13:/opt/hermes-admin/
```

服务器上执行：

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

## 排查

后端：

```bash
sudo systemctl status hermes-admin-api --no-pager
sudo journalctl -u hermes-admin-api -n 120 --no-pager
curl -fsS http://127.0.0.1:8000/api/health/ping
```

Nginx：

```bash
sudo nginx -t
sudo tail -n 100 /var/log/nginx/error.log
curl -I http://127.0.0.1
curl -fsS http://127.0.0.1/api/health/ping
```

登录：

- 确认 SQLite 里已经创建管理员用户。
- 确认 `HERMES_ADMIN_SECRET_KEY` 重启前后保持一致。
- 修改密码或 token 过期后，前端收到 401 会清理本地 token，需要重新登录。

安全：

- 只开放 22、80、443，除非有明确需求。
- 不要把 `/opt/hermes-admin/data`、`.env`、SQLite 备份放进 Nginx 静态目录。
- 公网访问前启用 HTTPS。
