# debug_paths.py
from pathlib import Path
import handler

print("handler.py :", Path(handler.__file__).resolve())
print("STATIC_DIR :", handler.STATIC_DIR.resolve())
print("exists     :", handler.STATIC_DIR.exists())
print("is_dir     :", handler.STATIC_DIR.is_dir())
if handler.STATIC_DIR.exists():
    print("contents   :", [p.name for p in handler.STATIC_DIR.iterdir()])