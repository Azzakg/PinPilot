import os
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app


def test_simulated_run_generates_and_builds(tmp_path: Path):
    """
    CI-friendly test:
      1) Calls POST /generate/pinmap (no uvicorn needed)
      2) Asserts artifacts exist (pinmap.json, firmware files, zip)
      3) Runs PlatformIO build in generated firmware folder
    """
    # Make API write outputs to a temporary folder
    os.environ["PINPILOT_OUTPUTS_DIR"] = str(tmp_path / "outputs")

    client = TestClient(app)

    payload = {
        "device_name": "ci_smart_shelf_tag",
        "board": "esp32c3",
        "peripherals": [
            {"id": "epaper_spi_2p13"},
            {"id": "bme280_i2c"},
        ],
        "power": {"source": "battery", "voltage": 3.7, "deep_sleep_required": True},
        "connectivity": {"type": "wifi", "protocol": "mqtt"},
        "reserve_usb_serial_jtag": True,
        "strict_avoid_boot_pins": True,
    }

    r = client.post("/generate/pinmap", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()

    # --- Validate response structure ---
    assert "project_id" in data
    assert "pinmap" in data
    assert "bundle_zip" in data

    project_id = data["project_id"]

    # --- Validate files exist on disk ---
    project_dir = Path(os.environ["PINPILOT_OUTPUTS_DIR"]) / project_id
    assert project_dir.exists(), f"Missing project dir: {project_dir}"

    pinmap_file = project_dir / "pinmap.json"
    assert pinmap_file.exists(), "pinmap.json not generated"

    firmware_dir = project_dir / "firmware"
    assert firmware_dir.exists(), "firmware/ not generated"
    assert (firmware_dir / "platformio.ini").exists(), "platformio.ini missing"
    assert (firmware_dir / "src" / "main.cpp").exists(), "src/main.cpp missing"
    assert (firmware_dir / "include" / "pinmap.h").exists(), "include/pinmap.h missing"

    zip_path = Path(data["bundle_zip"])
    assert zip_path.exists(), "ZIP bundle missing"

    # --- Ensure pinmap.json is valid JSON ---
    pinmap_json = json.loads(pinmap_file.read_text(encoding="utf-8"))
    assert pinmap_json["project_id"] == project_id

    # --- Build firmware with PlatformIO (no device needed) ---
    # Use python -m platformio to avoid system pio conflicts.
    result = subprocess.run(
        ["python", "-m", "platformio", "run"],
        cwd=str(firmware_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "PlatformIO build failed\n"
        f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    )
