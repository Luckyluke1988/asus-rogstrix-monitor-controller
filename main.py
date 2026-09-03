import screen_brightness_control as sbc
from pynput import keyboard

STEP = 5

monitors = sbc.list_monitors()
print("Detected monitors:", monitors)

MONITOR = monitors[0]

print(f"Controlling: {MONITOR}")
print("Alt + ↑ = brighter")
print("Alt + ↓ = darker")
print("ESC = quit")

alt_pressed = False


def get_brightness():
    return sbc.get_brightness(display=MONITOR)[0]


def set_brightness(value):
    value = max(0, min(100, value))
    sbc.set_brightness(value, display=MONITOR)
    print(f"Brightness: {value}%")


def on_press(key):
    global alt_pressed

    try:
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            alt_pressed = True

        elif alt_pressed and key == keyboard.Key.up:
            set_brightness(get_brightness() + STEP)

        elif alt_pressed and key == keyboard.Key.down:
            set_brightness(get_brightness() - STEP)

        elif key == keyboard.Key.esc:
            return False

    except Exception as e:
        print(f"Error: {e}")


def on_release(key):
    global alt_pressed

    if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
        alt_pressed = False


with keyboard.Listener(
    on_press=on_press,
    on_release=on_release
) as listener:
    listener.join()