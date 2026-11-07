# Arctis Nova Pro Wireless Base-Station Recovery

A narrowly scoped recovery tool for a SteelSeries Arctis Nova Pro Wireless base
station that is permanently enumerating as the SteelSeries bootloader
(`1038:12E1`) instead of its normal USB device (`1038:12E0`).

This tool **does not flash firmware**. It sends the bootloader handshake followed
by its reset command, allowing an intact application image to boot again.

## Credit to Timpan4

This recovery exists thanks to
[Timpan4/steelseries-unbrick](https://github.com/Timpan4/steelseries-unbrick).
Timpan4 reverse-engineered and publicly documented the Nova Pro bootloader
handshake, flash packet format, acknowledgements, and reset command from
SteelSeries' updater. That research supplied the crucial protocol knowledge
behind this project and saved a substantial amount of independent
reverse-engineering work.

Timpan4's published tool targets the headset MCU through the `12E2 -> 12E3`
path. This repository is a small, safety-focused adaptation of that research
for a base station already stranded in its separate `12E1` bootloader.

## When this applies

The recovery was developed for this specific state:

- The base-station OLED says `FIRMWARE UPDATE AVAILABLE`.
- Its wheel does not respond.
- SteelSeries GG offers an update but does not start it.
- Windows sees `VID 1038, PID 12E1`, product string
  `SteelSeries Bootloader`.
- The base remains in `12E1` after a complete USB power cycle.

Do not use this for a headset bootloader (`12E3`), an Xbox model, a different
SteelSeries product, or a base station already operating normally as `12E0`.

## What the recovery sends

1. A 1024-byte HID feature report beginning `06 B0` (bootloader handshake).
2. A 64-byte HID feature report beginning `06 BB` (reset).
3. No erase or firmware-write command is implemented.

The tool refuses to continue unless exactly one matching `1038:12E1` HID device
is present and its product string is `SteelSeries Bootloader`. After resetting,
it waits for a `1038:12E0` HID interface to appear.

## Requirements

- Windows 10 or 11
- Python 3
- [`hidapi`](https://pypi.org/project/hidapi/)
- The non-Xbox Arctis Nova Pro Wireless base station connected by USB

Close SteelSeries GG completely before recovery so that it does not hold or
reconnect to the HID interface during the reset.

## Read-only check

Open PowerShell in this directory:

```powershell
py -m pip install -r requirements.txt
py recover.py --inspect
```

The expected recovery target resembles:

```text
1038:12E1  SteelSeries Bootloader  usage_page=0xFFFF
```

## Reset the bootloader

```powershell
py recover.py --reset
```

The script displays the selected device and asks you to type `RESET` before it
sends anything. A successful recovery ends with a normal `1038:12E0` interface
being detected. Reopen SteelSeries GG only after that succeeds.

For a non-interactive run after reviewing the target:

```powershell
py recover.py --reset --yes
```

## Original commands used during recovery

For historical reproducibility, the successful manual sequence was equivalent
to:

```powershell
py -c "import hid,time; x=hid.enumerate(0x1038,0x12E1)[0]; d=hid.device(); d.open_path(x['path']); pkt=bytes([0x06,0xB0])+bytes(1022); print('sent:',d.send_feature_report(pkt)); time.sleep(0.1); r=d.read(64,2000); print('ack:',bytes(r).hex() if r else 'NO RESPONSE'); d.close()"

py -c "import hid,time; x=hid.enumerate(0x1038,0x12E1)[0]; d=hid.device(); d.open_path(x['path']); pkt=bytes([0x06,0xBB])+bytes(62); print('sent:',d.send_feature_report(pkt)); time.sleep(0.2); r=d.read(64,1000); print('ack:',bytes(r).hex() if r else 'NO RESPONSE'); d.close()"
```

Use `recover.py` instead: it adds target validation, confirmation, diagnostics,
and post-reset verification that the one-liners lack.

## What this does not fix

This reset only works when the application firmware already stored on the base
station is bootable. If the device resets and returns to `12E1`, its application
image may be absent or invalid; firmware flashing is a separate and riskier
operation and is intentionally outside this repository's scope.

## Background and attribution

The shared Nova Pro bootloader protocol and the key `06 B0` handshake were
reverse-engineered and first documented publicly by
[Timpan4/steelseries-unbrick](https://github.com/Timpan4/steelseries-unbrick).
That project also provided the practical proof that the protocol could recover
real Nova Pro hardware outside SteelSeries GG.

Building on that work, this repository applies the independently verified
handshake/reset portion to the base station's `12E0 -> 12E1` path. Inspection
of SteelSeries GG's local `SSEdevice.dll` confirmed the base-specific boot-entry
command `06 EB`, the shared `06 B0` handshake, and `06 BB` reset. Only the
latter two are used here because the affected base station is already in
`12E1` bootloader mode.

## Disclaimer

This is an unofficial recovery utility and is not affiliated with or endorsed
by SteelSeries. It sends commands directly to hardware. Although it contains no
firmware flashing functionality, use it at your own risk.

## Personal note

I'm never buying another SteelSeries product after having to do this.
Steelseries is an absolute disgrace.

