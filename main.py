import time
import screen_brightness_control as sbc
from pynput import keyboard

from ctypes import (
    windll,
    byref,
    Structure,
    WinError,
    POINTER,
    WINFUNCTYPE
)

from ctypes.wintypes import (
    BOOL,
    HMONITOR,
    HDC,
    RECT,
    LPARAM,
    DWORD,
    BYTE,
    WCHAR,
    HANDLE
)


# ============================================================
# CONFIG
# ============================================================

BRIGHTNESS_STEP = 5

BRIGHTNESS_MONITOR_INDEX = 0
DDC_MONITOR_INDEX = 0

DISPLAY_MODE_VCP = 0xDC


# Modes reported directly by your ASUS XG32VQ:
#
# DC(03 0B 0D 0E 11 12 13 14)
#
# We know 0x03 is Cinema.
# The other ASUS-specific mappings can be renamed later.
DISPLAY_MODES = [
    ("Cinema", 0x03),
    ("Unknown 0B", 0x0B),
    ("Unknown 0D", 0x0D),
    ("Unknown 0E", 0x0E),
    ("Unknown 11", 0x11),
    ("Unknown 12", 0x12),
    ("Unknown 13", 0x13),
    ("Unknown 14", 0x14),
]


# ============================================================
# BRIGHTNESS
# ============================================================

monitors = sbc.list_monitors()

if not monitors:
    raise RuntimeError("No monitors detected")


print()
print("===== DETECTED MONITORS =====")

for index, monitor in enumerate(monitors):
    print(f"{index}: {monitor}")

print("=============================")
print()


BRIGHTNESS_MONITOR = monitors[
    BRIGHTNESS_MONITOR_INDEX
]

print(
    "Brightness monitor:",
    BRIGHTNESS_MONITOR
)


def get_brightness():

    values = sbc.get_brightness(
        display=BRIGHTNESS_MONITOR
    )

    return values[0]


def set_brightness(value):

    value = max(
        0,
        min(100, value)
    )

    sbc.set_brightness(
        value,
        display=BRIGHTNESS_MONITOR
    )

    print(
        f"Brightness: {value}%"
    )


# ============================================================
# WINDOWS DDC
# ============================================================

class PhysicalMonitor(Structure):

    _fields_ = [
        (
            "handle",
            HANDLE
        ),
        (
            "description",
            WCHAR * 128
        )
    ]


MONITOR_ENUM_PROC = WINFUNCTYPE(
    BOOL,
    HMONITOR,
    HDC,
    POINTER(RECT),
    LPARAM
)


def get_physical_monitor():

    logical_monitors = []

    def callback(
        hmonitor,
        hdc,
        rect,
        data
    ):

        logical_monitors.append(
            hmonitor
        )

        return True


    callback_function = MONITOR_ENUM_PROC(
        callback
    )


    success = windll.user32.EnumDisplayMonitors(
        None,
        None,
        callback_function,
        None
    )


    if not success:
        raise WinError()


    physical_handles = []


    print()
    print("===== DDC MONITORS =====")


    for logical_monitor in logical_monitors:

        count = DWORD()


        success = (
            windll.dxva2
            .GetNumberOfPhysicalMonitorsFromHMONITOR(
                logical_monitor,
                byref(count)
            )
        )


        if not success:
            continue


        physical_monitors = (
            PhysicalMonitor * count.value
        )()


        success = (
            windll.dxva2
            .GetPhysicalMonitorsFromHMONITOR(
                logical_monitor,
                count.value,
                physical_monitors
            )
        )


        if not success:
            continue


        for monitor in physical_monitors:

            index = len(
                physical_handles
            )


            print(
                f"{index}: "
                f"{monitor.description}"
            )


            physical_handles.append(
                monitor.handle
            )


    print("========================")
    print()


    if not physical_handles:
        raise RuntimeError(
            "No DDC monitors found"
        )


    if DDC_MONITOR_INDEX >= len(
        physical_handles
    ):
        raise RuntimeError(
            f"DDC monitor index "
            f"{DDC_MONITOR_INDEX} does not exist"
        )


    print(
        f"Using DDC monitor "
        f"#{DDC_MONITOR_INDEX}"
    )


    return physical_handles[
        DDC_MONITOR_INDEX
    ]


physical_monitor = get_physical_monitor()


# ============================================================
# VCP READ / WRITE
# ============================================================

def get_vcp(code):

    current = DWORD()
    maximum = DWORD()


    success = (
        windll.dxva2
        .GetVCPFeatureAndVCPFeatureReply(
            physical_monitor,
            BYTE(code),
            None,
            byref(current),
            byref(maximum)
        )
    )


    if not success:
        raise WinError()


    return (
        current.value,
        maximum.value
    )


def set_vcp(
    code,
    value
):

    success = (
        windll.dxva2
        .SetVCPFeature(
            physical_monitor,
            BYTE(code),
            DWORD(value)
        )
    )


    if not success:
        raise WinError()


# ============================================================
# DISPLAY MODE HELPERS
# ============================================================

def get_mode_name(value):

    for name, mode_value in DISPLAY_MODES:

        if mode_value == value:
            return name

    return f"Unknown 0x{value:02X}"


display_mode_index = 0


def detect_current_display_mode():

    global display_mode_index


    try:

        current, maximum = get_vcp(
            DISPLAY_MODE_VCP
        )


        print()

        print(
            f"Current display mode: "
            f"{get_mode_name(current)}"
        )

        print(
            f"Raw value: "
            f"0x{current:02X}"
        )


        for index, (
            name,
            value
        ) in enumerate(
            DISPLAY_MODES
        ):

            if value == current:

                display_mode_index = index

                return


        print(
            "Current mode isn't in "
            "DISPLAY_MODES."
        )


    except Exception as e:

        print(
            "Could not detect "
            "display mode:"
        )

        print(e)


# ============================================================
# CHANGE DISPLAY MODE
# ============================================================

def change_display_mode(direction):

    global display_mode_index


    display_mode_index += direction

    display_mode_index %= len(
        DISPLAY_MODES
    )


    requested_name, requested_value = (
        DISPLAY_MODES[
            display_mode_index
        ]
    )


    try:

        before, _ = get_vcp(
            DISPLAY_MODE_VCP
        )


        set_vcp(
            DISPLAY_MODE_VCP,
            requested_value
        )


        # Give monitor a moment to apply
        # the new GameVisual mode.
        time.sleep(0.3)


        after, _ = get_vcp(
            DISPLAY_MODE_VCP
        )


        print()
        print(
            "=========================="
        )


        if after == requested_value:

            print(
                f"Selected mode: "
                f"{requested_name}"
            )

            print(
                f"VCP value: "
                f"0x{after:02X}"
            )

        else:

            print(
                f"Requested mode: "
                f"{requested_name}"
            )

            print(
                f"Requested value: "
                f"0x{requested_value:02X}"
            )

            print(
                f"Monitor reports: "
                f"{get_mode_name(after)} "
                f"(0x{after:02X})"
            )


        print(
            "=========================="
        )


    except Exception as e:

        print()
        print(
            "Display mode error:"
        )

        print(e)


# ============================================================
# KEYBOARD
# ============================================================

alt_pressed = False
ctrl_pressed = False


def on_press(key):

    global alt_pressed
    global ctrl_pressed


    try:

        # ALT
        if key in (
            keyboard.Key.alt,
            keyboard.Key.alt_l,
            keyboard.Key.alt_r
        ):

            alt_pressed = True


        # CTRL
        elif key in (
            keyboard.Key.ctrl,
            keyboard.Key.ctrl_l,
            keyboard.Key.ctrl_r
        ):

            ctrl_pressed = True


        # ====================================================
        # CTRL + ALT + UP
        # BRIGHTNESS +
        # ====================================================

        elif (
            ctrl_pressed
            and alt_pressed
            and key == keyboard.Key.up
        ):

            current = get_brightness()

            set_brightness(
                current
                + BRIGHTNESS_STEP
            )


        # ====================================================
        # CTRL + ALT + DOWN
        # BRIGHTNESS -
        # ====================================================

        elif (
            ctrl_pressed
            and alt_pressed
            and key == keyboard.Key.down
        ):

            current = get_brightness()

            set_brightness(
                current
                - BRIGHTNESS_STEP
            )


        # ====================================================
        # CTRL + ALT + RIGHT
        # NEXT DISPLAY MODE
        # ====================================================

        elif (
            ctrl_pressed
            and alt_pressed
            and key == keyboard.Key.right
        ):

            change_display_mode(
                +1
            )


        # ====================================================
        # CTRL + ALT + LEFT
        # PREVIOUS DISPLAY MODE
        # ====================================================

        elif (
            ctrl_pressed
            and alt_pressed
            and key == keyboard.Key.left
        ):

            change_display_mode(
                -1
            )


    except Exception as e:

        print()
        print(
            "Keyboard error:"
        )

        print(e)


def on_release(key):

    global alt_pressed
    global ctrl_pressed


    if key in (
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r
    ):

        alt_pressed = False


    elif key in (
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r
    ):

        ctrl_pressed = False


# ============================================================
# START
# ============================================================

detect_current_display_mode()


print()
print(
    "================================="
)

print(
    "MONITOR CONTROLS RUNNING"
)

print(
    "================================="
)

print()

print(
    "Ctrl + Alt + Up"
    "      Brightness +5"
)

print(
    "Ctrl + Alt + Down"
    "    Brightness -5"
)

print()

print(
    "Ctrl + Alt + Right"
    "   Next display mode"
)

print(
    "Ctrl + Alt + Left"
    "    Previous display mode"
)

print()

print(
    "================================="
)

print()


with keyboard.Listener(
    on_press=on_press,
    on_release=on_release
) as listener:

    listener.join()