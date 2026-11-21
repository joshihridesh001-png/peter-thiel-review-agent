# Off-site backups

## What happens every night

At **23:30 IST** (after the 8 PM card, 9 PM goals and 9:30 PM nudge), `scripts/backup.sh` runs on the VPS:

1. Snapshots `founder_ops.db` with SQLite's own backup (safe while the bot is writing), then runs `PRAGMA integrity_check`. A corrupt snapshot is **never** uploaded.
2. Bundles it with `.env`, the bot's systemd service file, and the deploy launcher.
3. Uploads through an rclone **crypt** remote, which encrypts on the server before upload. Google Drive only stores scrambled names and contents.
4. Checks the uploaded size matches. If it doesn't, nothing old is deleted.
5. Deletes nightly backups older than **30 days**. Backups taken on the **1st of each month are kept forever**.

If any step fails, it posts **one "⚠️ Backup Alert" card** in `#dev-updates`. That title is on the scoring skip list, so it never counts as anyone's work.

The code is not in the backup. It's on GitHub.

> **The two encryption passwords are the only way to read these backups.** Keep them in your password manager. If the VPS dies, the copy in its rclone config dies with it.

---

## One-time setup

Do this on the VPS, except step 2, which is on your PC.

### 1. Install rclone on the VPS

Use the official installer. Ubuntu's own package is too old for Google's sign-in.

```bash
curl -fsSL https://rclone.org/install.sh | bash
```

```bash
rclone version
```

### 2. Install rclone on your PC (for the Google sign-in)

In PowerShell:

```bash
winget install Rclone.Rclone
```

### 3. Connect Google Drive (on the VPS)

```bash
rclone config
```

Answer the prompts:

| Prompt | Answer |
|---|---|
| New remote | `n` |
| name | `gdrive` |
| Storage | `drive` |
| client_id / client_secret | press Enter (leave blank) |
| scope | `drive.file` (rclone can only see files it creates) |
| service_account_file | press Enter |
| Edit advanced config | `n` |
| Use web browser to automatically authenticate | **`n`** (the server has no browser) |

It prints a line like `rclone authorize "drive" "eyJ..."`. **Run that exact line in PowerShell on your PC.** A browser opens, you sign in to Google, and PowerShell prints a token. Paste the token back into the VPS prompt.

| Prompt | Answer |
|---|---|
| Configure this as a Shared Drive | `n` |
| Keep this remote | `y` |

### 4. Add encryption on top (still in `rclone config`)

| Prompt | Answer |
|---|---|
| New remote | `n` |
| name | **`peter-backup`** (the script uses this name) |
| Storage | `crypt` |
| remote | `gdrive:peter-thiel-backups` |
| filename_encryption | `standard` |
| directory_name_encryption | `true` |
| password | `g` (generate), `1024`, then **save it in your password manager**, then `y` |
| password2 (salt) | `g`, `1024`, **save it too**, then `y` |
| Edit advanced config | `n` |
| Keep this remote | `y` |
| | `q` to quit |

### 5. Turn on the nightly timer

```bash
cp /root/peter-thiel-review-agent/scripts/systemd/peter-backup.service /root/peter-thiel-review-agent/scripts/systemd/peter-backup.timer /etc/systemd/system/
```

```bash
systemctl daemon-reload && systemctl enable --now peter-backup.timer
```

### 6. Run one backup now and check it

```bash
systemctl start peter-backup.service && journalctl -u peter-backup -n 20 --no-pager
```

It should end with `[backup] Uploaded peter-thiel-….tar.gz` and `[backup] Backup done.`

```bash
rclone lsl peter-backup:
```

This shows the readable name. In Google Drive you'll see a `peter-thiel-backups` folder with scrambled names inside. That's how it should look.

```bash
systemctl list-timers peter-backup.timer --no-pager
```

This shows the next run at 23:30 IST.

---

## Restoring

### Check a backup opens (do this once after setup, then every few months)

```bash
mkdir -p /tmp/restore && rclone copy peter-backup: /tmp/restore --max-age 2d && ls /tmp/restore
```

```bash
cd /tmp/restore && tar -xzf peter-thiel-*.tar.gz && venv=/root/peter-thiel-review-agent/venv/bin/python && $venv -c "import sqlite3; print(sqlite3.connect('founder_ops.db').execute('select count(*) from daily_scores').fetchone())"
```

A number means the backup is good. Clean up with `rm -rf /tmp/restore`.

### Put a backup back on this server

```bash
systemctl stop peter-thiel.service
```

```bash
cd /root/peter-thiel-review-agent && cp founder_ops.db founder_ops.db.before-restore && cp /tmp/restore/founder_ops.db founder_ops.db
```

```bash
systemctl start peter-thiel.service
```

### On a brand-new server

1. Clone the repo and set up the venv (`deploy_gcp.sh`).
2. Install rclone, then redo steps 3 and 4 above **using the two saved passwords** (choose `y` to type your own instead of `g`).
3. Copy the latest backup down and extract it as above. Put `founder_ops.db` and `.env` in the repo folder, and `peter-thiel.service` in `/etc/systemd/system/`.
4. `systemctl daemon-reload && systemctl enable --now peter-thiel.service`, then redo the deploy setup in `docs/DEPLOY.md`.

---

## Turning it off

```bash
systemctl disable --now peter-backup.timer
```
