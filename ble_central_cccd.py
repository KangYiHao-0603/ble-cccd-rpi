#!/usr/bin/env python3
"""
HW3 - BLE Central on Raspberry Pi (bluepy)
  Tested on Raspberry Pi 4 (Raspberry Pi OS, Debian trixie) with an iPhone running
  LightBlue (Virtual Device) as the GATT server. Also works with Android BLE Tool / nRF Connect.

  1. Scan for BLE peripherals (the phone acting as a GATT server)
  2. Connect and discover services / characteristics
  3. Find a characteristic with INDICATE property and write 0x0002 to its CCCD (0x2902)
  4. Read the CCCD back, write a test string, then wait for indications

Usage:
  sudo python3 ble_central_cccd.py                 # auto-pick first custom char with INDICATE
  sudo python3 ble_central_cccd.py <char-uuid>     # or specify the target characteristic UUID
"""
import sys
import time
from bluepy.btle import (Scanner, DefaultDelegate, Peripheral, UUID,
                         Characteristic, BTLEException, BTLEManagementError)

CCCD_UUID = UUID(0x2902)
# Generic Access / Generic Attribute services: skip them
# (0x1801 contains "Service Changed", which also has INDICATE)
SKIP_SERVICES = {
    UUID(0x1800), UUID(0x1801),
    UUID(0x1805), UUID(0x180A),                       # Current Time, Device Info (iPhone)
    UUID("7905f431-b5ce-4e99-a40f-4b1e122d00d0"),     # Apple ANCS
    UUID("89d3502b-0f36-433a-8ef4-c502ad55f8dc"),     # Apple Media Service
    UUID("d0611e78-bbb4-4591-a5f8-487910ae4366"),     # Apple Continuity
    UUID("9fa480e0-4967-4542-9390-d343dc5d04ae"),     # Apple Nearby
}


class ScanDelegate(DefaultDelegate):
    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print(f"Discovered {dev.addr} ({dev.addrType}) RSSI={dev.rssi}")


class NotifyDelegate(DefaultDelegate):
    def handleNotification(self, cHandle, data):
        print(f"[Indication] handle=0x{cHandle:04x} data={data.hex()} ({data!r})")


def scan(timeout=10.0):
    scanner = Scanner().withDelegate(ScanDelegate())
    scanner.clear()
    scanner.start()
    scanner.process(timeout)
    try:
        scanner.stop()
    except BTLEManagementError as e:
        # Newer BlueZ sometimes rejects 'scanend'; results are still valid
        print(f"(warning) stop scan failed, ignored: {e}")
    devices = list(scanner.getDevices())
    print("\n=== Scan result ===")
    for i, d in enumerate(devices):
        name = d.getValueText(9) or d.getValueText(8) or "(no name)"
        print(f"[{i}] {d.addr} {d.addrType:6s} RSSI={d.rssi:4d}  name={name}")
    return devices


def find_target(p, want_uuid=None):
    target, writable = None, None
    for svc in p.getServices():
        print(f"Service {svc.uuid}")
        for ch in svc.getCharacteristics():
            print(f"    Char {ch.uuid}  handle=0x{ch.getHandle():04x}  "
                  f"props={ch.propertiesToString()}")
            if svc.uuid in SKIP_SERVICES:
                continue
            if want_uuid is not None:
                if ch.uuid == want_uuid:
                    target = ch
            elif target is None and ch.properties & Characteristic.props["INDICATE"]:
                target = ch
            if writable is None and ch.properties & (Characteristic.props["WRITE"] |
                                                     Characteristic.props["WRITE_NO_RESP"]):
                writable = ch
    return target, writable


def main():
    want_uuid = UUID(sys.argv[1]) if len(sys.argv) > 1 else None

    devices = scan()
    if not devices:
        print("No device found.")
        return
    dev = devices[int(input("\nSelect device index: "))]

    print(f"\nConnecting to {dev.addr} ({dev.addrType}) ...")
    p = Peripheral(dev.addr, dev.addrType)
    p.setDelegate(NotifyDelegate())
    try:
        target, writable = find_target(p, want_uuid)
        if target is None:
            print("\nNo suitable characteristic (need INDICATE property). "
                  "Check the service you added in the phone app.")
            return

        descs = target.getDescriptors(forUUID=CCCD_UUID)
        cccd_handle = descs[0].handle if descs else target.getHandle() + 1
        print(f"\nTarget char {target.uuid}, CCCD handle = 0x{cccd_handle:04x}")

        print("Before:", p.readCharacteristic(cccd_handle).hex())
        # CCCD is little-endian: 0x0002 -> bytes 02 00  (0x0001 = notify, 0x0002 = indicate)
        p.writeCharacteristic(cccd_handle, b"\x02\x00", withResponse=True)
        val = p.readCharacteristic(cccd_handle)
        print(f"After : {val.hex()}  -> CCCD = 0x{int.from_bytes(val, 'little'):04x}")

        if writable is not None:
            msg = b"Hello from RPi3"  # kept identical to the demo screenshots
            writable.write(msg, withResponse=True)
            print(f"Wrote {msg!r} to {writable.uuid}")

        print("\nWaiting for indications (30 s) ... send a value from the phone app now.")
        end = time.time() + 30
        while time.time() < end:
            p.waitForNotifications(1.0)
    except BTLEException as e:
        print("BLE error:", e)
    finally:
        p.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
