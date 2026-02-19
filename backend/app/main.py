
from fastapi import FastAPI, HTTPException
from pathlib import Path
import json
import uuid
from datetime import datetime, timezone
import shutil

from app.models import HardwareIntent
from engines.pinmapper import generate_pinmap
from engines.firmware_gen import generate_platformio_project

APP_NAME = "PinPilot"
DATA_DIR = Path("data")
OUTPUTS_DIR = Path("../outputs")  # outputs folder at repo root (../outputs from backend/)

app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    description="PinPilot MVP API — Hardware Intent → Pinout Mapping → Firmware Bundle"
)


def _load_profile(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": APP_NAME,
        "utc": datetime.now(timezone.utc).isoformat()
    }


@app.get("/profiles/boards")
def list_boards():
    boards_dir = DATA_DIR / "boards"
    if not boards_dir.exists():
        return {"boards": []}
    boards = sorted([p.stem for p in boards_dir.glob("*.json")])
    return {"boards": boards}


@app.get("/profiles/peripherals")
def list_peripherals():
    per_dir = DATA_DIR / "peripherals"
    if not per_dir.exists():
        return {"peripherals": []}
    peripherals = sorted([p.stem for p in per_dir.glob("*.json")])
    return {"peripherals": peripherals}


@app.get("/profiles/boards/{board_id}")
def get_board(board_id: str):
    try:
        return _load_profile(DATA_DIR / "boards" / f"{board_id}.json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Board profile not found: {board_id}")


@app.get("/profiles/peripherals/{peripheral_id}")
def get_peripheral(peripheral_id: str):
    try:
        return _load_profile(DATA_DIR / "peripherals" / f"{peripheral_id}.json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Peripheral profile not found: {peripheral_id}")


@app.post("/generate/pinmap")
def generate_pinmap_endpoint(intent: HardwareIntent):
    """
    Generates:
      1) pinmap.json
      2) firmware/ (PlatformIO project)
      3) pinpilot_bundle.zip (pinmap + firmware)
    Saved under: outputs/<project_id>/
    """
    # Validate board profile exists
    board_path = DATA_DIR / "boards" / f"{intent.board}.json"
    if not board_path.exists():
        raise HTTPException(status_code=400, detail=f"Unknown board: {intent.board}")

    # Validate peripheral profiles exist
    peripheral_paths = []
    for p in intent.peripherals:
        per_path = DATA_DIR / "peripherals" / f"{p.id}.json"
        if not per_path.exists():
            raise HTTPException(status_code=400, detail=f"Unknown peripheral: {p.id}")
        peripheral_paths.append(str(per_path))

    # Generate project id and output folder
    project_id = uuid.uuid4().hex[:10]
    project_dir = OUTPUTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # Run pin mapper
    try:
        pinmap_result = generate_pinmap(
            board_profile_path=str(board_path),
            peripheral_profile_paths=peripheral_paths,
            reserve_usb_serial_jtag=intent.reserve_usb_serial_jtag,
            strict_avoid_boot_pins=intent.strict_avoid_boot_pins,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pin mapping failed: {str(e)}")

    # Full payload (saved + returned)
    payload = {
        "project_id": project_id,
        "device_name": intent.device_name,
        "intent": intent.model_dump(),
        "pinmap": pinmap_result,
        "generated_utc": datetime.now(timezone.utc).isoformat()
    }

    # Save pinmap.json
    with open(project_dir / "pinmap.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Generate firmware project
    try:
        generate_platformio_project(
            templates_dir=Path("templates"),
            project_dir=project_dir,
            pinmap_payload=payload,
            device_name=intent.device_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firmware generation failed: {str(e)}")

    # Create ZIP bundle (pinmap + firmware)
    try:
        zip_path = shutil.make_archive(
            base_name=str(project_dir / "pinpilot_bundle"),
            format="zip",
            root_dir=str(project_dir),
        )
        payload["bundle_zip"] = str(Path(zip_path).resolve())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ZIP bundle failed: {str(e)}")

    return payload
