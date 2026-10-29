# Deploy LiberRPA Console

This guide deploys Console on one Linux server with Docker Compose and a host HTTPS reverse proxy. The image includes PostgreSQL and all Console services. Python, Node.js, and PostgreSQL are not required on the host.

- [Requirements](#requirements)
- [Install Console](#install-console)
- [Configure HTTPS](#configure-https)
- [Verify the deployment](#verify-the-deployment)
- [Operate the instance](#operate-the-instance)
- [Back up](#back-up)
- [Upgrade](#upgrade)
- [Restore](#restore)
- [Build from source](#build-from-source)

## Requirements

- Linux on `amd64`, [Docker Engine](https://docs.docker.com/engine/install/) with the Compose plugin, and sudo access.
- [Caddy installed as a system service](https://caddyserver.com/docs/install#debian-ubuntu-raspbian).
- A working SMTP account for account verification and notifications.
- A dedicated hostname or fixed LAN IP, without a URL path prefix. Every browser, Executor, Project Manager, and Python client must trust its HTTPS certificate.
- Storage for live data, backups, and upgrade/restore work; see [Disk space](#disk-space).

Expose only the HTTPS proxy to clients. The supplied Compose file binds Console to `127.0.0.1:52100`; PostgreSQL and other internal services are not published. Keep the Docker network gateway aligned with the trusted upstream address in [deployment/haproxy.cfg](deployment/haproxy.cfg).

The default Compose paths are:

| Host path                         | Container path         | Contents                                                    |
| --------------------------------- | ---------------------- | ----------------------------------------------------------- |
| `~/liberrpa-console`            | Not mounted as a whole | `compose.yaml`, `.env`, and initial configuration files |
| `/srv/liberrpa-console`         | `/data`              | Configuration, secrets, database, and stored files          |
| `/srv/liberrpa-console-backups` | `/backup`            | Completed backups and backup work files                     |

To use another disk or location, change the bind-mount `source` paths in `compose.yaml` and the corresponding host paths in this guide. Keep `/data` and `/backup` as the container targets. Mount any separate disk before creating its data directories.

### Disk space

Plan for the following separately:

| Area              | Space to allow                                                                                                                                                                                |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docker storage    | The current and next image during upgrades, container files, and diagnostic logs.                                                                                                             |
| Live Console data | Database and uploaded-file growth. Uploads require 5 GiB of free space by default; this is a capacity check, not preallocated storage.                                                        |
| Backups           | Seven retained backups by default, plus one new backup. Each includes a database export, configuration, secrets, and independent stored-file copies. Pruning follows a successful new backup. |
| Restore work      | A restored copy alongside the existing instance until verification is complete.                                                                                                               |

If live data and backups share a disk, plan for their combined usage. Keep protected off-server copies of completed backups.

Console bind mounts do not relocate Docker's image or log storage. Account for that storage separately; see [Docker storage](https://docs.docker.com/engine/storage/containerd/).

Diagnostic log rotation allows `50m` per file and ten files per container, separate from database-backed Run logs and audit records.

## Install Console

Initialization requires a new, empty data directory. For an existing instance, use [Upgrade](#upgrade) or [Restore](#restore).

### 1. Obtain the deployment files

These examples use development version `0.1.0-dev`, Git tag `console-v0.1.0-dev`. Use matching deployment files and images; for another release, update both URLs and `CONSOLE_IMAGE` below.

```bash
mkdir -p ~/liberrpa-console
cd ~/liberrpa-console
install -d -m 700 bootstrap

curl -fL "https://raw.githubusercontent.com/HUHARED/LiberRPA/console-v0.1.0-dev/djangoConsole/compose.example.yaml" -o compose.yaml
curl -fL "https://raw.githubusercontent.com/HUHARED/LiberRPA/console-v0.1.0-dev/djangoConsole/deployment/Console.container.example.jsonc" -o bootstrap/Console.jsonc
```

Run subsequent Compose commands from this directory. For a custom image, see [Build from source](#build-from-source).

### 2. Set the image, time zone, and transfer budgets

Create `.env`:

```dotenv
CONSOLE_IMAGE=ghcr.io/huhared/liberrpa-console:0.1.0-dev
TZ=UTC
CONSOLE_UPLOAD_BANDWIDTH=800k
CONSOLE_DOWNLOAD_BANDWIDTH=800k
```

`CONSOLE_IMAGE` must include a version tag or image digest. Set `TZ` to the instance's IANA time zone. Administrative timestamps and the daily backup schedule use this value; diagnostic logs and UTC-day statistics retain their UTC basis. Host time-zone changes do not update `.env` automatically.

`CONSOLE_UPLOAD_BANDWIDTH` and `CONSOLE_DOWNLOAD_BANDWIDTH` are separate, instance-wide file-transfer budgets in **bytes per second**. `k` means KiB/s and `m` means MiB/s. Transfers share each direction's budget; it is not a limit per user. Ordinary API requests and WebSockets do not consume these file-transfer budgets.

Choose budgets below the available network capacity to leave room for other traffic. The example `800k` is about 6.55 Mbps in each direction; adjust it for the deployment. If inbound and outbound traffic share one provider limit, divide that capacity between the budgets. An omitted variable defaults to `10m` (about 83.9 Mbps); empty values are invalid.

### 3. Set the data paths and create the directories

Review the two bind-mount sources in `compose.yaml`, then create the selected directories. For the defaults:

```bash
sudo install -d -m 755 /srv/liberrpa-console /srv/liberrpa-console-backups
```

The data directory must be empty; the backup directory need not be. Initialization sets ownership and permissions. With `create_host_path: false`, missing bind-mount sources are errors.

### 4. Configure the instance and SMTP password

Edit `bootstrap/Console.jsonc`:

| Setting          | Public-domain example           | LAN example              |
| ---------------- | ------------------------------- | ------------------------ |
| `consoleUrl`   | `https://console.example.com` | `https://192.168.1.50` |
| `allowedHosts` | `["console.example.com"]`     | `["192.168.1.50"]`     |

Set `supportEmail` and the SMTP host, port, security, username, and sender using the provider's settings. Keep `debug` false.

Keep the supplied database, storage, secret-file, and `fileTransferProxy` settings, which refer to paths and services inside the image. Leave `limits` as `{}` unless overriding a default from `LimitsConfig` in [backend/console_project/config.py](backend/console_project/config.py).

Leave `backup` as `null` for initialization, then configure it under [Back up](#back-up).

Create a protected SMTP password file:

```bash
touch bootstrap/smtp-password.txt
chmod 600 bootstrap/Console.jsonc bootstrap/smtp-password.txt
```

Enter the SMTP password as one line without quotes.

### 5. Check the configuration and pull the image

```bash
sudo docker compose config
sudo docker compose pull console
```

Check the resolved image, environment, and mount paths. Continue after the pull succeeds.

### 6. Initialize the instance

Initialization creates the database, applies migrations, generates secrets, and creates the platform administrator `admin`.

Run from an interactive terminal:

```bash
sudo docker compose run -d --rm --no-deps --pull never --interactive --no-tty=false --name liberrpa-console-initialize -v "$PWD/bootstrap:/bootstrap:ro" console initialize --config /bootstrap/Console.jsonc --smtp-password-file /bootstrap/smtp-password.txt && sudo docker attach liberrpa-console-initialize
```

Enter the password twice; input is hidden. Continue only after:

```text
Platform administrator 'admin' created.
Console initialized. Keep /data and its secrets together when backing up or moving the instance.
```

If attachment misses a prompt, inspect the temporary container's logs and reconnect with `sudo docker attach liberrpa-console-initialize`. On failure, inspect the preserved data before retrying; do not initialize a partially created instance again.

### 7. Start the service

```bash
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
sudo docker compose ps
```

The active configuration is `/srv/liberrpa-console/config/Console.jsonc`. After successful initialization, remove the bootstrap copies:

```bash
rm bootstrap/smtp-password.txt bootstrap/Console.jsonc
rmdir bootstrap
```

## Configure HTTPS

Choose a publicly trusted certificate or the LAN internal CA branch. Windows internal CA setup applies only to the latter. Cloudflare is an optional extension to the public-certificate setup. Add the selected site to `/etc/caddy/Caddyfile` while retaining other sites.

### Publicly trusted certificate

Use the hostname from `consoleUrl`, with DNS and network access configured for [Caddy&#39;s automatic HTTPS](https://caddyserver.com/docs/automatic-https):

```caddyfile
console.example.com {
    reverse_proxy 127.0.0.1:52100
}
```

Caddy obtains and renews the certificate. Continue with [Apply the configuration](#apply-the-configuration).

### LAN IP with an internal CA

Use the same fixed IP configured in `consoleUrl` and `allowedHosts`:

```caddyfile
https://192.168.1.50 {
    tls internal
    reverse_proxy 127.0.0.1:52100
}
```

Apply this configuration using [Apply the configuration](#apply-the-configuration), then configure certificate trust on every client. Windows, Node.js, and Python may use different trust stores.

#### Windows client trust

With the standard Caddy system service, export its public root certificate on the server:

```bash
sudo install -m 0644 /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt "$PWD/console-root.crt"
sha256sum console-root.crt
```

Transfer `console-root.crt` to each client through an authenticated channel. Never distribute `root.key`. In PowerShell, verify the hash against the server output:

```powershell
certutil -hashfile .\console-root.crt SHA256
```

These commands are for a new client setup. Preserve existing custom roots in certificate files and CA environment variables when adding this CA.

Install the certificate for the Windows user who runs LiberRPA:

```powershell
$certificateDirectory = Join-Path $env:LOCALAPPDATA 'LiberRPA\certificates'
New-Item -ItemType Directory -Force $certificateDirectory | Out-Null
$caFile = Join-Path $certificateDirectory 'console-root.crt'
Copy-Item '.\console-root.crt' $caFile
certutil -user -addstore Root $caFile
```

`NODE_EXTRA_CA_CERTS` extends Node.js's built-in trust. Requests' `REQUESTS_CA_BUNDLE` replaces its default bundle, so include the public roots too. Set `$rpaPython` to the RPA environment's executable:

```powershell
$rpaPython = 'C:\path\to\your-rpa-environment\python.exe'
$requestsBundle = Join-Path $certificateDirectory 'requests-ca-bundle.pem'
$publicBundle = & $rpaPython -m certifi

$bundleBytes = [IO.File]::ReadAllBytes($publicBundle) + [byte[]]@(10) + [IO.File]::ReadAllBytes($caFile)
[IO.File]::WriteAllBytes($requestsBundle, [byte[]]$bundleBytes)

[Environment]::SetEnvironmentVariable('NODE_EXTRA_CA_CERTS', $caFile, 'User')
[Environment]::SetEnvironmentVariable('REQUESTS_CA_BUNDLE', $requestsBundle, 'User')
$env:NODE_EXTRA_CA_CERTS = $caFile
$env:REQUESTS_CA_BUNDLE = $requestsBundle
```

Fully exit Executor, including its tray process, and all VS Code windows; restart them with the new environment. Restart Python processes too. Changing variables in an existing VS Code terminal does not update its extension host.

Import the CA into browsers with separate trust stores. Repeat for other client accounts or hosts. Retain the certificate files and rebuild the Requests bundle when its public roots or the internal CA change. See the [Node.js](https://nodejs.org/api/cli.html#node_extra_ca_certsfile), [Requests](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification), and [VS Code](https://code.visualstudio.com/docs/setup/network#_ssl-certificates) documentation for other environments.

### Cloudflare proxy (optional)

Use a valid origin certificate and [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/) encryption. Configure Caddy to accept client addresses only from Cloudflare and forward one address to Console. Replace the example hostname and merge global options with any existing global block:

```caddyfile
{
    servers {
        trusted_proxies static 173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32
        client_ip_headers CF-Connecting-IP
    }
}

console.example.com {
    reverse_proxy 127.0.0.1:52100 {
        header_up X-Forwarded-For {client_ip}
    }
}
```

Keep trusted ranges aligned with Cloudflare's [IPv4](https://www.cloudflare.com/ips-v4) and [IPv6](https://www.cloudflare.com/ips-v6) lists. Keep visitor-IP headers enabled and do not enable Pseudo IPv4's `Overwrite Headers` mode. See [Caddy&#39;s trusted proxy options](https://caddyserver.com/docs/caddyfile/options#trusted-proxies).

Keep `/api/` uncached and free of browser-only challenges. Verify Executor and Project Manager connections and representative uploads and downloads through the proxy; Cloudflare's request-size and timeout limits still apply. Restrict origin web access separately if clients must not bypass Cloudflare.

### Apply the configuration

```bash
sudo -u caddy -H caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

Caddy supports streaming transfers and WebSockets. An alternative proxy must preserve these behaviors and send one verified client IP in `X-Forwarded-For`, not arbitrary client-supplied values.

## Verify the deployment

```bash
sudo docker compose exec --user liberrpa console python /app/backend/manage.py instance_status
sudo docker compose exec console supervisorctl -c /app/deployment/supervisord.conf status
```

Container health checks the core service, not every background task or integration. Allow startup recovery to finish and check individual services with `instance_status`. Backup health is `Unknown` until configured.

Verify the following before opening the service to users:

- Open the configured HTTPS URL without a certificate warning.
- Sign in at `/platform/sign-in` as `admin` and check the audit log. Ordinary accounts use `/sign-in`.
- Complete an email-based account operation and confirm delivery.
- Connect Executor and Project Manager and perform a Console operation from an RPA flow, including Python certificate validation for internal CA deployments.
- Complete a manual backup and rehearse restoration.

## Operate the instance

### Logs

Container diagnostic logs use standard output/error:

```bash
sudo docker compose logs --tail 200 console
sudo docker compose logs --since 30m --timestamps console
sudo docker compose logs -f --tail 100 console
```

Export diagnostics or inspect the HTTPS proxy:

```bash
sudo docker compose logs --no-color --since 24h console > console-diagnostics.log
sudo journalctl -u caddy --since "30 minutes ago"
```

The `local` logging driver rotates logs at `50m` per file with up to ten files per container. Retention depends on volume, not elapsed days. Export needed diagnostics before removing or recreating a container. Do not edit Docker's internal log files.

Diagnostic timestamps are UTC. Audit records and Run logs are stored separately in the database and follow their own retention settings.

### Configuration changes

Edit the active `Console.jsonc` or the secret files it references, then restart:

```bash
sudo docker compose restart console
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
```

Changes to `.env` or `compose.yaml` require recreation, not just restart:

```bash
sudo docker compose config
sudo docker compose up -d --no-build --pull never --force-recreate --wait --wait-timeout 120
```

Persistent data remains in the bind mounts. Check `instance_status` after either operation.

### Maintenance mode

```bash
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance enter
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance status
```

Maintenance pauses new jobs, schedule triggers, and start permissions. Existing Runs and valid reports can continue. It is not an access restriction or complete write freeze, and it survives restarts. Review reported jobs and allow run-control recovery to finish before resuming:

```bash
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance resume
```

## Back up

Replace `"backup": null` in `/srv/liberrpa-console/config/Console.jsonc` with your settings:

```jsonc
"backup": {
  "location": "/backup",
  "dailyTime": "03:00",
  "notificationEmail": "admin@example.com"
}
```

The schedule uses `TZ`. Notifications report backup failure and recovery. Default retention is seven successful backups, counting manual and scheduled backups together.

Apply the configuration and check readiness:

```bash
sudo docker compose restart console
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
sudo docker compose exec --user liberrpa console python /app/backend/manage.py backup status
```

When `Can request` is `yes`:

```bash
sudo docker compose exec --user liberrpa console python /app/backend/manage.py backup request
sudo docker compose exec --user liberrpa console python /app/backend/manage.py backup status
```

`request` queues work; it does not wait for completion. Record the returned ID and check until that backup reports `Succeeded`.

A completed backup is a UUID-named directory without hyphens under the host backup path. Preserve the whole directory: `manifest.json`, `database.dump`, configuration, secrets, and stored files. An unfinished `.partial` directory is not a usable backup. Keep protected off-server copies and record the matching image tag/digest.

Console backups exclude host deployment files. Back up `compose.yaml`, `.env`, `/etc/caddy/Caddyfile`, and Caddy's data directory `/var/lib/caddy/.local/share/caddy` separately. These include private keys; preserving an internal CA avoids replacing trust on every client after server loss.

## Upgrade

Review the target release's notes and deployment files while preserving site settings. Pull the image before the outage:

```bash
newImage="ghcr.io/huhared/liberrpa-console:<new-version>"
sudo docker pull "$newImage"
```

Leave `.env` on the running version. Enter maintenance, inspect active work, allow Runs to finish where possible, and complete a fresh backup. Stopping Console interrupts control but does not reliably stop flows already running on Executors.

Stop Console, then update `CONSOLE_IMAGE` and any required Compose settings:

```bash
sudo docker compose stop console
```

Apply the migrations shipped with the release:

```bash
sudo docker compose config
sudo docker compose run --rm --no-deps --pull never console offline python /app/backend/manage.py migrate --noinput
```

On failure, stop and inspect the error. Do not run `makemigrations` or repeat initialization on the server.

After migration succeeds:

```bash
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
sudo docker compose exec --user liberrpa console python /app/backend/manage.py instance_status
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance status
```

After recovery and review, run `maintenance resume` and verify the application. Ordinary startup checks migrations but does not apply them.

This procedure assumes the same PostgreSQL major version; otherwise follow the release's database upgrade procedure. After schema changes, rollback requires the pre-upgrade backup and its matching image, not just an older image tag.

## Restore

Restoration replaces the whole instance. It does not undo RPA effects in external systems. Restore into a separate directory and retain the current data until verification.

### 1. Select the backup and matching image

Use the exact Console version recorded in `manifest.json`; restoration also checks Django's major/minor version. Prefer the original image digest. Restore an older backup with its matching image before upgrading it.

```bash
backupDir="/srv/liberrpa-console-backups/<completed-backup-directory>"
restoreDir=/srv/liberrpa-console-restore
restoreImage="ghcr.io/huhared/liberrpa-console:<backup-version>"
sudo docker pull "$restoreImage"
```

Replace placeholders. `restoreDir` must not exist and must be separate from the backup. Allow space for existing and restored data together.

Preserve transferred backup permissions and ownership for container user `liberrpa` (UID 1000). If ownership was lost, correct the local working copy with `sudo chown -R 1000 "$backupDir"`.

Defaults are encoding `UTF8`, collation `C.UTF-8`, and ctype `C.UTF-8`. For other values, pass the manifest's `database_encoding`, `database_collation`, and `database_ctype` to `prepare-restore` using `--database-encoding`, `--database-collation`, and `--database-ctype`.

### 2. Restore offline

Close the public entry point and stop Console. The following assumes Caddy serves only this instance; otherwise disable just the Console site.

```bash
sudo systemctl stop caddy
sudo docker compose stop console
sudo mkdir "$restoreDir"
```

Create an empty recovery database:

```bash
sudo docker run --rm --pull never --network none --tmpfs /run --env-file .env --mount "type=bind,source=$restoreDir,target=/data" --mount "type=bind,source=$backupDir,target=/restore-source,readonly" "$restoreImage" prepare-restore --password-file /restore-source/config/secrets/database-password.txt
```

Then restore the backup:

```bash
sudo docker run --rm --pull never --network none --tmpfs /run --env-file .env --mount "type=bind,source=$restoreDir,target=/data" --mount "type=bind,source=$backupDir,target=/restore-source,readonly" "$restoreImage" offline python /app/restore_console.py /restore-source --target /data/config --database-host 127.0.0.1 --database-port 5432 --database-name liberrpa_console --database-user liberrpa_console --password-file /restore-source/config/secrets/database-password.txt
```

Continue only after `Restore completed in maintenance mode`. On failure, preserve the existing data and inspect the error; do not bypass markers or start a partially restored directory.

### 3. Switch to the restored data

Set `CONSOLE_IMAGE` to the restored image. Review `$restoreDir/config/Console.jsonc`, including its URL, SMTP settings, and permissions. Restoration rewrites secret and storage paths under `/data/config/secrets` and `/data/config/storage`; keep those paths.

Make sure `/srv/liberrpa-console-before-restore` does not already exist. Switch directories, keeping the previous instance:

```bash
sudo mv --no-target-directory -- /srv/liberrpa-console /srv/liberrpa-console-before-restore && sudo mv --no-target-directory -- "$restoreDir" /srv/liberrpa-console
```

Recreate the container so its bind mount uses the new directory:

```bash
sudo docker compose up -d --no-build --pull never --force-recreate --wait --wait-timeout 120
sudo docker compose exec --user liberrpa console python /app/backend/manage.py instance_status
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance status
```

The restored instance starts in maintenance. Sessions and API keys are revoked; clients must authenticate again and API keys must be replaced. Pending email is not replayed. Review jobs needing attention before resuming; restrict browser access to administrators if needed for this review.

After recovery and review:

```bash
sudo docker compose exec --user liberrpa console python /app/backend/manage.py maintenance resume
sudo systemctl start caddy
```

If Caddy stayed running for other sites, re-enable the Console block and run `sudo systemctl reload caddy` instead.

Backups are disabled after restoration. Re-enable them and complete a new manual backup. Old backup directories remain on disk but are untracked by the restored backup history and retention. Retain them and the previous data until the restored service and its new backup are verified; remove only copies no longer needed.

## Build from source

For custom or unpublished versions, use a complete checkout with Django migrations and frontend assets, including `frontend/public/LiberRPA_icon_v3_color_Console.svg`. From `djangoConsole`:

```bash
sudo docker build --progress=plain -t liberrpa-console:local .
```

The build checks for model changes missing migrations. Resolve failures in development, review and commit migrations, then rebuild.

Use that checkout's `compose.example.yaml` and `deployment/Console.container.example.jsonc` as the deployment templates. Set `CONSOLE_IMAGE=liberrpa-console:local` and follow [Install Console](#install-console), skipping downloads and the image pull. Retain the built image for restoring its backups; rebuilding changed source under the same tag does not preserve the original version.
