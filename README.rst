******
Lutris
******

Lutris is an open source gaming platform for GNU/Linux. It makes gaming
on Linux easier by taking care of managing, installing and providing
optimal settings for games.

Lutris does not sell games, you have to provide your own copy of the games
unless they are Open Source or Freeware.
The games can be installed anywhere you want on your system, the tool
does not impose anything.

Lutris relies on various programs referenced as 'runners' to provide a
vast library of games. These runners (with the exception of Steam,Desura
and Web browsers) are provided by lutris, you don't need to install them
with your package manager.
We currently support the following runners:

* Linux (Native games)
* Steam
* Desura (Experimental support)
* Web browser
* Wine
* Wine + Steam
* DosBOX
* Mame
* Mess
* ScummVM
* Mednafen
* FS-UAE
* Vice
* Stella
* Atari800
* Hatari
* Virtual Jaguar
* Snes9x
* Mupen64 Plus
* PCSXR
* Osmose
* GenS
* NullDC (using wine)
* OpenMSX
* Frotz
* Jzintv
* O2em

Runners that will be added in future versions of Lutris:

* PCSX2
* Dolphin
* Reicast (replacing NullDC)

Installer scripts
=================

Lutris automates installation of games using configuration files written
in JSON or YAML, these scripts list various files needed to install a game
and run a list of actions on them (such as extract, move, execute, …).
The syntax of installers is described in `docs/installers.rst` (also
available on lutris.net when writing installers).

A web UI is planned to ease the creation of these scripts.

Game Library
============

You can optionally create an account on lutris.net and connect to this
account on the client. This will allow you to sync your game library from
the website to the client (not the other way around). If you wish, you can
sync your Steam library with your Lutris library on the website.

The client does not store your lutris.net credentials on your computer.
Instead, when you authenticate, the website will send a token which will
be used to sync your library. This token is stored in
~/.cache/lutris/auth-token

Configuration files
===================

The client, runner and games configuration files are stored in
~/.config/lutris. There is no need to manually edit these files as
everything should be done from the client.

`lutris.conf`: stores preferences for the client's UI

`system.yml`: stores configuration that will be used for every game

`runners/*.yml`: stores configuration used for any game from a particular
runner

`games/*.yml`: stores configuration used for a specific game

The game configuration can override previously defined runner and system
configuration and runner configuration can override system configuration.

Runners and game database
=========================

The data necessary to manage your library and run the game is stored in
~/.local/share/lutris .

`pga.db`: stores your game library, the installation status, the location
on the filesystem plus some additional metadata. This file is a SQLite
database.

`runners/*`: runners downloaded from lutris.net (emulators and such)

`icons/*.png` and `banners/*.jpg`: images for the games.

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
  -s, --list-steam      List Steam (Windows) games
  --reinstall           Reinstall game

Additionally, you can pass a `lutris:` protocol link followed by a game
identifier on the command line such as::

    lutris lutris:quake

This will install the game if not already installed or launch the game
otherwise (unless the `--reinstall` flag is passed).

Planned features
================

Lutris is far from complete and some of the most intertesting features
are yet to be implemented!

Here's what to expect from the future versions of lutris:

* Better support for multiple wine version
* Integration with GOG and Humble Bundle
* Integration with the TOSEC databse
* Management of Personnal Game Archives (let you store your games files on
  private storage, allowing you to reinstall them on all your devices)
* Game saves sync
* Community features (friends list, chat, multiplayer game scheduling)
* Patched emulators to provide better fullscreen and controller support
* Controller configuration GUI (with xboxdrv / joy2key support)

Come with us!
=============

Want to make Lutris better? Help implement feature, fix bug, test our
pre-releases or simply chat with the developers?

You can always reach us on:
* IRC: #lutris on the Freenode servers
* Github: http://github.com/lutris
* Twitter: https://twitter.com/LutrisGaming
* Google+: https://plus.google.com/+LutrisNet
* Email: contact@lutris.net

