import json
import subprocess
from abc import ABC, abstractmethod
import platform
import cpuinfo



class WattageSensor(ABC):
    os: str = ""
    cpu: str = ""

    @abstractmethod
    def get_wattage(self) -> dict[str, float]:
        """Return mapping of '{chip}/{label}' -> watts."""
        ...

    def linux_version(self) -> str:
        try:
            return platform.linux_distribution()[0].lower()
        except AttributeError:
            # platform.linux_distribution() is removed in Python 3.8+
            return "N/A"
        
    def macos_version(self) -> str:
        try:
            if platform.mac_ver()[0] == '':
                return "N/A"
            return platform.mac_ver()[0].lower()
        except AttributeError:
            # platform.mac_ver() is removed in some Python versions
            return "N/A"
    
    def get_config(self) -> dict[str, str]:
        platform_os = platform.platform().lower() # Treat 'macOS' as 'macos' for compatibility  
        platform_mac = self.macos_version() # Get macOS version for Apple Silicon detection
        cpu_info = cpuinfo.get_cpu_info()
        platform_cpu = cpu_info.get("brand_raw", "").lower()
        lv = self.linux_version() # Get CPU brand for AMD/Intel/Apple detection
        print(f"Detected platform: {platform_os}, mac_ver: {platform_mac}, cpu_brand: {platform_cpu}, linux_version: {lv}")

        #check os and set os class variable
        if "windows" in platform_os:
            self.os = "windows"
        elif "darwin" in platform_os or "mac" in platform_os:
            self.os = "macos"
        elif "linux" in platform_os:
            self.os = "linux"
        else:
            raise RuntimeError(f"Unsupported OS: {platform_os}")
        
        #check cpu and set cpu class variable
        if "apple" in platform_cpu:
            self.cpu = "apple"
        elif "amd" in platform_cpu:
            self.cpu = "amd"
        elif "intel" in platform_cpu:
            self.cpu = "intel"
        else:
            # Fallback to Linux version parsing for AMD/Intel detection if cpuinfo fails
            if self.os == "linux":
                if "ubuntu" in lv or "debian" in lv:
                    self.cpu = "amd"  # Assume AMD for common Linux distros if cpuinfo is inconclusive
                else:
                    self.cpu = "unknown"
            else:
                raise RuntimeError(f"Unsupported CPU: {platform_cpu}")
            
        #check if zenpower is available on linux with amd cpu using lsmod
        if self.os == "linux" and self.cpu == "amd":
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"lsmod failed: {result.stderr.strip()}")
            if "zenpower" in result.stdout:
                print("Detected zenpower module for AMD CPU on Linux")
            else:
                # thrwo error if zenpower is not available on linux with amd cpu
                warn_msg = """
                    Warning: zenpower module not detected, wattage readings may be unavailable or inaccurate on AMD CPU with Linux.
                    To enable wattage readings, please ensure you have the zenpower kernel module installed and loaded.
                    check https://github.com/AliEmreSenel/zenpower3 for more information.
                    """
                
                raise RuntimeError(warn_msg)
        
                


class WindowsPowerSensor(WattageSensor):
    os = "windows"
    cpu = "amd"

    def get_wattage(self) -> dict[str, float]:
        # Placeholder implementation for Windows power sensor
        return {}


class MacOsPowerSensor(WattageSensor):
    os = "macos"
    cpu = "apple"

    def get_wattage(self) -> dict[str, float]:
        result = subprocess.run(
            ["powermetrics", "--samplers", "smc", "-n1", "-J"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"powermetrics failed: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        readings: dict[str, float] = {}

        for sample in data.get("samples", []):
            for key, value in sample.get("smc_readings", {}).items():
                if key.startswith("P") and key.endswith("_avg"):
                    chip_label = key[:-4]  # Remove '_avg' suffix
                    readings[chip_label] = float(value)

        return readings

class LinuxLmSensor(WattageSensor):
    os = "linux"
    cpu = "amd"

    def get_wattage(self) -> dict[str, float]:
        result = subprocess.run(
            ["sensors", "-j"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"sensors failed: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        readings: dict[str, float] = {}

        for chip, chip_data in data.items():
            if not isinstance(chip_data, dict):
                continue
            for label, sensor_data in chip_data.items():
                if label == "Adapter" or not isinstance(sensor_data, dict):
                    continue
                for key, value in sensor_data.items():
                    if key.startswith("power") and (
                        key.endswith("_input") or key.endswith("_average")
                    ):
                        readings[f"{chip}/{label}"] = float(value)

        return readings


# Registry: (os, cpu) -> sensor class. Add new platforms here.
_SENSOR_REGISTRY: dict[tuple[str, str], type[WattageSensor]] = {
    ("linux", "amd"):    LinuxLmSensor,
    ("linux", "intel"):  LinuxLmSensor,
    ("macos", "apple"):  MacOsPowerSensor,
    ("windows", "amd"):  WindowsPowerSensor,
    ("windows", "intel"): WindowsPowerSensor,
}


def get_sensor() -> WattageSensor:
    """Detect OS/CPU and return the appropriate WattageSensor instance."""
    probe = LinuxLmSensor()
    probe.get_config()
    key = (probe.os, probe.cpu)
    cls = _SENSOR_REGISTRY.get(key)
    if cls is None:
        raise RuntimeError(f"No sensor registered for {key}")
    sensor = cls()
    print(f"Using sensor: {cls.__name__} (os={sensor.os}, cpu={sensor.cpu})")
    return sensor
