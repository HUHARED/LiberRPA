# Deploy LiberRPA Console

This guide covers a single Linux server using Docker Compose, with Caddy on the host providing HTTPS. Use a public domain or a fixed LAN IP address. The Console image includes PostgreSQL and all application services; Python, Node.js, and PostgreSQL do not need to be installed on the host.

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
- A public domain pointing to this server, or a fixed LAN IP. Clients must trust the HTTPS certificate.
- TCP ports 80 and 443 accessible to the intended clients through the host and provider firewalls. Keep port 52100 bound to loopback as supplied; do not publish PostgreSQL or other internal ports.
- Enough disk space for the database, stored files, and retained backups. Capacity depends on uploaded packages, run files, and usage.

Use a dedicated HTTPS hostname or IP, without a URL path prefix. The examples assume Caddy receives client connections directly.

The default host directories are:

| Host path | Container path | Contents |
| --- | --- | --- |
| `/srv/liberrpa-console` | `/data` | Configuration, secrets, database, and stored files |
| `/srv/liberrpa-console-backups` | `/backup` | Completed backups and backup work files |

To use a separate data disk, change the bind-mount **source** paths in `compose.yaml` and use those paths throughout this guide. Keep the container targets unchanged. Ensure the disk is mounted before starting Console. A backup on the same server still needs an off-server copy.

## Install Console

### 1. Obtain the deployment files and image

Choose a published version from the [repository](https://github.com/HUHARED/LiberRPA). Use its versioned image and matching `console-v<version>` Git tag. Do not use a moving tag for a production deployment. An image digest may also be used in `CONSOLE_IMAGE`.

Run the Linux commands in this guide from one deployment directory:

```bash
mkdir -p ~/liberrpa-console
cd ~/liberrpa-console
install -d -m 700 bootstrap

CONSOLE_VERSION="<published-version>"
CONSOLE_TAG="console-v${CONSOLE_VERSION}"

curl -fL "https://raw.githubusercontent.com/HUHARED/LiberRPA/${CONSOLE_TAG}/djangoConsole/compose.example.yaml" \
  -o compose.yaml
curl -fL "https://raw.githubusercontent.com/HUHARED/LiberRPA/${CONSOLE_TAG}/djangoConsole/deployment/Console.container.example.jsonc" \
  -o bootstrap/Console.jsonc

printf 'CONSOLE_IMAGE=ghcr.io/huhared/liberrpa-console:%s\nTZ=%s\n' \
  "$CONSOLE_VERSION" "$(timedatectl show --property=Timezone --value)" > .env
```

Replace `<published-version>` before running the commands. If using your own build, follow [Build from source](#build-from-source) and set `CONSOLE_IMAGE` to that local image instead.

Review `.env`. `TZ` must be an IANA time zone such as `Asia/Taipei` or `Europe/London`. It controls administrative time displays and the daily backup schedule. It is copied from the host at setup; later host time-zone changes do not automatically update this file.

### 2. Set file-transfer budgets

Add these settings to `.env`, choosing values below the available link capacity:

```dotenv
CONSOLE_UPLOAD_BANDWIDTH=800k
CONSOLE_DOWNLOAD_BANDWIDTH=800k
```

These are separate, instance-wide file-transfer budgets in **bytes per second**. `k` means KiB/s and `m` means MiB/s. Transfers share each direction's budget; it is not a limit per user. Ordinary API requests and WebSockets do not consume these file-transfer budgets.

The example `800k` is about 6.55 Mbps and leaves some headroom on a 10 Mbps link in each direction. If your provider imposes one combined inbound/outbound limit, divide that total between the two budgets. Use measured capacity where possible. Omitting either variable uses `10m` for that direction, which is about 83.9 Mbps. Do not leave a variable empty.

### 3. Configure the instance

Edit `bootstrap/Console.jsonc`:

| Setting | Public-domain example | LAN example |
| --- | --- | --- |
| `consoleUrl` | `https://console.example.com` | `https://192.168.1.50` |
| `allowedHosts` | `["console.example.com"]` | `["192.168.1.50"]` |

Set `supportEmail` and the SMTP host, port, security, username, and sender. Use the provider's settings, commonly `ssl` with port 465 or `starttls` with port 587. Keep `debug` false.

Keep the supplied database, storage, secret-file, and `fileTransferProxy` settings. They refer to services and paths inside the image. Keep `limits` as `{}` unless you need specific overrides; available fields and defaults are defined by `LimitsConfig` in [backend/console_project/config.py](backend/console_project/config.py).

Leave `backup` as `null` for initialization, then configure it under [Back up](#back-up).

Create a protected file and enter the SMTP password as a single line using your editor:

```bash
install -m 600 /dev/null bootstrap/smtp-password.txt
chmod 600 bootstrap/Console.jsonc
```

Create the persistent directories, then validate Compose and pull the image:

```bash
sudo install -d /srv/liberrpa-console /srv/liberrpa-console-backups
sudo docker compose config --quiet
sudo docker compose pull console
```

The data directory must be empty for first initialization. Do not run initialization against an existing instance.

### 4. Initialize and start

Run initialization in an interactive terminal. It creates the database, applies the supplied migrations, generates secrets, and asks twice for the platform administrator password. The administrator login is `admin`.

```bash
sudo docker compose run --rm --no-deps --pull never \
  -v "$PWD/bootstrap:/bootstrap:ro" \
  console initialize \
  --config /bootstrap/Console.jsonc \
  --smtp-password-file /bootstrap/smtp-password.txt
```

Only after `Console initialized` appears, start the service:

```bash
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
sudo docker compose ps
```

The active configuration is now `/srv/liberrpa-console/config/Console.jsonc`. Edit that file for later changes. The bootstrap copies are no longer used; remove them after verifying initialization:

```bash
rm bootstrap/smtp-password.txt bootstrap/Console.jsonc
rmdir bootstrap
```

## Configure HTTPS

Choose one of the following Caddy configurations in `/etc/caddy/Caddyfile`. If Caddy already serves other sites, add the Console block without replacing those sites.

### Public domain

Point the domain's DNS records to this server. Any published IPv6 record must also work. For this direct-Caddy setup, use DNS-only records if your DNS provider offers an HTTP proxy feature.

```caddyfile
console.example.com {
    reverse_proxy 127.0.0.1:52100
}
```

Caddy obtains and renews a publicly trusted certificate and redirects HTTP to HTTPS. Its certificate validation requires the DNS and firewall configuration described above.

### LAN IP with an internal CA

Use the same fixed IP configured in `consoleUrl` and `allowedHosts`:

```caddyfile
https://192.168.1.50 {
    tls internal
    reverse_proxy 127.0.0.1:52100
}
```

Caddy issues the server certificate from its internal certificate authority (CA). Each client must trust that CA; a browser warning is not a successful deployment.

### Apply the configuration

```bash
sudo -u caddy -H caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

The default Caddy reverse proxy supports streaming file transfers and WebSockets and supplies the client address required by Console. No upload/download buffering settings are needed. If replacing Caddy, preserve these behaviors and send one verified client IP in `X-Forwarded-For`; do not forward arbitrary client-supplied values.

### Trust the internal CA on Windows

Skip this section for a publicly trusted certificate.

With the standard Caddy system service, export its public root certificate on the server:

```bash
sudo install -m 0644 \
  /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt \
  "$PWD/console-root.crt"
sha256sum console-root.crt
```

Copy `console-root.crt` to each Windows client through your existing SSH/SCP connection. Never distribute `root.key`. In PowerShell, from the directory containing the downloaded certificate:

```powershell
certutil -hashfile .\console-root.crt SHA256
```

Confirm that the file hash matches the server output. The commands below assume an initial setup. If these files or `NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, or `CURL_CA_BUNDLE` already contain custom roots, preserve those roots when adding this CA instead of overwriting them.

Install the certificate for the Windows user who runs LiberRPA:

```powershell
$certificateDirectory = Join-Path $env:LOCALAPPDATA 'LiberRPA\certificates'
New-Item -ItemType Directory -Force $certificateDirectory | Out-Null
$caFile = Join-Path $certificateDirectory 'console-root.crt'
Copy-Item '.\console-root.crt' $caFile
certutil -user -addstore Root $caFile
```

Node.js and Python also need the certificate. `NODE_EXTRA_CA_CERTS` adds roots to Node.js's built-in trust. `REQUESTS_CA_BUNDLE` replaces Python Requests' default bundle, so its file must include the public roots too.

Replace `$rpaPython` with the Python executable used by your RPA environment:

```powershell
$rpaPython = 'C:\path\to\your-rpa-environment\python.exe'
$requestsBundle = Join-Path $certificateDirectory 'requests-ca-bundle.pem'
$publicBundle = & $rpaPython -m certifi

$bundleBytes = (
    [IO.File]::ReadAllBytes($publicBundle) +
    [byte[]]@(10) +
    [IO.File]::ReadAllBytes($caFile)
)
[IO.File]::WriteAllBytes($requestsBundle, [byte[]]$bundleBytes)

[Environment]::SetEnvironmentVariable('NODE_EXTRA_CA_CERTS', $caFile, 'User')
[Environment]::SetEnvironmentVariable('REQUESTS_CA_BUNDLE', $requestsBundle, 'User')
$env:NODE_EXTRA_CA_CERTS = $caFile
$env:REQUESTS_CA_BUNDLE = $requestsBundle
```

Fully exit Executor, including its tray process, and close all VS Code windows. Relaunch them from this PowerShell session, or from Windows after saving the user environment variables. Restart existing Python processes. Setting variables only in an already-running VS Code terminal does not update its extension host.

If a browser uses a separate certificate store, import the same CA into that store. Configure other Windows accounts or remote hosts separately when they run clients. Keep the certificate files in place and rebuild the Python bundle when its public roots or the internal CA change.

See the official [Node.js](https://nodejs.org/api/cli.html#node_extra_ca_certsfile), [Requests](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification), and [VS Code](https://code.visualstudio.com/docs/setup/network#_ssl-certificates) certificate documentation for additional environments.

## Verify the deployment

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py instance_status
sudo docker compose exec console \
  supervisorctl -c /app/deployment/supervisord.conf status
```

A healthy container confirms the core service is reachable. Background services may still be recovering after startup. Wait for the scheduler to become healthy and use `instance_status` to check the individual services. Backup health remains `Unknown` until backups are configured.

Verify the following before opening the service to users:

- Open the configured HTTPS URL without a certificate warning.
- Sign in at `/platform/sign-in` as `admin` and check the audit log. Ordinary accounts use `/sign-in`.
- Complete an email-based account operation and confirm delivery. A healthy email worker alone does not prove SMTP delivery works.
- Connect Executor and Project Manager. For an internal CA, also perform a Console operation from an RPA flow to verify Python's trust configuration.
- Enable backups, complete a manual backup, and rehearse a restore before relying on the instance.

## Operate the instance

### Logs

Production diagnostic logs go to container standard output/error, rather than the development `.local/logs` directory:

```bash
sudo docker compose logs --tail 200 console
sudo docker compose logs --since 30m --timestamps console
sudo docker compose logs -f --tail 100 console
```

Use Ctrl+C to stop following logs; this does not stop Console. To export diagnostics or inspect the HTTPS proxy:

```bash
sudo docker compose logs --no-color --since 24h console > console-diagnostics.log
sudo journalctl -u caddy --since "30 minutes ago"
```

Compose explicitly uses Docker's `local` logging driver with `max-size: 50m` and `max-file: 10` per container. Retention is size-based, not a number of days; old files rotate out. Removing a container also removes its diagnostic log history, so export logs before recreating it when needed. Do not read or edit Docker's internal log files directly.

Application diagnostic timestamps remain UTC. Administrative commands use `TZ`. Audit records and Run logs are database records, separate from Docker diagnostics.

### Configuration changes

Edit the active `Console.jsonc` or the secret files it references, then restart:

```bash
sudo docker compose restart console
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
```

Once the container is healthy, check the background services:

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py instance_status
```

Changes to `.env` or `compose.yaml` require recreation, not just restart:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --no-build --pull never --force-recreate \
  --wait --wait-timeout 120
```

Persistent data remains in the host bind mounts. Do not change the supplied Docker subnet/gateway independently of the trusted upstream addresses in `deployment/haproxy.cfg`.

### Maintenance mode

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance enter
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance status
```

Maintenance pauses new jobs, schedule triggers, and start permissions. Existing Runs and valid reports can continue. It is not a complete write freeze or an access restriction. The state survives container restarts.

Resume only after checking the status and resolving any reported jobs needing review:

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance resume
```

If the command reports that run control is recovering, wait and check the status again.

## Back up

Replace `"backup": null` in the active configuration with your settings:

```json
"backup": {
  "location": "/backup",
  "dailyTime": "03:00",
  "notificationEmail": "admin@example.com"
}
```

The time uses the instance's `TZ`. `notificationEmail` receives backup failure and recovery notifications. The default retention limit is seven successful backups, including manual and scheduled backups, rather than seven days.

Restart to load the settings and wait for the container to become healthy:

```bash
sudo docker compose restart console
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
```

Check that the backup worker is ready and `Can request` is `yes`:

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py backup status
```

Then request a backup and check its progress:

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py backup request
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py backup status
```

`backup request` queues work; it does not wait for completion. Record the returned ID and check until **that backup** reports `Succeeded`. The worker must be ready before a request can be accepted.

A completed backup is a directory under the host backup path named with its UUID without hyphens. Keep the whole directory: `manifest.json`, `database.dump`, configuration, secrets, and stored files belong together. Do not use an unfinished `.partial` directory. Copy completed backups off the server and restrict access because they contain credentials and encryption keys.

Record the deployed image tag/digest alongside your backups. Also back up `compose.yaml`, `.env`, `/etc/caddy/Caddyfile`, and Caddy's data directory `/var/lib/caddy/.local/share/caddy`. These host files are outside Console's backup. The Caddy data includes private keys; retaining the internal CA avoids having to establish a new CA on every client after server replacement.

## Upgrade

Read the release notes and obtain the target version's deployment files. Review changes while preserving your host paths and settings. Pull the new image before the outage:

```bash
newImage="ghcr.io/huhared/liberrpa-console:<new-version>"
sudo docker pull "$newImage"
```

Keep `.env` pointing to the running version for now. Enter maintenance and inspect active work using the commands above. Allow active Runs to finish where possible, then choose an outage window. Stopping Console interrupts communication and control; it does not reliably stop flows already running on Executors. Request a backup and confirm that the new backup succeeded before continuing.

Stop Console, then change `CONSOLE_IMAGE` in `.env` to the new image. Apply only the migrations shipped with that release:

```bash
sudo docker compose stop console
```

After editing `.env`:

```bash
sudo docker compose config --quiet
sudo docker compose run --rm --no-deps --pull never console \
  offline python /app/backend/manage.py migrate --noinput
```

If migration fails, stop here and inspect the error. Do not run `makemigrations` on the server or repeat initialization.

After migration succeeds:

```bash
sudo docker compose up -d --no-build --pull never --wait --wait-timeout 120
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py instance_status
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance status
```

Wait for recovery to finish, review the status, then run `maintenance resume` and verify the application. Ordinary startup checks migrations but does not apply them automatically.

This procedure assumes the same PostgreSQL major version. A release changing that version needs its own database upgrade procedure. After schema changes, rollback means restoring the pre-upgrade backup with its matching image; switching only the image tag is not a database rollback.

## Restore

A restore replaces the whole instance with the backup state. It does not undo effects that RPA flows have already made in external systems. Restore into a separate directory and keep the current data until the replacement is verified.

### 1. Select the backup and matching image

Use the exact Console version recorded in `manifest.json`; the restore also checks the Django major/minor version. Prefer the original image digest. To upgrade an old backup, restore it with its matching image first, then follow [Upgrade](#upgrade).

```bash
backupDir="/srv/liberrpa-console-backups/<completed-backup-directory>"
restoreDir=/srv/liberrpa-console-restore
restoreImage="ghcr.io/huhared/liberrpa-console:<backup-version>"
sudo docker pull "$restoreImage"
```

Replace the placeholders. `restoreDir` must be a new directory, separate from the backup. Check that the disk has room for the old data and restored copy together.

When copying a backup from another machine, preserve ownership and permissions so the container's `liberrpa` user (UID 1000) can read it. If ownership was lost, correct the local working copy with `sudo chown -R 1000 "$backupDir"`. This is unnecessary for backups created by this instance.

The commands below assume the container defaults `UTF8`, `C.UTF-8`, and `C.UTF-8` for database encoding, collation, and ctype. For a backup with other values, pass its `database_encoding`, `database_collation`, and `database_ctype` values to `prepare-restore` using `--database-encoding`, `--database-collation`, and `--database-ctype`.

### 2. Restore offline

Close the public entry point and stop Console. The following assumes Caddy serves only this instance; otherwise disable just the Console site.

```bash
sudo systemctl stop caddy
sudo docker compose stop console
sudo mkdir "$restoreDir"
```

Create an empty recovery database:

```bash
sudo docker run --rm --pull never \
  --network none --tmpfs /run --env-file .env \
  --mount "type=bind,source=$restoreDir,target=/data" \
  --mount "type=bind,source=$backupDir,target=/restore-source,readonly" \
  "$restoreImage" prepare-restore \
  --password-file /restore-source/config/secrets/database-password.txt
```

Then restore the backup:

```bash
sudo docker run --rm --pull never \
  --network none --tmpfs /run --env-file .env \
  --mount "type=bind,source=$restoreDir,target=/data" \
  --mount "type=bind,source=$backupDir,target=/restore-source,readonly" \
  "$restoreImage" \
  offline python /app/restore_console.py /restore-source \
  --target /data/config \
  --database-host 127.0.0.1 --database-port 5432 \
  --database-name liberrpa_console --database-user liberrpa_console \
  --password-file /restore-source/config/secrets/database-password.txt
```

Continue only after `Restore completed in maintenance mode` appears. On failure, keep the current instance untouched and inspect the error; do not bypass restore markers or start a partially restored directory.

### 3. Switch to the restored data

Set `CONSOLE_IMAGE` in `.env` to `restoreImage`'s value. Review the restored configuration at `$restoreDir/config/Console.jsonc`, including its URL, SMTP settings, and permissions.

The restore rewrites paths: secrets and stored files are now under `/data/config/secrets` and `/data/config/storage`. Use the paths in the restored configuration rather than moving them back to the initial layout.

Make sure `/srv/liberrpa-console-before-restore` does not already exist. Switch directories, keeping the previous instance:

```bash
sudo mv -T /srv/liberrpa-console /srv/liberrpa-console-before-restore &&
sudo mv -T "$restoreDir" /srv/liberrpa-console
```

Recreate the container so its bind mount uses the new directory:

```bash
sudo docker compose up -d --no-build --pull never --force-recreate \
  --wait --wait-timeout 120
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py instance_status
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance status
```

The restored instance starts in maintenance. Sessions and API keys are revoked; users and clients need to authenticate again, and API keys must be replaced. Pending email is not replayed. Review jobs needing attention before resuming. If browser access is needed for this review, restrict the HTTPS entry to administrators until it is complete.

After recovery and review:

```bash
sudo docker compose exec --user liberrpa console \
  python /app/backend/manage.py maintenance resume
sudo systemctl start caddy
```

If Caddy stayed running for other sites, re-enable the Console block and run `sudo systemctl reload caddy` instead.

Backups are disabled after restore. Re-enable them using [Back up](#back-up) and complete a new manual backup. Old backup directories remain on disk but are no longer tracked by the restored instance's backup history or retention. Keep them and the previous data directory until you have verified the restored service and its new backup, then remove only the copies you no longer need.

## Build from source

Use this option for local changes or an unpublished version. Published images avoid the build workload on the deployment host and let all operators use the same built artifact.

Use a complete checkout of the desired source version. It must include Django migration files and frontend assets, including `frontend/public/LiberRPA_icon_v3_color_Console.svg`. From its `djangoConsole` directory:

```bash
sudo docker build --progress=plain -t liberrpa-console:local .
```

The image build checks for model changes missing migrations. If that check fails, generate and review migrations in the development environment, commit them, and build again. Do not generate migrations inside a deployed instance.

Copy `compose.example.yaml` to your deployment directory as `compose.yaml`, and `deployment/Console.container.example.jsonc` as `bootstrap/Console.jsonc`. Set `CONSOLE_IMAGE=liberrpa-console:local` in `.env`, supply `TZ` and transfer budgets, and follow the same installation steps, skipping the image pull. Retain this image for restoring backups made with it; rebuilding changed source under the same tag is not a reliable way to recover that version.
