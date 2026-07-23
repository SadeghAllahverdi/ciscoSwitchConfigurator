import os
import sys

# convenience launcher for Visual Studio: the real entry point is front/main.py
_base_dir = os.path.dirname(os.path.abspath(__file__))
for _path in (_base_dir, os.path.join(_base_dir, "front")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from main import main

if __name__ == "__main__":
    main()
