from engines.pinmapper import generate_pinmap

result = generate_pinmap(
    board_profile_path="data/boards/esp32c3.json",
    peripheral_profile_paths=["data/peripherals/epaper_spi_2p13.json"],
)

print(result)
