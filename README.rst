******
Lutris
******

Lutris is an open source gaming platform that makes gaming on Linux easier by
managing, installing and providing optimal settings for games.

Lutris does not sell games. For commercial games, you must own a copy to install
the game on Lutris.
The platform uses programs referered to as 'runners' to launch games,
Those runners (with the exception of Steam and web browsers) are provided and
managed by Lutris, so you don't need to install them with your package manager.

Scripts written by the community allow access to a library of games.
Using scripts, games can be played without manual setup.

Installer scripts
=================

Lutris installations are fully automated through scripts, which can be written
in either JSON or YAML.
The scripting syntax is described in ``docs/installers.rst``, and is also
available online at `lutris.net <https://lutris.net>`_.

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

This will install the game if it is not already installed, otherwise it will
launch the game. The game will always be installed if the ``--reinstall`` flag is passed.

Planned features
================

Lutris is far from complete, and some features have yet
to be implemented.

Here's what to expect from future versions of Lutris:

* Humble Bundle integration
* TOSEC database integration
* Management of personal game data (i.e. syncing games across devices using private cloud storage)
* Community features (friends list, chat, multiplayer game scheduling, etc.)
* Controller configuration GUI (with xboxdrv support)

Support the project
===================

Lutris is 100% community supported, to ensure a continuous developement on the
project, please consider donating to the project.
Our main platform for supporting Lutris is Patreon: https://www.patreon.com/lutris
but there are also other options available at https://lutris.net/donate

Come with us!
=============

Want to make Lutris better? Help implement features, fix bugs, test
pre-releases, or simply chat with the developers?

You can always reach us on:

* Discord: #lutris_support and #lutris_dev on the LGG server: https://discord.gg/C3uJjRD
* IRC: #lutris on the Freenode servers
* Github: https://github.com/lutris
* Twitter: https://twitter.com/LutrisGaming
* Google+: https://plus.google.com/+LutrisNet
