"""Constants for SolaX Local Control."""

from datetime import timedelta

DOMAIN = "solax_local"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
MAINTENANCE_UNLOCK_INTERVAL = timedelta(minutes=5)
MAINTENANCE_UNLOCK_SETTLE_SECONDS = 2

# This mapping was verified on an X1-BOOST-5K-G4 with a Pocket WiFi 3.0.
# Refuse control on other layouts until their register maps are verified.
SUPPORTED_DEVICE_TYPE = 18
SUPPORTED_SERIAL_PREFIXES = ("XB4050",)
OUTPUT_LIMIT_REGISTER = 7
MAINTENANCE_UNLOCK_REGISTER = 0
MAINTENANCE_UNLOCK_PIN = 2014
RUN_MODE_NORMAL = 2
