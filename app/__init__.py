import sys
import os

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
_backend_app = os.path.join(_backend_dir, "app")

if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

if os.path.exists(_backend_app) and _backend_app not in __path__:
    __path__.append(_backend_app)
