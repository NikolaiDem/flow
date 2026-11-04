# debug_paths.py
from pathlib import Path
import test_handler

print("test_handler.py :", Path(test_handler.__file__).resolve())
print("STATIC_DIR :", test_handler.STATIC_DIR.resolve())
print("exists     :", test_handler.STATIC_DIR.exists())
print("is_dir     :", test_handler.STATIC_DIR.is_dir())
if test_handler.STATIC_DIR.exists():
    print("contents   :", [p.name for p in test_handler.STATIC_DIR.iterdir()])