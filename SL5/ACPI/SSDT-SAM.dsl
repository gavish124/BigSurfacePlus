/*
 * Surface Laptop 5: the firmware's "SsdtSurf" table (which defines the Surface
 * Serial Hub \_SB.SSH, MSHW0084) is not present when macOS boots through OpenCore.
 * This re-creates only the hub under a different name (SSHM) so BigSurface's
 * SurfaceSerialHubDriver (IONameMatch MSHW0084) has something to attach to.
 * Resources copied from the firmware table: UART0 (\_SB.PC00.UA00) at 4,000,000 baud,
 * 8N1, hardware flow control, 64-byte buffers; wake/IRQ on GPIO pin 0xAE.
 * Enabled for macOS only, so Windows booted from OpenCore is unaffected.
 */
DefinitionBlock ("", "SSDT", 2, "HACK", "SL5SAM", 0x00001000)
{
    External (_SB_.GPI0, DeviceObj)
    External (_SB_.PC00.UA00, DeviceObj)

    Scope (\_SB)
    {
        Device (SSHM)
        {
            Name (_HID, "MSHW0084")  // _HID: Hardware ID
            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }

                Return (Zero)
            }

            Method (_CRS, 0, NotSerialized)  // _CRS: Current Resource Settings
            {
                Return (ResourceTemplate ()
                {
                    UartSerialBusV2 (0x003D0900, DataBitsEight, StopBitsOne,
                        0xC0, LittleEndian, ParityTypeNone, FlowControlHardware,
                        0x0040, 0x0040, "\\_SB.PC00.UA00",
                        0x00, ResourceConsumer, , Exclusive,
                        )
                    GpioInt (Edge, ActiveHigh, SharedAndWake, PullNone, 0x0000,
                        "\\_SB.GPI0", 0x00, ResourceConsumer, ,
                        )
                        {   // Pin list
                            0x00AE
                        }
                    GpioIo (Shared, PullNone, 0x0000, 0x0000, IoRestrictionInputOnly,
                        "\\_SB.GPI0", 0x00, ResourceConsumer, ,
                        )
                        {   // Pin list
                            0x00AE
                        }
                })
            }
        }
    }
}
