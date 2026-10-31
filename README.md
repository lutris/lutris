# Lutris

**Open-source gaming platform for Linux.** All your games, from all eras and all platforms, in one library.

[![Liberapay](https://img.shields.io/liberapay/receives/Lutris.svg?logo=liberapay)](https://liberapay.com/Lutris/)
[![Patreon](https://img.shields.io/badge/dynamic/json?color=%23ff424d&label=Patreon&query=data.attributes.patron_count&suffix=%20Patreons&url=https%3A%2F%2Fwww.patreon.com%2Fapi%2Fcampaigns%2F556103&style=flat&logo=patreon)](https://www.patreon.com/lutris)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
[![Discord](https://img.shields.io/badge/chat-Discord-5865F2)](https://discordapp.com/invite/Pnt5CuY)

Lutris helps you install and play video games from all eras and from most
gaming systems. It combines existing emulators, engine re-implementations and
compatibility layers (Wine, Proton, DOSBox, RetroArch...) behind a single
interface, so you don't have to configure each one by hand.

<!-- SCREENSHOT 1/4: main library view with game covers loaded -->
<!-- ![Lutris game library](docs/screenshots/library.png) -->

## Features

- **One library for everything**: native Linux games, Windows games, retro consoles and more
- **Connects to your stores**: Humble Bundle, GOG, Steam and other services
- **Automated installers**: community-made scripts handle downloads, setup and tweaks
- **Per-game configuration**: game-specific options that override the runner and system defaults
- **Optional lutris.net account**: fetch your library from the website and sync your Steam library

<!-- SCREENSHOT 2/4: sidebar with connected services (GOG / Steam / Humble) -->
<!-- ![Connected services](docs/screenshots/services.png) -->

<!-- SCREENSHOT 3/4: game configuration window (runner options) -->
<!-- ![Game configuration](docs/screenshots/configuration.png) -->

## Installation

Lutris is available in most distribution repositories, and as a Flatpak:

```bash
flatpak install flathub --user -y net.lutris.Lutris
```

If you install Lutris from your distribution's packages, install Wine and
up-to-date graphics drivers as well if you plan to play Windows games (not
needed with the Flatpak).

See [lutris.net/downloads](https://lutris.net/downloads) for distro-specific
instructions. To run Lutris from the source package, see "Running Lutris" at
the end of this file.

## Installer scripts

Lutris installations are fully automated through scripts, which can be written
in either JSON or YAML.
The scripting syntax is described in [docs/installers.rst](docs/installers.rst),
and is also available online at [lutris.net](https://lutris.net).

<!-- SCREENSHOT 4/4: an installer running (the install dialog with progress) -->
<!-- ![Lutris installer](docs/screenshots/install.png) -->

## Game library

Optional accounts can be created at [lutris.net](https://lutris.net) and linked
with Lutris clients. This enables your client to automatically fetch your
library from the website. Via the website, it is also possible to sync your
Steam library to your Lutris library.

The Lutris client only stores a token when connected with the website, and your
login credentials are never saved. This token is stored in
`~/.cache/lutris/auth-token`.

## Community

You can always reach us on:

- Discord: https://discordapp.com/invite/Pnt5CuY
- IRC: ircs://irc.libera.chat:6697/lutris
- GitHub: https://github.com/lutris
- Mastodon: https://fosstodon.org/@lutris

## Support the project

Lutris is 100% community supported, to ensure a continuous development on the
project, please consider donating to the project.
Our main platform for supporting Lutris is Patreon: https://www.patreon.com/lutris
but there are also other options available at https://lutris.net/donate

## Contributing

Want to make Lutris better? Help implement features, fix bugs, test
pre-releases, or simply chat with the developers?

Improve the code by just cloning the repository, editing the scripts and then
starting Lutris with the `./bin/lutris -d` command. See
[CONTRIBUTING.md](CONTRIBUTING.md) for more details.

<details>
<summary>Running Lutris</summary>

(current content, unchanged: running from the source package, and the gdb
command for troubleshooting segmentation faults)

</details>

<details>
<summary>Configuration files</summary>

(current content, unchanged)

</details>

<details>
<summary>Command line options</summary>

(current content, unchanged, including the `lutris:` protocol explanation)

</details>
