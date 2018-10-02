******
Lutris
******

Lutris is an open source gaming platform that makes gaming on Linux easier by
managing, installing and providing optimal settings for games.

Lutris does not sell games, and you must provide your own copy of a game
unless it is open source/freeware.
Instead, Lutris utilizes scripts called "runners" to provide a large library of
games.
These runners (with the exception of Steam and web browsers) are provided and
managed by Lutris, so you don't need to install them with your package manager.

Lutris currently supports the following programs:

* Linux (Native games)
* Steam
* Web
* Wine
* Wine + Steam
* Libretro
* DOSBox
* MAME
* MESS
* ScummVM
* ResidualVM
* Adventure Game Studio
* Mednafen
* FS-UAE
* Vice
* Stella
* Atari800
* Hatari
* Virtual Jaguar
* Snes9x
* Mupen64Plus
* Dolphin
* PCSX2
* PPSSPP
* Osmose
* Reicast
* Frotz
* jzIntv
* O2EM
* ZDoom
* Citra
* DeSmuME
* DGen


Installer scripts
=================

Lutris installations are fully automated through runners, which can be written
in either JSON or YAML.
The runner syntax is described in ``docs/installers.rst``, and is also
available online at `lutris.net <https://lutris.net>`_.

A web UI is planned to ease the creation of runners.

Game library
============

Optional accounts can be created at `lutris.net
<https://lutris.net>`_ and linked with Lutris clients.
This enables your client to automatically sync fetch library from the website.
**It is currently not possible to sync from the client to the cloud.**
Via the website, it is also possible to sync your Steam library to your Lutris
library.

The Lutris client only stores a token when connected with the website, and your
login credentials are never saved.
This token is stored in ``~/.cache/lutris/auth-token``.

Configuration files
===================

* ``~/.config/lutris``: The client, runners, and game configuration files

   * There is be no need to manually edit these files as everything should
be done from the client.

* ``lutris.conf``: Preferences for the client's UI

* ``system.yml``: Default game configuration, which applies to every game

* ``runners/*.yml``: Runner-specific configurations

* ``games/*.yml``: Game-specific configurations

Game-specific configurations supersede runner-specific configurations, which in
turn supersede the system configuration.

Runners and the game database
=============================

``~/.local/share/lutris``: All data necessary to manage Lutris' library and games, including:

* ``pga.db``: An SQLite database tracking the game library, game installation
status, various file locations, and some additional metadata

``runners/*``: Runners downloaded from `lutris.net <https://lutris.net>`_

``icons/*.png`` and ``banners/*.jpg``: Game banners and icons

Command line options
====================

The following command line arguments are available::

  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -v, --verbose         Verbose output
  -d, --debug           Show debug messages
  -i INSTALLER_FILE, --install=INSTALLER_FILE
                        Install a game from a yml file
  -l, --list-games      List all games in database
  -o, --installed       Only list installed games
  -j, --json            Display the list of games in JSON format
  --list-steam-games    List available Steam games
  --list-steam-folders  List all known Steam library folders
  --reinstall           Reinstall game

Additionally, you can pass a ``lutris:`` protocol link followed by a game
identifier on the command line such as::

    lutris lutris:quake

This will install the game if it is not already installed; otherwise it will
launch the game (unless the ``--reinstall`` flag is passed).

Planned features
================

Lutris is far from complete, and some of the more interesting features have yet
to be implemented.

Here's what to expect from future versions of Lutris:

* GOG and Humble Bundle integration
* TOSEC database integration
* Management of personal game data, i.e. syncing games across devices using private cloud storage
* Save syncing
* Community features (friends list, chat, multiplayer game scheduling, etc.)
* Controller configuration GUI (with xboxdrv support)
* Web UI for editing runners

Come with us!
=============

Want to make Lutris better? Help implement features, fix bugs, test
pre-releases, or simply chat with the developers?

You can always reach us on:

* IRC: #lutris on the Freenode servers
* Github: https://github.com/lutris
* Twitter: https://twitter.com/LutrisGaming
* Google+: https://plus.google.com/+LutrisNet
* Email: contact@lutris.net
