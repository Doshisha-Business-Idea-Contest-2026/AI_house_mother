# deploy/

Deployment artefacts for AI House Mother.

## Files

- **`ai_house_mother.service`** — systemd unit that runs uvicorn on
  port 8084 with `--workers 1`. Copy to `/etc/systemd/system/` on the
  deploy host.
- **`apache.conf.snippet`** — Apache reverse-proxy stanza to be inserted
  into the existing `linebot.kmchan.jp` VirtualHost files.

## First-time setup

```bash
# 1. systemd unit
sudo cp deploy/ai_house_mother.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai_house_mother.service
sudo systemctl start ai_house_mother.service
sudo systemctl status ai_house_mother.service

# 2. Apache reverse proxy (both files)
sudo vim /etc/apache2/sites-enabled/linebot.kmchan.jp.conf
sudo vim /etc/apache2/sites-enabled/linebot.kmchan.jp-le-ssl.conf
sudo apache2ctl configtest
sudo systemctl reload apache2

# 3. Verify
curl https://linebot.kmchan.jp/ai_house_mother/health

# 4. LINE Developers Console
#    Webhook URL: https://linebot.kmchan.jp/ai_house_mother/callback
#    Enable "Use webhook", disable "Auto-reply messages".
```

## Restart & logs

```bash
sudo systemctl restart ai_house_mother.service
journalctl -u ai_house_mother.service -f
```

## Local development

Instead of touching systemd, use `scripts/run_local.sh` on a machine
that already has `.venv` populated and a valid `.env`.
