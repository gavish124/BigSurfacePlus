# BigSurface on the Surface Laptop 5 (Alder Lake-P, macOS Tahoe 26)

The keyboard, trackpad and battery work on the Surface Laptop 5 (i5-1235U) with BigSurface.

**The BigSurface source itself is unchanged.** All the changes are in two of its dependencies (VoodooSerial and VoodooGPIO) and one SSDT:

| What | Why |
| --- | --- |
| **VoodooSerial**: match the Alder Lake-P UART0 (PCI `8086:51a8`) and set its clock | The Surface Aggregator Module (SAM) talks to the OS over this UART. Upstream only knows Ice Lake (`34a8`) and Kaby Lake (`9d27`) UARTs. The ADL-P LPSS clock is 100 MHz, and the driver assumes 64 MHz, so the M/N divider is set to 16/25. |
| **VoodooGPIO**: add the Tiger Lake-LP pin tables (ACPI `INTC1055`, `INT34C5`) | The SAM interrupt is a GPIO pin. ADL-P uses the same GPIO layout as Tiger Lake-LP (Linux uses the TGL driver for it too). The tables come from VoodooI2C/VoodooGPIO `d415406`, changed to the base class of BigSurface's VoodooGPIO fork. |
| **SSDT-SAM** | The firmware's SAM device (`\_SB.SSH`, `MSHW0084`) lives in an SSDT ("SsdtSurf") that isn't present when macOS boots through OpenCore. SSDT-SAM re-creates it as `SSHM` with the same resources, for macOS only. |

## Files

- `build-bigsurface-sl5.py`: fetches BigSurface `8282631` (with its pinned submodules) and VoodooGPIO `d415406`, applies the changes and builds the five kexts **with the Xcode Command Line Tools only** (no Xcode). Run `python3 build-bigsurface-sl5.py`; the kexts end up in `~/Downloads/bigsurface-sl5/out`.
- `patches/VoodooSerial-AlderLake-P-UART.patch`: the change to `Dependencies/VoodooSerial` (git diff, apply inside that submodule with `git apply`).
- `patches/VoodooGPIO-TigerLake-LP.patch`: the change to `Dependencies/VoodooGPIO`. If you build with Xcode instead of the script, also add the new `TigerLake-LP` folder to the VoodooGPIO target.
- `ACPI/SSDT-SAM.dsl` / `.aml`: the SSDT (source and compiled).

## OpenCore config

- Kernel → Add, in this order, after Lilu and VirtualSMC: `VoodooGPIO`, `VoodooSerial`, `VoodooInput`, `BigSurface`, `BigSurfaceHIDDriver`.
- Disable `VoodooI2C*`, any other `VoodooInput`, `SMCBatteryManager` and `SMCLightSensor` (BigSurface provides the battery and light sensor).
- ACPI → Add: `SSDT-SAM.aml`.
- SMBIOS: `MacBookPro16,2`. System Settings shows the **Battery** pane only for a laptop model. With a desktop model it shows **Energy** even though the battery itself works.

## Porting to another Surface

Everything device-specific is in the three changes above:

1. **The SAM device's resources.** In a Windows ACPI dump, find the device with `_HID "MSHW0084"` and copy its `_CRS` into SSDT-SAM: the UART controller path (here `\_SB.PC00.UA00`), baud rate and flow control, and the GPIO pin (here `0xAE`). If your firmware already exposes `MSHW0084` to macOS (check the IOACPIPlane), you don't need the SSDT.
2. **The UART's PCI ID and clock.** If your UART isn't `51a8`, add its ID to VoodooSerial's `IOPCIMatch` and give it the right clock in `startUARTClock()` (64 MHz from whatever the LPSS input clock is).
3. **The GPIO controller.** `INTC1055`/`INT34C5` use the Tiger Lake-LP tables. Other platforms need their own tables.

The keyboard and trackpad themselves are BigSurfaceHIDDriver, which is unchanged.

## Credits

BigSurface, VoodooSerial and VoodooGPIO fork by Xiashangning; VoodooGPIO by CoolStar and the VoodooI2C team (Tiger Lake-LP tables); linux-surface for documenting the SAM protocol.
