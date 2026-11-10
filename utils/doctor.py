#!/usr/bin/env python3
"""Report which of the things Lutris needs are available to a Python interpreter.

Checks the Python version, the runtime dependencies declared in pyproject.toml, the GObject
introspection libraries and (informationally) the development tools. Exits with 1 if a required
item is missing. By default it checks the interpreter running it (`make doctor`) and suggests system packages;
with --venv it checks a virtualenv instead (`make doctor venv`) and suggests pip installs into it.

--setup first prepares the environment: with --venv it creates the virtualenv if it is missing and pip installs
what is missing into it (`make setup venv`); in both modes it installs the git pre-commit hook. The usual report
follows, so it shows what is still missing (for example system libraries that need your package manager).
"""

import argparse
import ast
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
MINIMUM_PYTHON = (3, 10)

# Distribution names whose import name differs from the normalized distribution name.
IMPORT_NAMES = {
    "pyyaml": "yaml",
    "pillow": "PIL",
    "python-magic": "magic",
    "dbus-python": "dbus",
    "pygobject": "gi",
    "protobuf": "google.protobuf",
}
# Imported lazily or guarded, so Lutris starts without them (debian/control only recommends some of them).
OPTIONAL_PYTHON_PACKAGES = {"evdev", "protobuf", "moddb"}

# Debian/Ubuntu packages (see INSTALL.rst and debian/control); pypresence and moddb are only available from PyPI.
APT_PYTHON_PACKAGES = {
    "pyyaml": "python3-yaml",
    "lxml": "python3-lxml",
    "requests": "python3-requests",
    "pillow": "python3-pil",
    "setproctitle": "python3-setproctitle",
    "python-magic": "python3-magic",
    "distro": "python3-distro",
    "dbus-python": "python3-dbus",
    "evdev": "python3-evdev",
    "pygobject": "python3-gi",
    "protobuf": "python3-protobuf",
}

# (acceptable (namespace, version) alternatives, required, Debian/Ubuntu package)
GI_LIBRARIES: Sequence[tuple[Sequence[tuple[str, str]], bool, str]] = (
    ((("Gtk", "3.0"),), True, "gir1.2-gtk-3.0"),
    ((("Gdk", "3.0"),), True, "gir1.2-gtk-3.0"),
    ((("GdkPixbuf", "2.0"),), True, "gir1.2-gdkpixbuf-2.0"),
    ((("PangoCairo", "1.0"),), True, "gir1.2-pango-1.0"),
    ((("WebKit2", "4.1"), ("WebKit2", "4.0")), True, "gir1.2-webkit2-4.1"),
    ((("GnomeDesktop", "3.0"),), False, "gir1.2-gnomedesktop-3.0"),
    ((("AppIndicator3", "0.1"), ("AyatanaAppIndicator3", "0.1")), False, "gir1.2-ayatanaappindicator3-0.1"),
)
# tool -> (installed by `make dev` as a pip package of the same name, Debian/Ubuntu package providing it)
DEVELOPMENT_TOOLS: dict[str, tuple[bool, str | None]] = {
    "ruff": (True, None),
    "mypy": (True, None),
    "mypy-baseline": (True, None),
    "nose2": (True, None),
    "msgfmt": (False, "gettext"),
}


# Dev-group packages whose import name is not worth guessing.
DEV_ONLY_DISTRIBUTIONS = {"ruff", "mypy", "mypy-baseline", "nose2", "pygobject-stubs"}

# Bindings that need system headers to build, so a virtualenv should see the distribution's copy.
SYSTEM_BINDINGS = {"dbus-python", "pygobject"}


class Report:
    def __init__(self, venv_python: Path | None = None) -> None:
        self.venv_python = venv_python
        use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self.codes = {"ok": "32", "missing": "31", "warn": "33", "bold": "1"} if use_color else {}
        self.failed = False
        self.apt_packages: list[str] = []
        self.python_packages: list[str] = []
        self.dev_tools: list[str] = []
        self.hints: list[str] = []

    def _paint(self, kind: str, text: str) -> str:
        code = self.codes.get(kind)
        return "\033[%sm%s\033[0m" % (code, text) if code else text

    def section(self, title: str) -> None:
        print(self._paint("bold", title))

    def ok(self, label: str) -> None:
        print("  %s %s" % (self._paint("ok", "[  OK   ]"), label))

    def missing(
        self,
        label: str,
        required: bool = True,
        note: str = "optional",
        apt: str | None = None,
        python_package: str | None = None,
        dev_tool: str | None = None,
        hint: str | None = None,
    ) -> None:
        for packages, package in (
            (self.apt_packages, apt),
            (self.python_packages, python_package),
            (self.dev_tools, dev_tool),
            (self.hints, hint),
        ):
            if package and package not in packages:
                packages.append(package)
        if required:
            self.failed = True
            print("  %s %s" % (self._paint("missing", "[MISSING]"), label))
        else:
            print("  %s %s (%s)" % (self._paint("warn", "[ WARN  ]"), label, note))

    def _split_python_packages(self) -> tuple[list[str], list[str], list[str]]:
        """Return (apt packages, packages to pip install, packages with no known distribution package)."""
        apt: list[str] = []
        pip: list[str] = []
        pypi_only: list[str] = []
        for name in self.python_packages:
            apt_name = APT_PYTHON_PACKAGES.get(name.lower())
            if apt_name and (self.venv_python is None or name.lower() in SYSTEM_BINDINGS):
                apt.append(apt_name)
            elif self.venv_python is not None:
                pip.append(name)
            elif apt_name is None:
                pypi_only.append(name)
        return apt, pip, pypi_only

    def print_fixes(self) -> None:
        python_apt, pip, pypi_only = self._split_python_packages()
        apt = python_apt + [package for package in self.apt_packages if package not in python_apt]
        if not (apt or pip or pypi_only or self.dev_tools or self.hints):
            return
        print("\n%s" % self._paint("bold", "How to fix:"))
        if apt:
            print("  Debian/Ubuntu:   sudo apt install %s" % " ".join(apt))
        if pip and self.venv_python:
            print("  Into the venv:   %s -m pip install %s" % (self.venv_python, " ".join(pip)))
        if pypi_only:
            print("  Not in debian/control, from PyPI: pip3 install %s" % " ".join(pypi_only))
            print("                   (an externally managed Python needs a virtualenv: `make doctor venv`)")
        if self.dev_tools and self.venv_python:
            print("  Dev tools:       %s -m pip install %s" % (self.venv_python, " ".join(self.dev_tools)))
        elif self.dev_tools:
            print("  Dev tools:       make dev")
        for hint in self.hints:
            print("  %s" % hint)
        print("  Other distributions: see INSTALL.rst for the package names.")


def read_requirements(group: str) -> list[str]:
    """Return the requirements of `runtime` ([project] dependencies) or `dev` ([dependency-groups] dev)."""
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        section, key = ("project", "dependencies") if group == "runtime" else ("dependency-groups", "dev")
        section_match = re.search(r"^\[%s\]\n(.*?)(?=^\[|\Z)" % re.escape(section), text, re.S | re.M)
        array_match = section_match and re.search(r"^%s\s*=\s*(\[.*?^\])" % key, section_match.group(1), re.S | re.M)
        return list(ast.literal_eval(re.sub(r"#.*", "", array_match.group(1)))) if array_match else []
    data = tomllib.loads(text)
    return list(data["project"]["dependencies"] if group == "runtime" else data["dependency-groups"]["dev"])


def requirement_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[;\s]", requirement, maxsplit=1)[0]


def is_installed(name: str) -> bool:
    """Whether a requirement is satisfied; stub packages and tools are looked up as distributions."""
    if name.lower().startswith("types-") or name.lower() in DEV_ONLY_DISTRIBUTIONS:
        return bool(distribution_version(name))
    module = IMPORT_NAMES.get(name.lower(), name.lower().replace("-", "_"))
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def distribution_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return ""


def check_python(report: Report) -> None:
    report.section("Python:")
    version = ".".join(str(part) for part in sys.version_info[:3])
    label = "python %s (%s)" % (version, sys.executable)
    if sys.version_info >= MINIMUM_PYTHON:
        report.ok(label)
    else:
        report.missing("%s, Lutris needs >= %d.%d" % (label, *MINIMUM_PYTHON))


def check_runtime_dependencies(report: Report) -> None:
    report.section("Runtime dependencies (pyproject.toml):")
    for requirement in read_requirements("runtime"):
        name = requirement_name(requirement)
        if name.lower().startswith("types-"):
            continue
        if is_installed(name):
            report.ok("%s %s" % (name, distribution_version(name)) if distribution_version(name) else name)
        else:
            report.missing(name, required=name.lower() not in OPTIONAL_PYTHON_PACKAGES, python_package=name)


def check_gobject(report: Report) -> None:
    report.section("GObject introspection:")
    try:
        import gi
    except ImportError:
        report.missing("PyGObject (import gi), the libraries below cannot be checked", apt="python3-gi")
        return
    for alternatives, required, apt_package in GI_LIBRARIES:
        for namespace, version in alternatives:
            try:
                gi.require_version(namespace, version)
                importlib.import_module("gi.repository." + namespace)
            except (ValueError, ImportError):
                continue
            report.ok("%s %s" % (namespace, version))
            break
        else:
            report.missing(
                " or ".join("%s %s" % alternative for alternative in alternatives), required=required, apt=apt_package
            )
    try:
        import cairo
    except ImportError:
        report.missing("pycairo (import cairo)", apt="python3-gi-cairo")
    else:
        report.ok("pycairo %s" % cairo.version)


def check_development_tools(report: Report) -> None:
    report.section("Development tools (see `make dev`):")
    for tool, (from_pip, apt_package) in DEVELOPMENT_TOOLS.items():
        if shutil.which(tool):
            report.ok(tool)
        else:
            report.missing(tool, required=False, note="not found", dev_tool=tool if from_pip else None, apt=apt_package)


def pip_install(requirement: str, *options: str) -> str | None:
    """Install a requirement quietly; return None on success or the last lines of pip's error output."""
    command = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *options, requirement]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return None
    lines = [line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()]
    causes = [line for line in lines if "fatal error" in line or line.startswith("ERROR:")]
    return "\n".join(causes[:3] or lines[-3:])


def venv_works(venv: Path) -> bool:
    command = [str(venv / "bin" / "python"), "-c", "pass"]
    try:
        return subprocess.run(command, capture_output=True, check=False).returncode == 0
    except OSError:
        return False


def venv_exists(venv: Path) -> bool:
    python = venv / "bin" / "python"
    return python.exists() or python.is_symlink()


def create_venv(venv: Path) -> bool:
    """Create the virtualenv, or recreate it when its interpreter no longer starts (for example after `python3 -m
    venv` was run over an environment made by another Python)."""
    command = [sys.executable, "-m", "venv", "--system-site-packages"]
    if venv_exists(venv):
        if venv_works(venv):
            return True
        print("Virtualenv %s is unusable (its interpreter does not start); recreating it" % venv)
        command.append("--clear")
    else:
        print("Creating virtualenv %s (with access to the system packages)" % venv)
    return subprocess.run([*command, str(venv)], check=False).returncode == 0


def install_missing_packages(report: Report) -> None:
    report.section("Installing into %s:" % sys.prefix)
    if subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=False).returncode != 0:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=False)
    wanted = [
        r
        for r in read_requirements("runtime") + read_requirements("dev")
        if not is_installed(requirement_name(r)) and requirement_name(r).lower() not in SYSTEM_BINDINGS
    ]
    if not wanted:
        report.ok("every package from pyproject.toml is already installed")
    for requirement in wanted:
        stubs = requirement_name(requirement).lower() == "pygobject-stubs"
        options = ("--no-cache-dir", "--config-settings=config=Gtk3,Gdk3,Soup2") if stubs else ()
        error = pip_install(requirement, *options)
        if error is None:
            report.ok("installed %s" % requirement)
        else:
            report.missing("could not install %s" % requirement, required=False, note="failed")
            print("\n".join("             " + line for line in error.splitlines()))


def install_git_hook(report: Report) -> None:
    hooks_dir = PYPROJECT.parent / ".git" / "hooks"
    source = Path("../../.hooks/pre-commit")
    if not hooks_dir.is_dir():
        report.missing(
            "git hook not installed: %s is not a git checkout" % PYPROJECT.parent, required=False, note="skipped"
        )
        return
    target = hooks_dir / "pre-commit"
    if target.is_symlink() and os.readlink(target) == str(source):
        report.ok("git pre-commit hook already installed")
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(source)
    report.ok("installed the git pre-commit hook")


def venv_site_packages_visible(venv: Path) -> bool:
    config = venv / "pyvenv.cfg"
    return (
        config.is_file()
        and re.search(r"^include-system-site-packages\s*=\s*true", config.read_text(), re.M | re.I) is not None
    )


def reexec_in_venv(venv: Path) -> Path:
    """Return the venv's interpreter, re-running this script with it unless it is already the current one."""
    venv_python = venv / "bin" / "python"
    if not venv_exists(venv):
        print("No virtualenv at %s. Create it with: make setup venv" % venv)
        raise SystemExit(1)
    if not venv_works(venv):
        print("Virtualenv %s is unusable (its interpreter does not start). Recreate it with: make setup venv" % venv)
        raise SystemExit(1)
    if Path(sys.prefix).resolve() != venv.resolve():
        sys.stdout.flush()
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    return venv_python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--venv", nargs="?", const=".venv", metavar="DIR", help="check a virtualenv (default: .venv)")
    parser.add_argument("--setup", action="store_true", help="create the venv if needed and install what is missing")
    args = parser.parse_args()

    venv = Path(args.venv) if args.venv else None
    if args.setup and venv and not create_venv(venv):
        return 1
    venv_python = reexec_in_venv(venv) if venv else None
    report = Report(venv_python)
    if venv_python:
        os.environ["PATH"] = str(venv_python.parent) + os.pathsep + os.environ.get("PATH", "")
    if args.setup:
        report.section("Setup:")
        install_git_hook(report)
        if venv:
            install_missing_packages(report)
        else:
            report.ok(
                "system Python: nothing is pip-installed; use your package manager (see below) or `make setup venv`"
            )
    check_python(report)
    check_runtime_dependencies(report)
    check_gobject(report)
    check_development_tools(report)
    if venv and report.failed and not venv_site_packages_visible(venv):
        report.hints.append(
            "%s cannot see the system packages (PyGObject, dbus, typelibs). Install them into it, or recreate it"
            " with: python3 -m venv --clear --system-site-packages %s" % (venv, venv)
        )
    report.print_fixes()
    if report.failed:
        print("\n%s" % report._paint("missing", "Some required items are missing."))
        return 1
    print("\n%s" % report._paint("ok", "Everything Lutris needs was found."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
