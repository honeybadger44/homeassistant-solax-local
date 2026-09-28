"""Protocol mapping tests that do not require Home Assistant."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

# Loading a component normally executes its Home Assistant entrypoint. These
# protocol-only tests deliberately load just const.py and api.py so they can be
# run in a lightweight development environment without installing HA Core.
COMPONENT = Path(__file__).parents[1] / "custom_components" / "solax_local"
custom_components = ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENT.parent)]
solax_package = ModuleType("custom_components.solax_local")
solax_package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components", custom_components)
sys.modules.setdefault("custom_components.solax_local", solax_package)
for module_name in ("const", "api"):
    qualified_name = f"custom_components.solax_local.{module_name}"
    spec = spec_from_file_location(qualified_name, COMPONENT / f"{module_name}.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)

api = sys.modules["custom_components.solax_local.api"]
encode_solax_form = api.encode_solax_form
parse_snapshot = api.parse_snapshot


def _responses():
    realtime = {
        "type": 18,
        "ver": "3.015.02",
        "Information": [5.0, "redacted", "XB405012345678"],
        "Data": [0] * 24,
    }
    realtime["Data"][0] = 2314
    realtime["Data"][1] = 182
    realtime["Data"][2] = 5001
    realtime["Data"][3] = 4210
    realtime["Data"][4] = 3072
    realtime["Data"][5] = 2984
    realtime["Data"][8] = 76
    realtime["Data"][9] = 71
    realtime["Data"][10] = 2
    realtime["Data"][13] = 2335
    realtime["Data"][14] = 2112
    realtime["Data"][19] = 12345
    realtime["Data"][21] = 187
    settings = [0] * 151
    settings[29] = 60
    settings[30] = 0
    settings[127] = 2
    return realtime, settings


def test_parse_verified_snapshot() -> None:
    """Map the indexes verified against the live inverter."""
    snapshot = parse_snapshot(*_responses())
    assert snapshot.serial_number == "XB405012345678"
    assert snapshot.ac_voltage_v == 231.4
    assert snapshot.ac_frequency_hz == 50.01
    assert snapshot.ac_power_w == 4210
    assert snapshot.pv_power_w == 4447
    assert snapshot.today_yield_kwh == 18.7
    assert snapshot.total_yield_kwh == 1234.5
    assert snapshot.output_limit_percent == 60
    assert snapshot.export_mode == 2


def test_setreg_form_keeps_json_literal() -> None:
    """Do not regress to standard form encoding, which breaks this dongle."""
    command = '{"num":1,"Data":[{"reg":7,"val":"20"}]}'
    encoded = encode_solax_form(
        {"optType": "setReg", "pwd": "example", "data": command}
    )
    assert encoded == f"optType=setReg&pwd=example&data={command}"
    assert "%7B" not in encoded
