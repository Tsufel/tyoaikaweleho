import sys
import os

# When running as a frozen exe, make the exe's own directory importable
# so the optional image_ocr.py DLC can be found there.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))

import updater
updater.cleanup_old_exe()   # removes any leftover .old exe from a previous update

from app import App


if __name__ == "__main__":
    application = App()
    application.mainloop()
