# Deploying

The bot runs as one container on a VPS next to other projects, under a `deploy` user that is in
the `docker` group and has no shell over SSH. Long polling needs no inbound port, so nothing is
published.

## Once, on the server

```bash
ssh root@YOUR_SERVER
install -d -o deploy -g deploy /srv/deel-advisor
sudo -u deploy git clone https://github.com/vinter-man/deel-bot /srv/deel-advisor
install -m 600 -o deploy -g deploy /dev/null /srv/deel-advisor/.env
$EDITOR /srv/deel-advisor/.env          # BOT_TOKEN=..., OWNER_ID=... (see .env.example)
sudo -u deploy sh -c 'cd /srv/deel-advisor && docker compose up -d --build'
```

Then a key that CI uses and that can do exactly one thing:

```bash
ssh-keygen -t ed25519 -N '' -C deel-advisor-ci -f deel_advisor_ci
# on the server, append to /home/deploy/.ssh/authorized_keys:
command="/srv/deel-advisor/deploy/deploy.sh",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAA... deel-advisor-ci
```

The forced command means a session with that key runs `deploy.sh` and exits, whatever the
client asks for; a leaked secret buys an attacker a redeploy of this repository's `main` and
nothing else.

## Repository secrets

| Secret | What it is |
|---|---|
| `DEPLOY_HOST` | the server's address |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the private half of `deel_advisor_ci` |
| `DEPLOY_HOST_KEY` | `ssh-keyscan -t ed25519 YOUR_SERVER`, pinned so the first connection cannot be intercepted |

## What a push to `main` does

CI runs ruff, prettier, mypy, the tests with a coverage gate, shellcheck, and builds the image
and imports every module from it. Only when all of that is green does it SSH in with the tested
commit's sha. `deploy.sh` accepts that sha only if it is on `origin/main` and not behind what is
running, builds first (a broken build changes nothing), restarts, and waits for the container's
healthcheck — a heartbeat file a background task touches each minute after a successful
`getMe`, i.e. the process is alive and reaches Telegram. Unhealthy
after a deploy that started from a healthy state means an automatic rollback to the previous
commit.

`.env` and the `data` volume (FX cache, language preferences) are never touched by a deploy.

To deploy by hand: `ssh -i deel_advisor_ci deploy@YOUR_SERVER` (or with a sha as the command).
