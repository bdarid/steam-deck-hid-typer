#!/usr/bin/env python3
"""USB HID keyboard gadget and cautious text typer for Steam Deck / Linux.

Commands (run in Desktop Mode):
  sudo python3 hid_typer_reliable.py setup
  sudo python3 hid_typer_reliable.py type harmless-test.txt --press-f7 --caps-lock-on
  sudo python3 hid_typer_reliable.py teardown

Use a harmless test file first. The script types text only; it does not run it.
"""
import argparse
import glob
import os
import sys
import time

GADGET = "/sys/kernel/config/usb_gadget/g_typer"
HID_DEV = "/dev/hidg0"

REPORT_DESC = bytes([
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01,
    0x75, 0x08, 0x81, 0x03, 0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01,
    0x29, 0x05, 0x91, 0x02, 0x95, 0x01, 0x75, 0x03, 0x91, 0x03, 0x95, 0x06,
    0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65,
    0x81, 0x00, 0xC0,
])


def write_text(path, data, mode="w"):
    with open(path, mode) as f:
        f.write(data)


def require_root():
    if os.geteuid() != 0:
        sys.exit("Run with sudo, for example: sudo python3 hid_typer_reliable.py setup")


def setup():
    if os.path.isdir(GADGET):
        print(f"Gadget directory already exists: {GADGET}")
        print("If it was created by this script, run teardown, then setup again.")
        return

    os.system("modprobe libcomposite 2>/dev/null")
    if not os.path.isdir("/sys/kernel/config"):
        os.system("mount -t configfs none /sys/kernel/config")

    # Best effort: ask any exposed USB role switch to use device/peripheral mode.
    for role_path in glob.glob("/sys/class/usb_role/*/role"):
        try:
            write_text(role_path, "device")
            print(f"Set USB role to device: {role_path}")
        except OSError as exc:
            print(f"Could not set {role_path}: {exc}")

    os.makedirs(GADGET + "/strings/0x409", exist_ok=True)
    os.makedirs(GADGET + "/configs/c.1/strings/0x409", exist_ok=True)
    os.makedirs(GADGET + "/functions/hid.usb0", exist_ok=True)
    write_text(GADGET + "/idVendor", "0x1d6b")
    write_text(GADGET + "/idProduct", "0x0104")
    write_text(GADGET + "/bcdUSB", "0x0200")
    write_text(GADGET + "/strings/0x409/serialnumber", "0001")
    write_text(GADGET + "/strings/0x409/manufacturer", "Generic")
    write_text(GADGET + "/strings/0x409/product", "USB Keyboard")
    write_text(GADGET + "/configs/c.1/strings/0x409/configuration", "HID")
    write_text(GADGET + "/configs/c.1/MaxPower", "100")

    function = GADGET + "/functions/hid.usb0"
    write_text(function + "/protocol", "1")
    write_text(function + "/subclass", "1")
    write_text(function + "/report_length", "8")
    write_text(function + "/report_desc", REPORT_DESC, "wb")
    link = GADGET + "/configs/c.1/hid.usb0"
    if not os.path.islink(link):
        os.symlink(function, link)

    try:
        controllers = os.listdir("/sys/class/udc")
    except OSError as exc:
        sys.exit(f"Cannot read /sys/class/udc: {exc}")
    if not controllers:
        sys.exit("No UDC found. USB device mode is not exposed by the current kernel.")

    write_text(GADGET + "/UDC", controllers[0])
    print(f"HID keyboard ready using UDC {controllers[0]}; check with: ls -l /dev/hidg0")


def teardown():
    if not os.path.isdir(GADGET):
        print("Nothing to remove.")
        return
    try:
        write_text(GADGET + "/UDC", "")
    except OSError:
        pass
    link = GADGET + "/configs/c.1/hid.usb0"
    if os.path.islink(link):
        os.unlink(link)
    directories = [
        GADGET + "/configs/c.1/strings/0x409",
        GADGET + "/configs/c.1",
        GADGET + "/functions/hid.usb0",
        GADGET + "/strings/0x409",
        GADGET,
    ]
    for directory in directories:
        try:
            os.rmdir(directory)
        except OSError as exc:
            print(f"Could not remove {directory}: {exc}")
    print("Gadget teardown attempted. Confirm with: test ! -e /dev/hidg0 && echo removed")


# US-layout ASCII -> (needs Shift, USB HID usage code).
KEYS = {}
for index, char in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEYS[char] = (False, 0x04 + index)
    KEYS[char.upper()] = (True, 0x04 + index)
for index, char in enumerate("1234567890"):
    KEYS[char] = (False, 0x1E + index)
for char, code in zip("!@#$%^&*()", range(0x1E, 0x28)):
    KEYS[char] = (True, code)
for pair, code in {
    "-_": 0x2D, "=+": 0x2E, "[{": 0x2F, "]}": 0x30, "\\|": 0x31,
    ";:": 0x33, "'\"": 0x34, "`~": 0x35, ",<": 0x36, ".>": 0x37, "/?": 0x38,
}.items():
    KEYS[pair[0]] = (False, code)
    KEYS[pair[1]] = (True, code)
KEYS[" "] = (False, 0x2C)
KEYS["\n"] = (False, 0x28)
KEYS["\t"] = (False, 0x2B)


def send_report(fd, modifier=0, key=0):
    os.write(fd, bytes([modifier, 0, key, 0, 0, 0, 0, 0]))


def release_all(fd):
    os.write(fd, bytes(8))


def type_file(path, start_delay, key_delay, mod_delay, line_delay,
              strip_indent, press_f7, caps_lock_on):
    try:
        with open(path, "r", encoding="utf-8", newline="") as source:
            text = source.read()
    except OSError as exc:
        sys.exit(f"Cannot read {path}: {exc}")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if strip_indent:
        text = "\n".join(line.lstrip(" \t") for line in text.split("\n"))

    bad = sorted({char for char in text if char not in KEYS})
    if bad:
        printable = ", ".join(repr(char) for char in bad)
        sys.exit("Refusing to type: unsupported characters would be lost: " + printable)

    if not os.path.exists(HID_DEV):
        sys.exit(f"{HID_DEV} is missing. Run setup first and check that the gadget is active.")

    line_count = len(text.splitlines())
    print(f"Preflight OK: {len(text)} characters across {line_count} lines; no unsupported characters.")
    if caps_lock_on:
        print("Caps Lock compensation enabled: alphabetic Shift handling will be inverted.")
    print("Focus the SmileBASIC editor. Press Ctrl+C here to cancel before the countdown ends.")
    for seconds in range(int(start_delay), 0, -1):
        print(f"  {seconds}", flush=True)
        time.sleep(1)

    try:
        fd = os.open(HID_DEV, os.O_WRONLY)
    except OSError as exc:
        sys.exit(f"Cannot open {HID_DEV}: {exc}")

    try:
        if press_f7:
            send_report(fd, 0, 0x40)  # USB HID usage ID 0x40 = F7
            time.sleep(0.15)
            release_all(fd)
            time.sleep(2.0)

        for index, char in enumerate(text, start=1):
            shift, code = KEYS[char]
            if caps_lock_on and char.isalpha():
                shift = not shift

            if shift:
                # Separate Shift-down report helps slower target editors register modifiers.
                send_report(fd, 0x02, 0)
                time.sleep(mod_delay)
                send_report(fd, 0x02, code)
                time.sleep(key_delay)
                send_report(fd, 0x02, 0)
                time.sleep(key_delay)
                release_all(fd)
                time.sleep(mod_delay)
            else:
                send_report(fd, 0, code)
                time.sleep(key_delay)
                release_all(fd)
                time.sleep(key_delay)

            if char == "\n":
                time.sleep(line_delay)
            if index % 250 == 0:
                print(f"Typed {index}/{len(text)} characters", flush=True)
    except KeyboardInterrupt:
        print("\nInterrupted. Releasing all keys.")
    finally:
        try:
            release_all(fd)
        finally:
            os.close(fd)
    print("Typing finished. Inspect the editor before running anything.")


def main():
    require_root()
    parser = argparse.ArgumentParser(description="Steam Deck USB HID keyboard helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup", help="create the USB HID keyboard gadget")
    subparsers.add_parser("teardown", help="remove the USB HID keyboard gadget")
    type_parser = subparsers.add_parser("type", help="type a UTF-8 text file")
    type_parser.add_argument("file")
    type_parser.add_argument("--start-delay", type=float, default=20.0)
    type_parser.add_argument("--key-delay", type=float, default=0.12)
    type_parser.add_argument("--mod-delay", type=float, default=0.12)
    type_parser.add_argument("--line-delay", type=float, default=0.8)
    type_parser.add_argument("--strip-indent", action="store_true")
    type_parser.add_argument("--press-f7", action="store_true", help="send F7 before typing")
    type_parser.add_argument("--caps-lock-on", action="store_true", help="invert Shift for letters when host Caps Lock is on")
    args = parser.parse_args()

    if args.command == "setup":
        setup()
    elif args.command == "teardown":
        teardown()
    else:
        type_file(args.file, args.start_delay, args.key_delay, args.mod_delay,
                  args.line_delay, args.strip_indent, args.press_f7, args.caps_lock_on)


if __name__ == "__main__":
    main()
