# Accessing the `prior` web app on ziz4

The app runs entirely on **ziz4** (`zizgpu04.cpu.stats.ox.ac.uk`), which sits
behind the department **jump host** (gateway). You reach it from your laptop by
SSH port-forwarding the two ports the app uses, then opening it in your local
browser. Nothing is exposed to the public internet.

| Port | Service | Notes |
|------|---------|-------|
| 5175 | Vite UI | what you open in the browser |
| 8078 | FastAPI | the browser calls this directly (baked in via `VITE_API_BASE`) |
| 7687 | Neo4j (bolt) | only needed if you want to query the DB directly |

---

## 1. Get your own access (no shared keys)

Each person uses **their own** SSH key and department account — we never share
private keys.

1. Generate a key on your laptop (skip if you have one):
   ```bash
   ssh-keygen -t ed25519 -C "you@stats.ox.ac.uk"
   ```
2. Send **only the public key** (`~/.ssh/id_ed25519.pub`) to the department admin
   and request access to the jump host + ziz4. (Private key never leaves your laptop.)

## 2. SSH config (`~/.ssh/config` on your laptop)

Fill in `<your-user>` and the real `<jump-host-hostname>`:

```sshconfig
Host ziz
    HostName <jump-host-hostname>        # department gateway / jump host
    User <your-user>

Host ziz4
    HostName zizgpu04.cpu.stats.ox.ac.uk
    User <your-user>
    ProxyJump ziz                        # routes through the gateway automatically
```

Test it: `ssh ziz4` should drop you onto the box.

## 3. Start the servers (on ziz4)

Once: clone/checkout the repo and install (`pip install -e ".[graph,web]"`).
Then, from the repo root on ziz4:

```bash
bash scripts/prior-up.sh        # starts Neo4j + API (:8078) + UI (:5175)
```
Tip: run it inside `tmux`/`screen` so it survives disconnects. Logs land in
`/tmp/prior-api.log` and `/tmp/prior-ui.log`. (Neo4j creds: see RUNNING.md.)

## 4. Tunnel + open (on your laptop)

```bash
./scripts/prior-tunnel.sh       # forwards 5175 + 8078, opens the browser
```
Or the raw one-liner:
```bash
ssh -N -L 5175:127.0.0.1:5175 -L 8078:127.0.0.1:8078 ziz4
```
then open **http://127.0.0.1:5175**. Leave the tunnel running while you use the app.

---

## Troubleshooting

- **Page loads but no data / errors:** port 8078 isn't forwarded, or the API/Neo4j
  isn't running on ziz4. Check `/tmp/prior-api.log`.
- **`channel: open failed: connect failed`:** the server on ziz4 isn't up on that
  port yet — run `scripts/prior-up.sh` first.
- **`open: command not found` (Linux laptop):** the script falls back to `xdg-open`;
  if neither exists, just open the URL manually.
- **Permission denied (publickey):** your key/account isn't set up — see step 1.
