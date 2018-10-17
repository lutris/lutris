******
Lutris
******

Lutris is an open source gaming platform for GNU/Linux.
It makes gaming on Linux easier by managing, installing and providing optimal
settings for games.

Lutris does not sell games; you have to provide your own copy of the games
unless they are open source or freeware.
Games can be installed anywhere on your system; Lutris does not impose
anything.

Lutris relies on various programs referenced as 'runners' to provide a vast
library of games.
These runners (with the exception of Steam and web browsers) are provided by
Lutris, you don't need to install them with your package manager.

We currently support the following runners:

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

Lutris automates installation of games using configuration scripts written in
JSON or YAML, which list the various files needed to install a game and can
perform a series of actions on them.
The syntax of installers is described in ``docs/installers.rst``, and is also
available on `lutris.net <https://lutris.net>`_ when writing installers.

A web UI is planned to ease the creation of these scripts.

Game Library
============

You can optionally create an account on `lutris.net <https://lutris.net>`_ and
connect this account to the client.
This will allow you to sync your game library from the website to the client
(not the other way around).
If you wish, you can also sync your Steam library with your Lutris library on
the website.

The client does not store your `lutris.net <https://lutris.net>`_ credentials
on your computer.
Instead, when you authenticate, the website will send a token which will
be used to sync your library.
This token is stored in ``~/.cache/lutris/auth-token``.

Configuration files
===================

The client, runner, and game configuration files are stored in
``~/.config/lutris``.
There is no need to manually edit these files as everything should be done from
the client.

``lutris.conf``: preferences for the client's UI

``system.yml``: default configuration for every game

``runners/*.yml``: runner-specific default configurations

``games/*.yml``: game-specific configurations

The game configuration can override previously defined runner and system
configuration and runner configuration can override system configuration.

Runners and the game database
=========================

The data necessary to manage your library and run the game is stored in
``~/.local/share/lutris``.

``pga.db``: your game library, game installation status, locations on the
filesystem, and some additional metadata, all stored in an SQLite
database

``runners/*``: runners downloaded from `lutris.net <https://lutris.net>`_

``icons/*.png`` and ``banners/*.jpg``: game images

Command line options
====================

The following command line arguments are available::

-v, --version              Print the version of Lutris and exit
-d, --debug                Show debug messages
-i, --install              Install a game from a yml file
-e, --exec                 Execute a program with the lutris runtime
-l, --list-games           List all games in database
-o, --installed            Only list installed games
-s, --list-steam-games     List available Steam games
--list-steam-folders       List all known Steam library folders
-j, --json                 Display the list of games in JSON format
--reinstall                Reinstall game
--display=DISPLAY          X display to use

Additionally, you can pass a ``lutris:`` protocol link followed by a game
identifier on the command line such as::

    lutris lutris:quake

This will install the game if not already installed or launch the game
otherwise (unless the ``--reinstall`` flag is passed).

Planned features
================

Lutris is far from complete and some of the more interesting features have yet
to be implemented.

Here's what to expect from the future versions of Lutris:

* Integration with GOG and Humble Bundle
* Integration with the TOSEC database
* Management of Personal Game Archives (let you store your games files on
  private storage, allowing you to reinstall them on all your devices)
* Game saves sync
* Community features (friends list, chat, multiplayer game scheduling)
* Controller configuration GUI (with xboxdrv support)

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
