******
Lutris
******

|LiberaPayBadge|  |PatreonBadge|

Lutris helps you install and play video games from all eras and from most
gaming systems. By leveraging and combining existing emulators, engine
re-implementations and compatibility layers, it gives you a central interface
to launch all your games.

The client can connect with existing services like Humble Bundle, GOG and Steam
to make your game libraries easily available. Game downloads and installations
are automated and can be modified through user made scripts.

Running Lutris
==============

If you have not installed Lutris through your package manager and are using the
source package, it is recommended that you install lutris at least once, even an
older version to have all dependencies available.
Once all dependencies are satisfied, you can run lutris directly from the source
directory with `./bin/lutris`

If you need to run lutris through gdb to troubleshoot segmentation faults, you
can use the following command:

`gdb -ex r --args "/usr/bin/python3" "./bin/lutris"`

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

   There is be no need to manually edit these files as everything should be done from the client.

* ``lutris.conf``: Preferences for the client's UI

* ``system.yml``: Default game configuration, which applies to every game

* ``runners/*.yml``: Runner-specific configurations

* ``games/*.yml``: Game-specific configurations

Game-specific configurations overwrite runner-specific configurations, which in
turn overwrite the system configuration.

Runners and the game database
=============================

``~/.local/share/lutris``: All data necessary to manage Lutris' library and games, including:

* ``pga.db``: An SQLite database tracking the game library, game installation status, various file locations, and some additional metadata

* ``runners/*``: Runners downloaded from `lutris.net <https://lutris.net>`

* ``banners/*.jpg``: Game banners

``~/.local/share/icons/hicolor/128x128/apps/lutris_*.png``: Game icons

Command line options
====================

The following command line arguments are available::

-v, --version              Print the version of Lutris and exit
-d, --debug                Show debug messages
-i, --install              Install a game from a yml file
-b, --output-script        Generate a bash script to run a game without the client
-e, --exec                 Execute a program with the lutris runtime
-l, --list-games           List all games in database
-o, --installed            Only list installed games
-s, --list-steam-games     List available Steam games
--list-steam-folders       List all known Steam library folders
--list-runners             List all known runners
--list-wine-runners        List all known Wine runners
-r, --install-runner       Install a Runner
-u, --uninstall-runner     Uninstall a Runner
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

* TOSEC database integration
* Management of personal game data (i.e. syncing games across devices using private cloud storage)
* Community features (friends list, chat, multiplayer game scheduling, etc.)

Support the project
===================

Lutris is 100% community supported, to ensure a continuous development on the
project, please consider donating to the project.
Our main platform for supporting Lutris is Patreon: https://www.patreon.com/lutris
but there are also other options available at https://lutris.net/donate

Come with us!
=============

Want to make Lutris better? Help implement features, fix bugs, test
pre-releases, or simply chat with the developers?

You can always reach us on:

* Discord: https://discordapp.com/invite/Pnt5CuY
* IRC: ircs://irc.libera.chat:6697/lutris
* Github: https://github.com/lutris
* Twitter: https://twitter.com/LutrisGaming


.. |LiberaPayBadge| image:: http://img.shields.io/liberapay/receives/Lutris.svg?logo=liberapay
.. _LiberaPayBadge: https://liberapay.com/Lutris/
.. |PatreonBadge| image:: https://img.shields.io/badge/dynamic/json?color=%23ff424d&label=Patreon&query=data.attributes.patron_count&suffix=%20Patreons&url=https%3A%2F%2Fwww.patreon.com%2Fapi%2Fcampaigns%2F556103&style=flat&logo=patreon
.. _PatreonBadge: https://www.patreon.com/lutris
