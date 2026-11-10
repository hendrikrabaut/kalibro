# Installeren op de Raspberry Pi

Kalibro draait naast TrainMetrics op dezelfde Pi: Kalibro op poort 8002,
TrainMetrics op 8000. Alles blijft op de Pi; er gaat geen cursusmateriaal naar
buiten.

## 1. Installeren

De Pi heeft al `uv` en de tijdzone `Europe/Brussels` (zie de handleiding van
TrainMetrics). Dan:

```bash
cd ~
git clone <url-van-je-repo> kalibro
cd kalibro/backend
uv sync --no-dev
uv run alembic upgrade head
```

Wil je je database en PDF's van de laptop meenemen:

```bash
scp database/kalibro.db pi@raspberrypi.local:kalibro/database/
scp -r data/uploads pi@raspberrypi.local:kalibro/data/
```

## 2. Automatisch starten en dagelijkse back-up

```bash
cd ~/kalibro
sudo cp deploy/kalibro.service deploy/kalibro-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kalibro kalibro-backup.timer
```

De back-up maakt elke nacht een kopie in `data/backups/` en houdt de laatste 14.
Die kopie staat op dezelfde SD-kaart, dus kopieer ze af en toe naar elders.

## 3. Bereikbaar via Tailscale

TrainMetrics gebruikt al het standaardadres. Kalibro krijgt poort 8443:

```bash
sudo tailscale serve --bg --https=8443 8002
```

De app staat dan op `https://<naam-van-de-pi>.<jouw-tailnet>.ts.net:8443`.

**Agenda:** `/api/calendar.ics` werkt als abonnement alleen in een agenda-app die
zelf de Pi kan bereiken, dus op een toestel met Tailscale (Apple Agenda met
*Op mijn Mac*, Thunderbird, iOS met VPN On Demand). Google Agenda haalt feeds op
vanaf de servers van Google en kan je tailnet niet bereiken. Download het bestand
daar eenmalig en importeer het, of zet de feed bewust publiek met
`tailscale funnel` (dan kan iedereen met de link je planning zien).

## 4. Het kleine scherm

`scherm.html` is de timer: starten, pauzeren en afronden met grote knoppen,
geschikt voor het resistieve aanraakscherm. Het ververst elke 30 seconden, dus
een timer die je op de laptop start, verschijnt ook daar.

Het scherm is al ingesteld voor TrainMetrics (FKMS, `hdmi_timings`, kanshi,
Chromium-policy). Om het naar Kalibro te zetten, vervang je alleen het
opstartscript:

```bash
echo '/home/pi/kalibro/deploy/screen.sh > /tmp/screen.log 2>&1 &' > ~/.config/labwc/autostart
sudo reboot
```

Terug naar TrainMetrics: zet in hetzelfde bestand opnieuw
`/home/pi/trainmetrics/deploy/screen.sh`.

## Updaten

```bash
cd ~/kalibro && git pull
cd backend && uv sync --no-dev && uv run alembic upgrade head
sudo systemctl restart kalibro
```

Heeft een update de herkenning van hoofdstukken verbeterd, gebruik dan
**opnieuw** bij een bron. Dat wordt geweigerd zodra er tijd gelogd is op taken
van die bron, zodat je nooit gelogde tijd verliest.
