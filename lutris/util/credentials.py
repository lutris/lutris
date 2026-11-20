"""Write individual store credentials atomically with private permissions."""

from pathlib import Path
from tempfile import NamedTemporaryFile


def save_credentials(filename: str, text: str) -> None:
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete_on_close=False) as output:
        output.write(text)
        output.flush()
        Path(output.name).replace(path)
