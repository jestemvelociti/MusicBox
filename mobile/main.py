import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(_BASE_DIR, "core")):
    sys.path.insert(0, _BASE_DIR)

from kivy.core.window import Window  # noqa: E402

Window.softinput_mode = "pan"

from musicbox.app import MusicBoxApp  # noqa: E402


def main():
    MusicBoxApp().run()


if __name__ == "__main__":
    main()
