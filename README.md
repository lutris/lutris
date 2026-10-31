# Lutris

**Open-source gaming platform for Linux.** All your games in one library.

[![Patreon](https://img.shields.io/badge/dynamic/json?color=%23ff424d&label=Patreon&query=data.attributes.patron_count&suffix=%20Patreons&url=https%3A%2F%2Fwww.patreon.com%2Fapi%2Fcampaigns%2F556103&style=flat&logo=patreon)](https://www.patreon.com/lutris)
[![Liberapay](https://img.shields.io/liberapay/receives/Lutris.svg?logo=liberapay)](https://liberapay.com/Lutris/)
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
- **Connects to your stores**: Humble Bundle, GOG, Steam, Epic Games Store and other services
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

If you install Lutris from your distribution's packages and plan to play
Windows games, also install Wine and up-to-date graphics drivers (not needed
with the Flatpak).

See [lutris.net/downloads](https://lutris.net/downloads) for distro-specific
instructions. To run Lutris from source, see "Running from source" at the end
of this page.

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

Lutris is 100% community supported. To ensure its continued development, please
consider donating. Our main platform is [Patreon](https://www.patreon.com/lutris),
but there are also [other options](https://lutris.net/donate).

## Contributing

Want to make Lutris better? Help implement features, fix bugs, test
pre-releases, or simply chat with the developers.

To improve the code, clone the repository, edit the scripts and start Lutris
with the `./bin/lutris -d` command. See [CONTRIBUTING.md](CONTRIBUTING.md) for
more details.

<details>
<summary>Running from source</summary>

If you are running Lutris from its source code rather than from a package,
install it at least once through your package manager (even an older version)
so that all its dependencies are available. Then you can run it directly from
the source directory:

```
./bin/lutris
```

To troubleshoot segmentation faults, run Lutris through gdb:

```
gdb -ex r --args "/usr/bin/python3" "./bin/lutris"
```

</details>

<details>
<summary>Command line options</summary>

The following command line arguments are available:

```
-v, --version                    Print the version of Lutris and exit
-d, --debug                      Show debug messages
-i, --install                    Install a game from a YAML file
-b, --output-script              Generate a bash script to run a game without the client
-e, --exec                       Execute a program with the Lutris runtime
-l, --list-games                 List all games in the database
-o, --installed                  Only list installed games
-s, --list-steam-games           List available Steam games
--list-steam-folders             List all known Steam library folders
--list-runners                   List all known runners
--list-wine-versions             List all known Wine versions
-a, --list-all-service-games     List all games for all services in the database
--list-service-games             List all games for the given service in the database
-r, --install-runner             Install a runner
-u, --uninstall-runner           Uninstall a runner
-j, --json                       Display the list of games in JSON format
--reinstall                      Reinstall a game
--display=DISPLAY                X display to use
--export <game>                  Export the specified game (requires --dest)
--import <game.7z>               Import games from an export file (requires --dest)
--dest <folder>                  Destination folder for --export and --import
```

You can also pass a `lutris:` link followed by a game identifier, for example:

```
lutris lutris:quake
```

This installs the game if it isn't installed yet, and launches it otherwise.
With `--reinstall`, the game is always installed.

</details>

<details>
<summary>Configuration files</summary>

Lutris stores its configuration and data in two main directories. You normally
don't need to edit them by hand, as everything can be configured from the
client.

`~/.config/lutris`:

- `lutris.conf`: Preferences for the client's UI
- `system.yml`: Default game configuration, which applies to every game
- `runners/*.yml`: Runner-specific configurations
- `games/*.yml`: Game-specific configurations

`~/.local/share/lutris`:

- `pga.db`: SQLite database of your game library (installation status, file locations and other metadata)
- `runners/*`: Runners downloaded from [lutris.net](https://lutris.net)
- `banners/*.jpg`: Game banners

Game icons are stored in `~/.local/share/icons/hicolor/128x128/apps/lutris_*.png`.

Game-specific configurations override runner-specific ones, which in turn
override the system configuration.

</details>
