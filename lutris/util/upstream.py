"""Find the newest builds that projects publish themselves, for Lutris to download.

Lutris fetches runners, Wine builds and the tools games use from where their own
developers release them: GitHub or a Forgejo forge's releases, a download
directory, or a fixed address.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, Protocol
from urllib.parse import quote, urljoin

from lutris.exceptions import LutrisError
from lutris.util.http import HTTPError, Request


class UpstreamError(LutrisError):
    """Raised when a project publishes no build Lutris can use."""


@dataclass(frozen=True)
class UpstreamBuild:
    """One downloadable build, and the version its project gives it."""

    version: str
    url: str


class UpstreamSource(Protocol):
    def find(self) -> UpstreamBuild:
        """Return the newest build, or raise UpstreamError (or HTTPError)."""
        ...


def _get(url: str) -> Request:
    return Request(url, headers={"Accept": "application/json"}).get()


@dataclass(frozen=True)
class ReleaseSource:
    """The newest release with an asset whose name matches `asset`, from GitHub or,
    with `host` set, a Forgejo or Gitea forge (which share GitHub's release API)."""

    repo: str
    asset: str | None = None
    host: str = "github.com"
    prereleases: bool = False

    @property
    def api_url(self) -> str:
        if self.host == "github.com":
            return f"https://api.github.com/repos/{self.repo}/releases"
        return f"https://{self.host}/api/v1/repos/{self.repo}/releases"

    def releases(self) -> list[dict[str, Any]]:
        releases = _get(self.api_url + ("?per_page=30" if self.host == "github.com" else "?limit=30")).json
        if not isinstance(releases, list):
            raise UpstreamError(f"{self.repo} returned no releases")
        return [release for release in releases if not release.get("draft")]

    def find(self) -> UpstreamBuild:
        # The forge's own idea of the latest stable release comes first: release lists
        # are ordered by creation, which nightly builds and re-published tags upset
        if not self.prereleases:
            try:
                latest = _get(self.api_url + "/latest").json
            except HTTPError as ex:
                if ex.code != 404:
                    raise
                latest = None
            if isinstance(latest, dict) and (build := self.build_for_release(latest)):
                return build
        for release in self.releases():
            if release.get("prerelease") and not self.prereleases:
                continue
            if build := self.build_for_release(release):
                return build
        raise UpstreamError(f"{self.repo} has no release with a file matching '{self.asset}'")

    def build_for_release(self, release: Mapping[str, Any]) -> UpstreamBuild | None:
        if self.asset:
            return release_build(release, self.asset)
        tag = release.get("tag_name")
        if isinstance(tag, str) and tag:
            return UpstreamBuild(tag, f"https://{self.host}/{self.repo}/archive/refs/tags/{quote(tag, safe='')}.tar.gz")
        return None


def release_build(release: Mapping[str, Any], asset: str) -> UpstreamBuild | None:
    """The build in a GitHub or Forgejo release whose file name matches `asset`."""
    version = release.get("tag_name")
    if not isinstance(version, str) or not version:
        return None
    for item in release.get("assets") or ():
        name = item.get("name")
        url = item.get("browser_download_url")
        if isinstance(name, str) and isinstance(url, str) and url and re.search(asset, name):
            return UpstreamBuild(version, url)
    return None


# A row of an Apache or nginx directory listing: the link, then its date
_LISTING_ROW = re.compile(
    r'href="([^"]+)"[^\n]*?(\d{4}-[A-Za-z]{3}-\d{2} \d{2}:\d{2}|\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2})'
)


@dataclass(frozen=True)
class ListingSource:
    """The newest file matching `asset` in a web server's directory listing, by the
    date the listing gives it, for projects that publish builds that way."""

    url: str
    asset: str

    def find(self) -> UpstreamBuild:
        newest: tuple[datetime, str] | None = None
        for link, stamp in _LISTING_ROW.findall(_get(self.url).text):
            name = unescape(link).rsplit("/", 1)[-1]
            if not re.search(self.asset, name):
                continue
            date_format = "%Y-%b-%d %H:%M" if stamp[4] == "-" else "%d-%b-%Y %H:%M"
            when = datetime.strptime(stamp, date_format)
            if newest is None or when > newest[0]:
                newest = (when, name)
        if newest is None:
            raise UpstreamError(f"{self.url} lists no file matching '{self.asset}'")
        name = newest[1]
        version = re.sub(r"\.(tar\.[a-z0-9]+|tgz|zip|7z|AppImage)$", "", name)
        return UpstreamBuild(version, urljoin(self.url, name))


@dataclass(frozen=True)
class FileSource:
    """A build at a fixed address, for projects that publish only one."""

    url: str
    version: str = ""

    def find(self) -> UpstreamBuild:
        return UpstreamBuild(self.version, self.url)


def source_from_dict(data: Mapping[str, Any]) -> UpstreamSource:
    """Read an upstream source from a runner's JSON definition: a release ("repo",
    "asset", and optionally "host" and "prereleases"), a directory listing
    ("listing" and "asset") or a fixed address ("url")."""
    if "repo" in data:
        return ReleaseSource(
            str(data["repo"]), str(data["asset"]), str(data.get("host", "github.com")), bool(data.get("prereleases"))
        )
    if "listing" in data:
        return ListingSource(str(data["listing"]), str(data["asset"]))
    if "url" in data:
        return FileSource(str(data["url"]), str(data.get("version", "")))
    raise ValueError(f"Unknown upstream source: {dict(data)}")
