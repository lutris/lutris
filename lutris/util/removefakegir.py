"""Remove fakegir (used for PyGObject autocompletion) from the Python Path."""
import os, sys

fakegir_path = os.path.join(os.path.expanduser('~'), '.cache/fakegir')
if fakegir_path in sys.path:
    sys.path.remove(fakegir_path)
