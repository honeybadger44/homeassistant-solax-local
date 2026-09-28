"""Constants for SolaX Local Control."""

from datetime import timedelta

DOMAIN = "solax_local"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)

# This mapping was verified on an X1-BOOST-5K-G4 with a Pocket WiFi 3.0.
# Refuse control on other layouts until their register maps are verified.
SUPPORTED_DEVICE_TYPE = 18
SUPPORTED_SERIAL_PREFIXES = ("XB4050",)
OUTPUT_LIMIT_REGISTER = 7

