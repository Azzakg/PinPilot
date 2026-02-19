{
  "device_name": "smart_shelf_tag",
  "board": "esp32-c3",
  "peripherals": [
    { "id": "epaper_spi_2p13" },
    { "id": "bme280_i2c" },
    { "id": "ws2812", "alias": "status_led" }
  ],
  "power": {
    "source": "battery",
    "voltage": 3.7,
    "deep_sleep_required": true
  },
  "connectivity": {
    "type": "wifi",
    "protocol": "mqtt"
  }
}
