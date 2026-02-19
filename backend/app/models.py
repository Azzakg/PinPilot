from pydantic import BaseModel, Field
from typing import List, Optional


class PowerConfig(BaseModel):
    source: str = Field(
        ...,
        description="battery | usb | external"
    )
    voltage: float = Field(
        default=3.7,
        description="Battery nominal voltage"
    )
    deep_sleep_required: bool = True


class ConnectivityConfig(BaseModel):
    type: str = Field(
        ...,
        description="wifi | ble | lora"
    )
    protocol: Optional[str] = Field(
        default="mqtt",
        description="mqtt | http | websocket"
    )


class PeripheralConfig(BaseModel):
    id: str = Field(
        ...,
        description="Must match peripheral JSON profile"
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional name for multiple instances"
    )


class HardwareIntent(BaseModel):

    device_name: str = Field(
        default="pinpilot_device"
    )

    board: str = Field(
        ...,
        description="Must match board profile ID"
    )

    peripherals: List[PeripheralConfig] = Field(
        ...,
        description="List of peripherals"
    )

    power: PowerConfig

    connectivity: ConnectivityConfig

    reserve_usb_serial_jtag: bool = True
    strict_avoid_boot_pins: bool = True
