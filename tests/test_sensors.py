import json
from unittest.mock import MagicMock, patch

import pytest

from power_tracker.sensors import LinuxLmSensor, MacOsPowerSensor


def _make_result(stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    r.stderr = stderr
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


# ---------------------------------------------------------------------------
# MacOsPowerSensor tests
# ---------------------------------------------------------------------------

@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_milliwatts(mock_run):
    """CPU and GPU both reported in mW are converted to watts."""
    mock_run.return_value = _make_result(
        "CPU Power: 4500 mW\nGPU Power: 1200 mW\n"
    )
    result = MacOsPowerSensor().get_wattage()
    assert result == pytest.approx({"cpu": 4.5, "gpu": 1.2})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_watts_fallback(mock_run):
    """CPU and GPU both reported in W (no mW suffix) are returned as-is."""
    mock_run.return_value = _make_result(
        "CPU Power: 4.5 W\nGPU Power: 1.2 W\n"
    )
    result = MacOsPowerSensor().get_wattage()
    assert result == pytest.approx({"cpu": 4.5, "gpu": 1.2})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_mixed_units(mock_run):
    """CPU in mW and GPU in W are both parsed correctly."""
    mock_run.return_value = _make_result(
        "CPU Power: 3000 mW\nGPU Power: 2.5 W\n"
    )
    result = MacOsPowerSensor().get_wattage()
    assert result == pytest.approx({"cpu": 3.0, "gpu": 2.5})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_values_on_stderr(mock_run):
    """Power values written to stderr are still parsed (stdout+stderr merged)."""
    mock_run.return_value = _make_result(
        stdout="",
        stderr="CPU Power: 5000 mW\nGPU Power: 800 mW\n",
    )
    result = MacOsPowerSensor().get_wattage()
    assert result == pytest.approx({"cpu": 5.0, "gpu": 0.8})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_missing_gpu(mock_run):
    """Missing GPU line is simply absent from the result dict."""
    mock_run.return_value = _make_result("CPU Power: 2000 mW\n")
    result = MacOsPowerSensor().get_wattage()
    assert "gpu" not in result
    assert result == pytest.approx({"cpu": 2.0})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_missing_cpu(mock_run):
    """Missing CPU line is simply absent from the result dict."""
    mock_run.return_value = _make_result("GPU Power: 1500 mW\n")
    result = MacOsPowerSensor().get_wattage()
    assert "cpu" not in result
    assert result == pytest.approx({"gpu": 1.5})


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_empty_output(mock_run):
    """No matching lines returns an empty dict."""
    mock_run.return_value = _make_result("")
    result = MacOsPowerSensor().get_wattage()
    assert result == {}


@patch("power_tracker.sensors.subprocess.run")
def test_macos_get_wattage_raises_on_nonzero_exit(mock_run):
    """Non-zero exit raises RuntimeError with the stderr message."""
    r = _make_result("", returncode=1, stderr="powermetrics: permission denied")
    mock_run.return_value = r
    with pytest.raises(RuntimeError, match="powermetrics failed"):
        MacOsPowerSensor().get_wattage()
