import os
from zoneinfo import ZoneInfo

# Availability is entered in local time; everything stored is UTC.
LOCAL_TZ = ZoneInfo(os.environ.get("KALIBRO_TZ", "Europe/Brussels"))
