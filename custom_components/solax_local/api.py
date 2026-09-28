"""Local HTTP client for a SolaX Pocket WiFi 3.0 dongle."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    MAINTENANCE_UNLOCK_INTERVAL,
    MAINTENANCE_UNLOCK_PIN,
    MAINTENANCE_UNLOCK_REGISTER,
    MAINTENANCE_UNLOCK_SETTLE_SECONDS,
    OUTPUT_LIMIT_REGISTER,
    SUPPORTED_DEVICE_TYPE,
    SUPPORTED_SERIAL_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)


class SolaxError(Exception):
    """Base exception for the local SolaX API."""


class SolaxConnectionError(SolaxError):
    """The dongle could not be reached or returned invalid HTTP."""


class SolaxAuthError(SolaxError):
    """The dongle rejected its local password."""


class SolaxProtocolError(SolaxError):
    """The dongle returned unexpected data."""


class SolaxUnsupportedDeviceError(SolaxProtocolError):
    """The inverter layout has not been verified for safe control."""


@dataclass(frozen=True, slots=True)
class SolaxSnapshot:
    """One coordinated inverter and settings sample."""

    serial_number: str
    firmware_version: str | None
    rated_power_kw: float
    ac_voltage_v: float
    ac_current_a: float
    ac_frequency_hz: float
    ac_power_w: int
    pv1_voltage_v: float
    pv2_voltage_v: float
    pv1_current_a: float
    pv2_current_a: float
    pv1_power_w: int
    pv2_power_w: int
    run_mode: int
    total_yield_kwh: float
    today_yield_kwh: float
    output_limit_percent: int
    export_limit_w: int
    export_mode: int

    @property
    def pv_power_w(self) -> int:
        """Return combined DC PV power."""
        return self.pv1_power_w + self.pv2_power_w


def _number(value: Any, name: str) -> float:
    """Return a numeric protocol value or fail with a useful error."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolaxProtocolError(f"{name} was not numeric")
    return float(value)


def _integer(value: Any, name: str) -> int:
    """Return an integer-valued protocol field."""
    number = _number(value, name)
    if not number.is_integer():
        raise SolaxProtocolError(f"{name} was not an integer")
    return int(number)


def encode_solax_form(values: dict[str, object]) -> str:
    """Encode the non-standard form format used by SolaX's own web client.

    Keys are URL encoded, while values - including setReg JSON - are sent
    literally. Using normal application/x-www-form-urlencoded encoding turns
    the JSON into percent escapes and this dongle silently rejects the write.
    """
    for value in values.values():
        if "&" in str(value):
            raise ValueError("SolaX form values cannot safely contain ampersands")
    return "&".join(f"{quote(key)}={value}" for key, value in values.items())


def build_register_command(register: int, value: int) -> str:
    """Build the exact local setReg JSON accepted by this inverter."""
    return json.dumps(
        {"num": 1, "Data": [{"reg": register, "val": str(value)}]},
        separators=(",", ":"),
    )


def parse_snapshot(realtime: Any, settings: Any) -> SolaxSnapshot:
    """Validate and map the verified X1-BOOST-5K-G4 response layout."""
    if not isinstance(realtime, dict):
        raise SolaxProtocolError("Real-time response was not an object")
    information = realtime.get("Information")
    data = realtime.get("Data")
    if not isinstance(information, list) or len(information) < 3:
        raise SolaxProtocolError("Real-time Information array was incomplete")
    if not isinstance(data, list) or len(data) < 24:
        raise SolaxProtocolError("Real-time Data array was incomplete")
    if not isinstance(settings, list) or len(settings) < 151:
        raise SolaxProtocolError("Settings array was incomplete")

    device_type = _integer(realtime.get("type"), "device type")
    serial_number = str(information[2]).strip()
    if device_type != SUPPORTED_DEVICE_TYPE or not serial_number.startswith(
        SUPPORTED_SERIAL_PREFIXES
    ):
        raise SolaxUnsupportedDeviceError(
            "Unsupported inverter layout "
            f"(type {device_type}, serial {serial_number!r})"
        )

    return SolaxSnapshot(
        serial_number=serial_number,
        firmware_version=str(realtime["ver"]) if realtime.get("ver") else None,
        rated_power_kw=_number(information[0], "rated power"),
        ac_voltage_v=_number(data[0], "AC voltage") / 10,
        ac_current_a=_number(data[1], "AC current") / 10,
        ac_frequency_hz=_number(data[2], "AC frequency") / 100,
        ac_power_w=_integer(data[3], "AC power"),
        pv1_voltage_v=_number(data[4], "PV1 voltage") / 10,
        pv2_voltage_v=_number(data[5], "PV2 voltage") / 10,
        pv1_current_a=_number(data[8], "PV1 current") / 10,
        pv2_current_a=_number(data[9], "PV2 current") / 10,
        run_mode=_integer(data[10], "run mode"),
        pv1_power_w=_integer(data[13], "PV1 power"),
        pv2_power_w=_integer(data[14], "PV2 power"),
        total_yield_kwh=_number(data[19], "total yield") / 10,
        today_yield_kwh=_number(data[21], "today yield") / 10,
        output_limit_percent=_integer(settings[29], "output limit"),
        export_limit_w=_integer(settings[30], "export limit"),
        export_mode=_integer(settings[127], "export mode"),
    )


class SolaxLocalApi:
    """Communicate directly with a SolaX Pocket WiFi dongle."""

    def __init__(self, host: str, password: str, session: ClientSession) -> None:
        """Initialize the client without making a network request."""
        clean_host = host.strip().removeprefix("http://").removeprefix("https://")
        self._base_url = f"http://{clean_host.rstrip('/')}"
        self._password = password
        self._session = session
        self._token: str | None = None
        self._request_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._last_unlock_attempt_at = 0.0

    async def _async_pace_requests(self) -> None:
        """Avoid overrunning the dongle's small embedded HTTP server."""
        loop = asyncio.get_running_loop()
        remaining = 0.5 - (loop.time() - self._last_request_at)
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def async_login(self) -> None:
        """Authenticate to the dongle's local web API."""
        await self._async_pace_requests()
        try:
            async with self._session.post(
                f"{self._base_url}/api/login",
                json={"acc": "admin", "pwd": self._password},
                headers={
                    "Connection": "close",
                    "X-Forwarded-For": "5.8.8.8",
                },
                timeout=10,
            ) as response:
                if response.status in (401, 403):
                    raise SolaxAuthError("Dongle login was rejected")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except SolaxAuthError:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            raise SolaxConnectionError("Could not log in to the SolaX dongle") from err

        finally:
            self._last_request_at = asyncio.get_running_loop().time()

        if not isinstance(payload, dict):
            raise SolaxProtocolError("Login response was not an object")
        data = payload.get("data")
        token = data.get("token") if isinstance(data, dict) else None
        if payload.get("code") != 0 or not isinstance(token, str) or not token:
            raise SolaxAuthError("Dongle login failed; check the local password")
        self._token = token

    async def _async_operation(self, operation: str, **extra: object) -> str:
        """Run one local dongle operation, reauthenticating once if needed."""
        async with self._request_lock:
            if self._token is None:
                await self.async_login()

            form = encode_solax_form(
                {"optType": operation, "pwd": self._password, **extra}
            )
            for attempt in range(2):
                await self._async_pace_requests()
                try:
                    async with self._session.post(
                        f"{self._base_url}/",
                        data=form.encode(),
                        headers={
                            "Connection": "close",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-Forwarded-For": "5.8.8.8",
                            "token": self._token or "",
                        },
                        timeout=10,
                    ) as response:
                        if response.status in (401, 403):
                            if attempt == 0:
                                await self.async_login()
                                continue
                            raise SolaxAuthError("Dongle authentication expired")
                        response.raise_for_status()
                        return await response.text()
                except SolaxAuthError:
                    raise
                except ClientResponseError as err:
                    raise SolaxConnectionError(
                        f"SolaX dongle returned HTTP {err.status}"
                    ) from err
                except (ClientError, TimeoutError) as err:
                    raise SolaxConnectionError(
                        "Could not reach the SolaX dongle"
                    ) from err
                finally:
                    self._last_request_at = asyncio.get_running_loop().time()

        raise SolaxAuthError("Dongle authentication failed")

    async def async_get_snapshot(self) -> SolaxSnapshot:
        """Read live data and settings as one validated sample."""
        realtime_text = await self._async_operation("ReadRealTimeData")
        settings_text = await self._async_operation("ReadSetData")
        try:
            realtime = json.loads(realtime_text)
            settings = json.loads(settings_text)
        except json.JSONDecodeError as err:
            raise SolaxProtocolError("Dongle returned invalid JSON") from err
        snapshot = parse_snapshot(realtime, settings)

        # Maintenance access is transient and its LockMode setting does not
        # reflect whether register writes are currently authorised. Refresh
        # it periodically, but never sacrifice otherwise valid telemetry if
        # the keepalive itself fails.
        try:
            await self.async_ensure_unlocked()
        except SolaxError as err:
            _LOGGER.warning("Could not refresh SolaX maintenance unlock: %s", err)

        return snapshot

    async def _async_write_register(self, register: int, value: int) -> str:
        """Write one local HTTP register and return its raw acknowledgement."""
        return await self._async_operation(
            "setReg", data=build_register_command(register, value)
        )

    async def _async_unlock_without_lock(self) -> None:
        """Unlock maintenance writes while the command lock is already held."""
        self._last_unlock_attempt_at = asyncio.get_running_loop().time()
        response = await self._async_write_register(
            MAINTENANCE_UNLOCK_REGISTER, MAINTENANCE_UNLOCK_PIN
        )
        if not response.startswith("Y"):
            raise SolaxProtocolError(
                f"Dongle did not acknowledge maintenance unlock: {response!r}"
            )

    async def async_ensure_unlocked(self, *, force: bool = False) -> None:
        """Keep the inverter in maintenance-unlocked mode."""
        now = asyncio.get_running_loop().time()
        if (
            not force
            and now - self._last_unlock_attempt_at
            < MAINTENANCE_UNLOCK_INTERVAL.total_seconds()
        ):
            return

        async with self._write_lock:
            now = asyncio.get_running_loop().time()
            if (
                not force
                and now - self._last_unlock_attempt_at
                < MAINTENANCE_UNLOCK_INTERVAL.total_seconds()
            ):
                return
            await self._async_unlock_without_lock()

    async def async_set_output_limit(self, percent: int) -> None:
        """Set the verified whole-inverter output percentage register."""
        if isinstance(percent, bool) or not isinstance(percent, int):
            raise ValueError("Output limit must be an integer")
        if not 0 <= percent <= 100:
            raise ValueError("Output limit must be between 0 and 100 percent")

        async with self._write_lock:
            # The inverter relocks maintenance settings after restart and may
            # do so at the start of a new solar day. Always unlock immediately
            # before the requested control write.
            await self._async_unlock_without_lock()
            await asyncio.sleep(MAINTENANCE_UNLOCK_SETTLE_SECONDS)
            response = await self._async_write_register(
                OUTPUT_LIMIT_REGISTER, percent
            )
        if not response.startswith("Y"):
            raise SolaxProtocolError(
                f"Dongle did not acknowledge the output-limit command: {response!r}"
            )
