"""Reset an Arctis Nova Pro Wireless base station stuck in its USB bootloader."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

try:
    import hid
except ImportError:
    print(
        "Missing dependency: hidapi\n"
        "Install it with: py -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)


VID_STEELSERIES = 0x1038
PID_BASE_NORMAL = 0x12E0
PID_BASE_BOOTLOADER = 0x12E1
EXPECTED_PRODUCT = "SteelSeries Bootloader"
EXPECTED_USAGE_PAGE = 0xFFFF


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def path_label(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="backslashreplace")
    return str(value)


def enumerate_devices(pid: int) -> list[dict[str, Any]]:
    return list(hid.enumerate(VID_STEELSERIES, pid))


def describe(device: dict[str, Any]) -> str:
    usage_page = device.get("usage_page")
    usage = device.get("usage")
    return (
        f"{VID_STEELSERIES:04X}:{int(device.get('product_id', 0)):04X}  "
        f"{text(device.get('product_string')) or '(no product string)'}  "
        f"usage_page=0x{int(usage_page or 0):04X} "
        f"usage=0x{int(usage or 0):04X}\n"
        f"  path: {path_label(device.get('path'))}"
    )


def inspect() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bootloaders = enumerate_devices(PID_BASE_BOOTLOADER)
    normal = enumerate_devices(PID_BASE_NORMAL)

    print("Base bootloader interfaces (1038:12E1):")
    if bootloaders:
        for device in bootloaders:
            print(describe(device))
    else:
        print("  none")

    print("\nNormal base interfaces (1038:12E0):")
    if normal:
        for device in normal:
            print(describe(device))
    else:
        print("  none")

    return bootloaders, normal


def select_target(devices: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        device
        for device in devices
        if text(device.get("product_string")) == EXPECTED_PRODUCT
        and int(device.get("usage_page") or 0) == EXPECTED_USAGE_PAGE
    ]

    if len(candidates) != 1:
        raise RuntimeError(
            "Refusing recovery: expected exactly one 1038:12E1 vendor HID "
            f"interface named {EXPECTED_PRODUCT!r}, found {len(candidates)}."
        )
    return candidates[0]


def send_feature(path: Any, packet: bytes, label: str) -> list[int]:
    device = hid.device()
    try:
        device.open_path(path)
        sent = device.send_feature_report(packet)
        if sent <= 0:
            raise RuntimeError(f"{label} feature report was not accepted")
        print(f"{label}: sent {sent} bytes")
        return list(device.read(64, 2000))
    finally:
        device.close()


def wait_for_normal(timeout: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if enumerate_devices(PID_BASE_NORMAL):
            return True
        time.sleep(0.25)
    return False


def reset(target: dict[str, Any]) -> None:
    path = target["path"]

    handshake = bytes((0x06, 0xB0)) + bytes(1022)
    ack = send_feature(path, handshake, "Handshake 06 B0")
    if not ack:
        raise RuntimeError("Bootloader did not acknowledge the handshake")
    print(f"Handshake response: {bytes(ack).hex()}")
    if len(ack) < 2 or ack[0:2] != [0x06, 0xB0]:
        raise RuntimeError(
            "Unexpected handshake response; reset was not sent: "
            f"{bytes(ack).hex()}"
        )

    # The successful manual recovery closed and reopened the HID handle between
    # handshake and reset. send_feature() deliberately preserves that behavior.
    reset_packet = bytes((0x06, 0xBB)) + bytes(62)
    response = send_feature(path, reset_packet, "Reset 06 BB")
    if response:
        print(f"Reset response: {bytes(response).hex()}")
    else:
        print("Reset response: device disconnected before replying (expected)")

    print("Waiting for the normal base station (1038:12E0)...")
    if not wait_for_normal():
        raise RuntimeError(
            "The normal 1038:12E0 device did not appear. The base may have "
            "returned to its bootloader or may require a USB power cycle."
        )
    print("Success: the base station is present in normal 1038:12E0 mode.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--inspect", action="store_true", help="enumerate relevant devices only"
    )
    action.add_argument(
        "--reset", action="store_true", help="send the handshake and reset commands"
    )
    parser.add_argument(
        "--yes", action="store_true", help="skip the interactive RESET confirmation"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bootloaders, normal = inspect()

    if args.inspect:
        return 0

    if normal:
        print(
            "\nRefusing recovery: a normal 1038:12E0 base interface is already "
            "present.",
            file=sys.stderr,
        )
        return 2

    try:
        target = select_target(bootloaders)
        print("\nSelected recovery target:\n" + describe(target))
        if not args.yes:
            answer = input("\nType RESET to send the handshake and reset command: ")
            if answer != "RESET":
                print("Cancelled; nothing was sent.")
                return 1
        reset(target)
    except (OSError, RuntimeError) as error:
        print(f"\nRecovery failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

