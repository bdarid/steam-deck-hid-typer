# Steam Deck USB HID Text Typer

A small Python utility for testing USB HID keyboard input from a Steam Deck running SteamOS/Linux. It can create a USB keyboard gadget and type a **plain text test file** into a focused editor.

> **Scope:** This repository documents generic keyboard-emulation and harmless text-entry tests. It does not provide instructions for injecting or running console exploits. Test only with text you own and a device you are authorized to configure.

## Features

- Creates a Linux USB HID keyboard gadget using `configfs`.
- Types a UTF-8 text file using a US-layout keyboard map.
- Optional F7 key press before typing.
- Optional Caps Lock compensation for alphabetic characters.
- Configurable key, modifier, line, and startup delays.
- Preflight validation refuses to type unsupported characters rather than silently dropping them.
- Includes harmless test files for checking case, punctuation, and line breaks.

## Requirements

- Steam Deck in Desktop Mode (or another Linux system with compatible USB gadget support).
- Python 3.
- A USB-C port that can operate in device/peripheral mode and exposes a USB Device Controller at `/sys/class/udc`.
- A data-capable USB cable and a host device that accepts standard USB HID keyboard input.
- `sudo` access.

Not every SteamOS/kernel/USB-C configuration exposes USB gadget mode. If `/sys/class/udc` is empty, the setup command will not work; do not install random drivers or change unrelated firmware settings to force it.

## Files

- `hid_typer_reliable.py` — the HID gadget and text-typing utility.
- `typing_stress_test.bas` — harmless multiline editor test; do not run it as a program.
- `hid_typing_case_test.txt` — short capitalization/punctuation test.
- `typing_3min_test.txt` — sample text for estimating timing; actual runtime depends on character composition and delay values.

Only add other source files if you wrote them yourself or have permission and a license that allows redistribution. In particular, don't rehost third-party bootstrap/exploit code unless its license or the author's permission explicitly allows it. Link to its original project instead.

## Setup

From the folder containing `hid_typer_reliable.py`, create the keyboard gadget:

```bash
sudo python3 hid_typer_reliable.py setup
```

Check that the HID device exists:

```bash
ls -l /dev/hidg0
```

If setup fails or `/dev/hidg0` is absent, stop and inspect the error. Do not assume the gadget is active just because the script ran.

## Safe text-entry test

1. Connect the Steam Deck to a host using a data-capable cable.
2. Open a blank text editor/program editor on the host and leave it focused.
3. Run the harmless stress test. `--press-f7` sends F7 before typing, so use it only when F7 is the intended editor shortcut on the host.

```bash
sudo python3 hid_typer_reliable.py type typing_stress_test.bas --press-f7 --caps-lock-on --start-delay 20 --key-delay 0.25 --mod-delay 0.20 --line-delay 1.5 --strip-indent
```

Inspect the resulting text against the original file. **The script cannot verify that the host received every character.** Keep the target visible during testing, and stop if characters are missing, symbols are wrong, or lines merge. Fast delay values are unverified and can lose keystrokes; do not assume that a shorter runtime is accurate.

### Options

- `--start-delay` — countdown before typing starts.
- `--key-delay` — time for key press/release handling.
- `--mod-delay` — additional wait around modifier-key handling.
- `--line-delay` — extra pause after each newline.
- `--press-f7` — send F7 before typing.
- `--caps-lock-on` — invert Shift handling for letters for the tested Caps Lock behavior.
- `--strip-indent` — remove leading spaces/tabs from each input line. Use only when that behavior is desired; it changes the text being typed.

The keyboard mapping assumes a US layout. Punctuation may differ on hosts configured for another layout.

## Cleanup

After testing, remove the keyboard gadget:

```bash
sudo python3 hid_typer_reliable.py teardown
```

Then verify:

```bash
test ! -e /dev/hidg0 && echo "HID device removed"
```

The script attempts to set an exposed USB role switch to `device` during setup; it does not automatically restore the role that was active before setup. Check your device's state after cleanup and reboot if needed.


This project changes USB gadget configuration and sends keystrokes to whichever device has focus. Review the code, use a harmless test file first, and keep the host visible. No guarantee is made that every character will be delivered correctly on every device or configuration.
