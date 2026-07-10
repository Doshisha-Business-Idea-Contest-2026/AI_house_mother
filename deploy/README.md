# deploy/

Deployment artefacts for AI House Mother.

## Files

- **`ai_house_mother.service`** — systemd unit that runs uvicorn on
  port 8084 with `--workers 1`. Copy to `/etc/systemd/system/` on the
  deploy host.
- **`ai_house_mother_monthly.service`** — oneshot systemd unit that
  runs `scripts/push_monthly_reports.py` when triggered by the timer
  below (or by hand for a manual re-run).
- **`ai_house_mother_monthly.timer`** — systemd timer that fires on the
  1st of every month at 09:00 Asia/Tokyo. `Persistent=true` re-fires
  the run once on boot if the machine was offline during the schedule.
- **`apache.conf.snippet`** — Apache reverse-proxy stanza to be inserted
  into the existing `linebot.kmchan.jp` VirtualHost files.

## First-time setup

```bash
# 1. systemd unit for the LINE Bot
sudo cp deploy/ai_house_mother.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai_house_mother.service
sudo systemctl start ai_house_mother.service
sudo systemctl status ai_house_mother.service

# 2. systemd timer for the monthly parent summary push
sudo cp deploy/ai_house_mother_monthly.service /etc/systemd/system/
sudo cp deploy/ai_house_mother_monthly.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai_house_mother_monthly.timer
systemctl list-timers ai_house_mother_monthly.timer

# 3. Apache reverse proxy (both files)
sudo vim /etc/apache2/sites-enabled/linebot.kmchan.jp.conf
sudo vim /etc/apache2/sites-enabled/linebot.kmchan.jp-le-ssl.conf
sudo apache2ctl configtest
sudo systemctl reload apache2

# 4. Verify
curl https://linebot.kmchan.jp/ai_house_mother/health

# 5. LINE Developers Console
#    Webhook URL: https://linebot.kmchan.jp/ai_house_mother/callback
#    Enable "Use webhook", disable "Auto-reply messages".
```

## Restart & logs

```bash
sudo systemctl restart ai_house_mother.service
journalctl -u ai_house_mother.service -f

# Monthly push (manual re-run and log)
sudo systemctl start ai_house_mother_monthly.service
journalctl -u ai_house_mother_monthly.service -n 50
```

## Monthly push manual invocation

For demos or catch-up runs, invoke the script directly (works without
systemd) — the state file at `data/monthly_report_state.json`
deduplicates against the batched YYYY-MM.

```bash
# Push the month before "now" (default)
.venv/bin/python scripts/push_monthly_reports.py

# Force-resend a specific month even if already recorded
.venv/bin/python scripts/push_monthly_reports.py --month 2026-07 --force

# Freeze the reference "now" for boundary tests
.venv/bin/python scripts/push_monthly_reports.py --now 2026-08-01T09:00:00+09:00
```

## Demo reset (pre-presentation)

`scripts/reset_demo.py` wipes every runtime JSON under `data/` (users,
profiles, posts, invitations, parent_links, session_activities,
monthly_report_state, coupon_distributions, prize_draws, …) back to its
empty skeleton. `data/seed/*.json` is never touched.

**Always stop the service first.** The script refuses to run while the
unit is active because overwriting live JSON while the LINE Bot holds
state in memory can silently revert or corrupt the file on the next
write. Use `--force-service-active` only when you know the risk.

```bash
# 1. Stop the LINE Bot so nothing is holding state
sudo systemctl stop ai_house_mother.service

# 2. Reset the runtime JSON
.venv/bin/python scripts/reset_demo.py --yes

# 3. Start the LINE Bot back up
sudo systemctl start ai_house_mother.service
sudo systemctl status ai_house_mother.service
```

Preview the target list without writing anything: `--dry-run`.
When the service is running the script exits with return code 2 and
prints the three-step recipe above.

## Local development

Instead of touching systemd, use `scripts/run_local.sh` on a machine
that already has `.venv` populated and a valid `.env`.
