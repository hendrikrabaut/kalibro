#!/bin/sh
# Shows the Kalibro timer full screen on the Waveshare 4" panel. Started by the
# desktop at login. Same approach as TrainMetrics; see docs/deployment.md.
URL=http://localhost:8002/scherm.html

until curl -fs -o /dev/null http://localhost:8002/api/health; do
  sleep 3
done

# Started straight after login, Chromium on a Pi 3 can stay a white window.
sleep 20

for attempt in 1 2 3 4 5 6 7 8 9 10; do
  wlr-randr | grep -q "480x800 px.*current" && break
  wlr-randr --output HDMI-A-1 --mode 480x800 || true
  sleep 2
done
sleep 3

exec chromium \
  --kiosk "$URL" \
  --ozone-platform=wayland \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --password-store=basic \
  --disable-features=Translate,TranslateUI \
  --lang=nl \
  --accept-lang=nl-BE,nl \
  --window-position=0,0 \
  --window-size=480,800 \
  --force-device-scale-factor=0.96 \
  --disable-gpu \
  --renderer-process-limit=1 \
  --disk-cache-size=20000000
