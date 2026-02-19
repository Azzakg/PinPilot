import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class PinPick:
    gpio: int
    reason: str
    score: int  # higher is better


def _load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_required_pins(peripheral: dict) -> List[dict]:
    """Return a list of pin descriptors that are required."""
    pins = peripheral.get("pins", [])
    return [p for p in pins if p.get("required") is True]


def _role_to_bus_role(pin_desc: dict) -> Optional[str]:
    return pin_desc.get("bus_role")


def _is_sensitive_role(role: str) -> bool:
    # Roles that often cause boot issues if forced high/low at reset
    return role in {"CS", "RST", "EN", "BOOT"}


def _rank_candidates(
    *,
    role: str,
    bus_role: Optional[str],
    board: dict,
    used: set[int],
    reserve_usb: bool,
    strict_avoid_boot: bool,
) -> List[PinPick]:
    """
    Produce ranked GPIO candidates for a given role.
    """
    gpio_min = board["gpio_range"]["min"]
    gpio_max = board["gpio_range"]["max"]
    all_gpio = list(range(gpio_min, gpio_max + 1))

    strapping = set(board.get("strapping_pins", {}).get("pins", []))
    usb = set(board.get("reserved_or_special", {}).get("usb_serial_jtag", []))
    preferred_order = board.get("pin_risk_rules", {}).get("prefer_free_pins_first", [])

    # Recommended pins per bus role (SCLK/MOSI/etc)
    rec = board.get("recommendations", {})
    bus_rec = []
    if bus_role:
        if bus_role.startswith("spi_"):
            k = bus_role.replace("spi_", "").upper()  # spi_sclk -> SCLK
            bus_rec = rec.get("spi_recommended", {}).get(k, [])
        elif bus_role.startswith("i2c_"):
            k = bus_role.replace("i2c_", "").upper()  # i2c_sda -> SDA
            bus_rec = rec.get("i2c_recommended", {}).get(k, [])
        elif bus_role.startswith("uart_"):
            k = bus_role.replace("uart_", "").upper()
            bus_rec = rec.get("uart_recommended", {}).get(k, [])

    candidates: List[PinPick] = []

    for gpio in all_gpio:
        if gpio in used:
            continue
        if reserve_usb and gpio in usb:
            continue

        score = 0
        reasons = []

        # Base preference ordering
        if gpio in preferred_order:
            score += 10
            reasons.append("preferred_free_pin")

        # Strong preference: recommended pins for this bus role
        if gpio in bus_rec:
            score += 50
            reasons.append(f"recommended_for_{bus_role}")

        # Avoid strapping pins, especially for sensitive roles
        if gpio in strapping:
            if strict_avoid_boot or _is_sensitive_role(role):
                score -= 100
                reasons.append("strapping_pin_avoided")
            else:
                score -= 25
                reasons.append("strapping_pin_less_preferred")

        # Small general preference: lower GPIO numbers aren’t inherently better,
        # but deterministic tie-break helps
        score -= gpio // 50  # basically no-op, keeps stable-ish

        candidates.append(
            PinPick(
                gpio=gpio,
                reason=";".join(reasons) if reasons else "fallback_available_pin",
                score=score,
            )
        )

    # Higher score first, deterministic tie-break by gpio
    candidates.sort(key=lambda x: (-x.score, x.gpio))
    return candidates


def generate_pinmap(
    *,
    board_profile_path: str,
    peripheral_profile_paths: List[str],
    reserve_usb_serial_jtag: bool = True,
    strict_avoid_boot_pins: bool = True,
) -> Dict[str, Any]:
    """
    Generate a pin map for one board + one or more peripherals.

    Returns:
      dict with:
        - board_id
        - peripherals
        - assignments (role -> gpio)
        - rationale (role -> reason)
        - warnings
    """
    board = _load_json(board_profile_path)
    peripherals = [_load_json(p) for p in peripheral_profile_paths]

    used: set[int] = set()
    assignments: Dict[str, int] = {}
    rationale: Dict[str, str] = {}
    warnings: List[str] = []

    # Flatten required pins from all peripherals
    required_pin_items: List[Tuple[str, dict]] = []
    for per in peripherals:
        for pin in _collect_required_pins(per):
            role = pin["role"]
            required_pin_items.append((per["id"], pin))

    # A simple ordering rule: assign bus pins first, then control pins
    def sort_key(item: Tuple[str, dict]) -> int:
        role = item[1]["role"]
        bus_role = _role_to_bus_role(item[1])
        if bus_role:
            return 0
        if role in {"CS", "DC", "RST"}:
            return 1
        return 2

    required_pin_items.sort(key=sort_key)

    for per_id, pin_desc in required_pin_items:
        role = pin_desc["role"]
        bus_role = _role_to_bus_role(pin_desc)

        # Avoid collisions if two peripherals have same role name:
        # namespace it like "epaper_spi_2p13.CS"
        key = f"{per_id}.{role}"

        candidates = _rank_candidates(
            role=role,
            bus_role=bus_role,
            board=board,
            used=used,
            reserve_usb=reserve_usb_serial_jtag,
            strict_avoid_boot=strict_avoid_boot_pins,
        )

        if not candidates:
            raise RuntimeError(f"No available GPIO pins left for {key}")

        pick = candidates[0]
        assignments[key] = pick.gpio
        rationale[key] = pick.reason
        used.add(pick.gpio)

        # Warn if we had to choose a strapping pin anyway
        strapping = set(board.get("strapping_pins", {}).get("pins", []))
        if pick.gpio in strapping:
            warnings.append(
                f"{key} mapped to strapping pin GPIO{pick.gpio}. "
                f"Check boot/reset behavior and external pull resistors."
            )

    return {
        "board_id": board.get("id"),
        "board_name": board.get("name"),
        "peripherals": [p.get("id") for p in peripherals],
        "assignments": assignments,
        "rationale": rationale,
        "warnings": warnings,
        "options": {
            "reserve_usb_serial_jtag": reserve_usb_serial_jtag,
            "strict_avoid_boot_pins": strict_avoid_boot_pins,
        },
    }
