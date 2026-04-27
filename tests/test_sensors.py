import json
from unittest.mock import MagicMock, patch

import pytest

from power_tracker.sensors import LinuxLmSensor


def _make_result(stdout: str, returncode: int = 0) -> MagicMock:
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    r.stderr = ""
    return r


SENSOR_JSON = {
    "zenpower-pci-00c3": {
        "Adapter": "PCI adapter",
        "SVI2_P_Core": {"power1_input": 40.0},
        "SVI2_P_SoC": {"power2_input": 5.0},
    },
    "amdgpu-pci-0700": {
        "Adapter": "PCI adapter",
        "PPT": {"power1_average": 50.0},
    },
}


@patch("power_tracker.sensors.subprocess.run")
def test_get_wattage_returns_power_readings(mock_run):
    mock_run.return_value = _make_result(json.dumps(SENSOR_JSON))
    result = LinuxLmSensor().get_wattage()
    assert result == {
        "zenpower-pci-00c3/SVI2_P_Core": 40.0,
        "zenpower-pci-00c3/SVI2_P_SoC": 5.0,
        "amdgpu-pci-0700/PPT": 50.0,
    }


@patch("power_tracker.sensors.subprocess.run")
def test_get_wattage_skips_non_power_keys(mock_run):
    data = {
        "chip": {
            "Adapter": "PCI adapter",
            "temp1": {"temp1_input": 55.0},
            "fan1": {"fan1_input": 500.0},
            "PPT": {"power1_average": 42.0},
        }
    }
    mock_run.return_value = _make_result(json.dumps(data))
    result = LinuxLmSensor().get_wattage()
    assert list(result.keys()) == ["chip/PPT"]
    assert result["chip/PPT"] == 42.0


@patch("power_tracker.sensors.subprocess.run")
def test_get_wattage_skips_adapter_key(mock_run):
    data = {"chip": {"Adapter": "Virtual device"}}
    mock_run.return_value = _make_result(json.dumps(data))
    assert LinuxLmSensor().get_wattage() == {}


@patch("power_tracker.sensors.subprocess.run")
def test_get_wattage_raises_on_nonzero_exit(mock_run):
    r = _make_result("", returncode=1)
    r.stderr = "sensors: command not found"
    mock_run.return_value = r
    with pytest.raises(RuntimeError, match="sensors failed"):
        LinuxLmSensor().get_wattage()


@patch("power_tracker.sensors.subprocess.run")
def test_get_wattage_empty_output(mock_run):
    mock_run.return_value = _make_result(json.dumps({}))
    assert LinuxLmSensor().get_wattage() == {}
