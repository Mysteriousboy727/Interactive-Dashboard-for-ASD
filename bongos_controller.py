import time
import subprocess
import os
import platform
import shutil
import argparse
import threading

# Try to import Raspberry Pi GPIO; fall back to a mock on other platforms
try:
    import RPi.GPIO as GPIO
    _GPIO_IS_MOCK = False
except Exception:
    _GPIO_IS_MOCK = True

    class _MockGPIO:
        BCM = 'BCM'
        OUT = 'OUT'
        IN = 'IN'
        PUD_UP = 'PUD_UP'
        FALLING = 'FALLING'
        HIGH = 1
        LOW = 0

        def __init__(self):
            self._callbacks = {}

        def setmode(self, mode):
            print(f"[MockGPIO] setmode({mode})")

        def setup(self, pin, mode, pull_up_down=None):
            print(f"[MockGPIO] setup(pin={pin}, mode={mode}, pull_up_down={pull_up_down})")

        def output(self, pin, value):
            print(f"[MockGPIO] output(pin={pin}, value={value})")

        def add_event_detect(self, pin, edge, callback=None, bouncetime=None):
            print(f"[MockGPIO] add_event_detect(pin={pin}, edge={edge}, bouncetime={bouncetime}) - callback registered but not auto-triggered in mock")
            if callback:
                self._callbacks[pin] = callback

        def cleanup(self):
            print("[MockGPIO] cleanup()")

    GPIO = _MockGPIO()

# ==============================
# GPIO SETUP (BCM numbering)
# ==============================
LEFT_LED = 16
RIGHT_LED = 26
LEFT_BUTTON = 17
RIGHT_BUTTON = 27

# ==============================
# VIDEO FILES (LOCAL)
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEFT_VIDEO = os.path.join(BASE_DIR, "left.mp4")
RIGHT_VIDEO = os.path.join(BASE_DIR, "right.mp4")

GPIO.setmode(GPIO.BCM)

GPIO.setup(LEFT_LED, GPIO.OUT)
GPIO.setup(RIGHT_LED, GPIO.OUT)

GPIO.setup(LEFT_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RIGHT_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("✅ Raspberry Pi Bongos Controller Running")
print("LEFT button  → LEFT video")
print("RIGHT button → RIGHT video\n")

# -----------------------------
# CLI / Simulation
# -----------------------------
parser = argparse.ArgumentParser(description="Raspberry Pi Bongos Controller")
parser.add_argument('--simulate', action='store_true', help='Enable interactive simulate mode (non-Pi)')
args = parser.parse_args()

_stop_event = threading.Event()
_sim_thread = None

# ==============================
# HELPER: PLAY VIDEO
# ==============================
def play_video(video_path):
    system = platform.system()

    # Prefer VLC if available (consistent behavior on Linux/RPi)
    if shutil.which("vlc"):
        subprocess.Popen([
            "vlc",
            "--play-and-exit",
            "--fullscreen",
            video_path
        ])
        return

    # On Windows, open with the default associated program
    if system == "Windows":
        try:
            os.startfile(video_path)
            return
        except Exception:
            # Fall through to subprocess fallback
            pass

    # On many Linux desktops use xdg-open if vlc isn't available
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", video_path])
        return

    # Last resort: try a platform-generic spawn
    try:
        subprocess.Popen([video_path], shell=True)
    except Exception:
        print("No suitable video player found. Please open:", video_path)


# -----------------------------
# Simulation loop (interactive)
# -----------------------------
def _simulate_loop():
    print("Simulation mode: type 'l' (left), 'r' (right), or 'q' (quit)")
    while not _stop_event.is_set():
        try:
            cmd = input('> ').strip().lower()
        except EOFError:
            _stop_event.set()
            break
        if cmd in ('l', 'left'):
            left_button_pressed(LEFT_BUTTON)
        elif cmd in ('r', 'right'):
            right_button_pressed(RIGHT_BUTTON)
        elif cmd in ('q', 'quit', 'exit'):
            print('Exiting simulate mode...')
            _stop_event.set()
            break
        elif cmd == '':
            continue
        else:
            print("Unknown command. Use 'l', 'r', or 'q'.")

# ==============================
# CALLBACKS
# ==============================
def left_button_pressed(channel):
    print("🟥 LEFT BUTTON PRESSED → Playing LEFT video")
    GPIO.output(LEFT_LED, GPIO.HIGH)
    play_video(LEFT_VIDEO)
    time.sleep(0.3)
    GPIO.output(LEFT_LED, GPIO.LOW)

def right_button_pressed(channel):
    print("🟦 RIGHT BUTTON PRESSED → Playing RIGHT video")
    GPIO.output(RIGHT_LED, GPIO.HIGH)
    play_video(RIGHT_VIDEO)
    time.sleep(0.3)
    GPIO.output(RIGHT_LED, GPIO.LOW)

# ==============================
# EVENT DETECTION
# ==============================
GPIO.add_event_detect(
    LEFT_BUTTON,
    GPIO.FALLING,
    callback=left_button_pressed,
    bouncetime=600
)

GPIO.add_event_detect(
    RIGHT_BUTTON,
    GPIO.FALLING,
    callback=right_button_pressed,
    bouncetime=600
)

try:
    if args.simulate:
        _sim_thread = threading.Thread(target=_simulate_loop, daemon=False)
        _sim_thread.start()
        _sim_thread.join()
    else:
        while True:
            time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Program stopped")

finally:
    _stop_event.set()
    GPIO.cleanup()
    if _GPIO_IS_MOCK:
        print("⚠️ Running with MockGPIO — no physical GPIO activity will occur on this machine.")