# Deploys

## How it works

1. **Every pull request and push** runs the tests on GitHub (`.github/workflows/ci.yml`).
2. **When something merges to `main` and the tests pass**, GitHub logs into the VPS. The key there can only run `/root/bin/peter-deploy` (a copy of `scripts/deploy-launcher.sh`), which fetches `main` and runs the **newest** `scripts/deploy.sh` from it. A fix to `deploy.sh` therefore takes effect on the very next deploy.
3. `deploy.sh` backs up the database, pulls, installs, restarts, and checks the bot came back online. If it didn't, it rolls back to the previous commit.

You see the result in the **Actions** tab on GitHub. A red ✗ on a deploy means the server was **not** changed, or was rolled back. GitHub emails you when that happens.

### When a deploy stops without changing anything

| Message | Why | What to do |
|---|---|---|
| "Quiet hours" | 19:10–22:05 IST daily, or 09:55–11:05 IST on the 1st. A restart then would post the 7:15 check, 8 PM card, 9 PM goals, or monthly equity twice. | After 22:05 IST: Actions → **CI and Deploy** → **Run workflow** on `main`. |
| "Files were edited by hand on the server" | Someone changed a tracked file directly on the VPS. | SSH in, `git stash push -m "server edits" <file>`, then Run workflow. Better: make the change in the repo instead. |
| "Deploy secrets are not set" | The one-time setup below isn't done yet. | Do the setup. |
| "Rolled back" | The new code didn't come online. The bot is back on the old code. | Read the log lines printed in the Action, fix, merge again. |

### Backups

Before each deploy, `deploy.sh` copies the database to `backups/` on the VPS (the last 14 are kept). These backups are **on the same server**, so they don't protect against losing the VPS.

---

## One-time setup

Do this once, **outside quiet hours** (not 19:10–22:05 IST).

### 1. Get `deploy.sh` onto the server

The first automatic deploy needs the script to already be there.

```bash
ssh root@51.68.205.225 -p 20022
cd /root/peter-thiel-review-agent && git pull
```

This change doesn't touch the bot's code, so no restart is needed.

### 2. Make a deploy key that can only run the deploy

On the VPS:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/github_deploy -N "" -C github-deploy
```

Install the launcher outside the repo, so a pull never changes it:

```bash
mkdir -p /root/bin && cp /root/peter-thiel-review-agent/scripts/deploy-launcher.sh /root/bin/peter-deploy
```

Allow that key to run **only** the launcher. It can't open a shell or run anything else:

```bash
echo "command=\"bash /root/bin/peter-deploy\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $(cat /root/.ssh/github_deploy.pub)" >> /root/.ssh/authorized_keys
```

Print the two values GitHub needs:

```bash
cat /root/.ssh/github_deploy
```

```bash
ssh-keyscan -p 20022 51.68.205.225 2>/dev/null
```

### 3. Add four secrets on GitHub

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Value |
|---|---|
| `VPS_SSH_KEY` | Everything `cat /root/.ssh/github_deploy` printed, including the `BEGIN` and `END` lines |
| `VPS_KNOWN_HOSTS` | Everything `ssh-keyscan` printed |
| `VPS_HOST` | `51.68.205.225` |
| `VPS_PORT` | `20022` |

### 4. Delete the private key from the server

GitHub has it now. The server only needs the public half.

```bash
rm /root/.ssh/github_deploy
```

### 5. Try it

Actions → **CI and Deploy** → **Run workflow** on `main`. Both jobs should go green, and the deploy log should say "Already on …" (nothing new to deploy) or "Deployed … Bot is online."

### Switching an existing setup to the launcher

Servers set up before the launcher existed run the `deploy.sh` copy on disk. To switch over (outside quiet hours), after the launcher is on `main` and deployed:

```bash
mkdir -p /root/bin && cp /root/peter-thiel-review-agent/scripts/deploy-launcher.sh /root/bin/peter-deploy
```

```bash
bash -c "sed -i 's#bash /root/peter-thiel-review-agent/scripts/deploy.sh#bash /root/bin/peter-deploy#' /root/.ssh/authorized_keys"
```

```bash
grep -o 'command="[^"]*"' /root/.ssh/authorized_keys
```

The last command should print `command="bash /root/bin/peter-deploy"`.

The launcher itself never updates on its own. If it ever needs a change, copy it again with the first command.

### Turning it off

Remove the `command="…peter-deploy"` line from `/root/.ssh/authorized_keys` on the VPS. Deploys then fail at login, and tests keep running.
