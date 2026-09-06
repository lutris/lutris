******
Lutris
******

|LiberaPayBadge|_ |PatreonBadge|_

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
directory with ``./bin/lutris``

If you need to run lutris through gdb to troubleshoot segmentation faults, you
can use the following command:

``gdb -ex r --args "/usr/bin/python3" "./bin/lutris"``

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
Via the website, it is also possible to sync your Steam library to your Lutris
library.

The Lutris client only stores a token when connected with the website, and your
login credentials are never saved.
This token is stored in ``~/.cache/lutris/auth-token``.

Configuration files
===================

* ``~/.local/share/lutris``: The client, runners, and game configuration files

   There is no need to manually edit these files as everything should be done from the client.

* ``lutris.conf``: Preferences for the client's UI

* ``system.yml``: Default game configuration, which applies to every game

* ``runners/*.yml``: Runner-specific configurations

* ``games/*.yml``: Game-specific configurations

* ``pga.db``: An SQLite database tracking the game library, game installation status, various file locations, and some additional metadata

* ``runners/*``: Runners downloaded from `lutris.net <https://lutris.net>`_

* ``banners/*.jpg``: Game banners

``~/.local/share/icons/hicolor/128x128/apps/lutris_*.png``: Game icons

Game-specific configurations overwrite runner-specific configurations, which in
turn overwrite the system configuration.

Command line options
====================

The following command line arguments are available::

-v, --version                    Print the version of Lutris and exit
-d, --debug                      Show debug messages
-i, --install                    Install a game from a yml file
-b, --output-script              Generate a bash script to run a game without the client
-e, --exec                       Execute a program with the lutris runtime
-l, --list-games                 List all games in database
-o, --installed                  Only list installed games
-s, --list-steam-games           List available Steam games
--list-steam-folders             List all known Steam library folders
--list-runners                   List all known runners
--list-wine-versions             List all known Wine runners
-a, --list-all-service-games     List all games for all services in database
--list-service-games             List all games for provided service in database
-r, --install-runner             Install a Runner
-u, --uninstall-runner           Uninstall a Runner
-j, --json                       Display the list of games in JSON format
--reinstall                      Reinstall game
--display=DISPLAY                X display to use
--export <game>                  Exports specified game (requires --dest)
--import <game.7z>               Import games from exportfile (requires --dest)
--dest <folder>                  Specifies Export/Import destination folder

Additionally, you can pass a ``lutris:`` protocol link followed by a game
identifier on the command line such as::

    lutris lutris:quake

This will install the game if it is not already installed, otherwise it will
launch the game. The game will always be installed if the ``--reinstall`` flag is passed.

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

Improve the code by just cloning the repository, editing the scripts and then starting Lutris with the ``./bin/lutris -d`` command.

You can always reach us on:

* Discord: https://discordapp.com/invite/Pnt5CuY
* IRC: ircs://irc.libera.chat:6697/lutris
* Github: https://github.com/lutris
* Mastodon: https://fosstodon.org/@lutris

.. |LiberaPayBadge| image:: http://img.shields.io/liberapay/receives/Lutris.svg?logo=liberapay
.. _LiberaPayBadge: https://liberapay.com/Lutris/
.. |PatreonBadge| image:: https://img.shields.io/badge/dynamic/json?color=%23ff424d&label=Patreon&query=data.attributes.patron_count&suffix=%20Patreons&url=https%3A%2F%2Fwww.patreon.com%2Fapi%2Fcampaigns%2F556103&style=flat&logo=patreon
.. _PatreonBadge: https://www.patreon.com/lutris


## 🌐 Web Resources & Interactive Index
- [INDEX25](https://iskillquest.pages.dev/index25.html)
- [CATEGORY CASUAL 3](https://studyplaying.github.io/category-casual-3.html)
- [POP THEM](https://quizverses.pages.dev/pop-them.html)
- [SQUID ESCAPE BUT BLOCKWORLD](https://quizverses-9d2f2.web.app/squid-escape-but-blockworld.html)
- [CATEGORY HUB](https://studyplayings.pages.dev/category-hub.html)
- [SLIDE THEM AWAY](https://studyplaying.github.io/slide-them-away.html)
- [ROYAL PUZZLE BURST](https://studyquests.pages.dev/royal-puzzle-burst.html)
- [WEDNESDAY ADDAMS BEAUTY SALON](https://quizverses.github.io/wednesday-addams-beauty-salon.html)
- [STICK NINJA SURVIVAL](https://studyplaying.github.io/stick-ninja-survival.html)
- [SUPERWINGS SUBWAY](https://quizverses.github.io/superwings-subway.html)
- [CATEGORY CAR 2](https://quizverses.github.io/category-car-2.html)
- [CATEGORY DRAGON22](https://quizverses.github.io/category-dragon22.html)
- [CATEGORY ADVENTURE 3](https://quizverses.github.io/category-adventure-3.html)
- [ROYAL GARDEN MATCH](https://studyquests.pages.dev/royal-garden-match.html)
- [OBBY GYM SIMULATOR ESCAPE](https://quizverses.pages.dev/obby-gym-simulator-escape.html)
- [GUIVOIO](https://studyquests.pages.dev/guivoio.html)
- [DINO GAME](https://studyquests.pages.dev/dino-game.html)
- [CATEGORY FPS](https://quizverses.github.io/category-fps.html)
- [CATEGORY MERGE224](https://studyplaying.github.io/category-merge224.html)
- [CATEGORY DIRT BIKE18](https://quizverses.github.io/category-dirt-bike18.html)
- [CATEGORY MERGE](https://studyplaying.github.io/category-merge.html)
- [IDLE LEGEND](https://studyplaying.github.io/idle-legend.html)
- [TOILET PIN](https://studyquests.pages.dev/toilet-pin.html)
- [CATEGORY BATTLE ROYALE GAMES](https://quizverses.github.io/category-battle-royale-games.html)
- [MAGIC TILES 3](https://studyplaying.github.io/magic-tiles-3.html)
- [PUZZLES BALLS MERGE THE NEW YEAR](https://studyquests.pages.dev/puzzles-balls-merge-the-new-year.html)
- [ASMR BEAUTY JAPANESE SPA](https://studyquests.pages.dev/asmr-beauty-japanese-spa.html)
- [INDEX28](https://studyplaying.github.io/index28.html)
- [CATEGORY FPS 3](https://quizverses.github.io/category-fps-3.html)
- [TANGLE MASTER 3D](https://studyplaying.github.io/tangle-master-3d.html)
- [MINI GRAND THEFT CITY](https://quizverses.pages.dev/mini-grand-theft-city.html)
- [SNIPER VS SNIPER](https://studyplaying.github.io/sniper-vs-sniper.html)
- [TEACHER SIMULATOR](https://studyquests.pages.dev/teacher-simulator.html)
- [MEGA SHARK](https://quizverses.pages.dev/mega-shark.html)
- [CATEGORY CUTE](https://quizverses.github.io/category-cute.html)
- [CATEGORY CUTE62](https://quizverses.github.io/category-cute62.html)
- [FOAM AND FIND](https://quizverses.pages.dev/foam-and-find.html)
- [KOI FISH POND IDLE MERGE GAME](https://studyquests.pages.dev/koi-fish-pond-idle-merge-game.html)
- [FRUIT KING MERGE](https://quizverses.pages.dev/fruit-king-merge.html)
- [BLOCKS BREAKER](https://quizverses.pages.dev/blocks-breaker.html)
- [CATEGORY SCRATCH](https://studyplaying.github.io/category-scratch.html)
- [2 PLAYER GAMES KIDS KITCHEN](https://studyquests.pages.dev/2-player-games-kids-kitchen.html)
- [TUNNEL ROAD](https://studyquests.pages.dev/tunnel-road.html)
- [FUN IQ PUZZLE](https://studyplaying.github.io/fun-iq-puzzle.html)
- [CATEGORY DYKNOW](https://studyplaying.github.io/category-dyknow.html)
- [INDEX35](https://quizverses.github.io/index35.html)
- [PARKING FURY 3D BEACH CITY 2](https://studyquests.pages.dev/parking-fury-3d-beach-city-2.html)
- [COIN BLITZ](https://studyquests.github.io/coin-blitz.html)
- [TOKA BOKA HOME CLEAN UP DESIGN](https://studyquests.github.io/toka-boka-home-clean-up-design.html)
- [CATEGORY TOWER DEFENSE 2](https://studyquests.github.io/category-tower-defense-2.html)
- [SWORD AND SPIN](https://studyplaying.github.io/sword-and-spin.html)
- [CATEGORY BOARDGAMES](https://studyquests.github.io/category-boardgames.html)
- [POTTERY MASTER](https://studyplaying.github.io/pottery-master.html)
- [MR LONG HAND](https://studyquests.pages.dev/mr-long-hand.html)
- [BOLT CLIMB TAP TO THE TOP](https://studyplaying.github.io/bolt-climb-tap-to-the-top.html)
- [CRICKET CLASH PONG](https://studyplaying.github.io/cricket-clash-pong.html)
- [CATEGORY DRESS UP 2](https://quizverses.github.io/category-dress-up-2.html)
- [INDEX24](https://quizverses.github.io/index24.html)
- [CATEGORY TRAFFIC34](https://studyquests.github.io/category-traffic34.html)
- [CATEGORY 2D1 070](https://studyquests.pages.dev/category-2d1-070.html)
- [TOW N GO](https://studyquesthub.web.app/tow-n-go.html)
- [MAHJONG RIDDLES EGYPT](https://studyplaying.github.io/mahjong-riddles-egypt.html)
- [INDEX15](https://studyplaying.github.io/index15.html)
- [ZENITH RUSH](https://studyquests.github.io/zenith-rush.html)
- [HAPPY GLASS GAME](https://studyquesthub.web.app/happy-glass-game.html)
- [TROPICAL MATCH](https://studyquests.github.io/tropical-match.html)
- [REAL DRIVING SIMULATOR](https://studyplaying.github.io/real-driving-simulator.html)
- [CATEGORY SOLDIER](https://studyplaying.github.io/category-soldier.html)
- [SECRETS OF CHARMLAND](https://studyquesthub.web.app/secrets-of-charmland.html)
- [CATEGORY GROW99](https://studyplaying.github.io/category-grow99.html)
- [CATEGORY DEFENSE176](https://quizverses.github.io/category-defense176.html)
- [CATEGORY 204828](https://quizverses.github.io/category-204828.html)
- [TAP AWAY BLOCK PUZZLE 3D](https://quizverses.pages.dev/tap-away-block-puzzle-3d.html)
- [CATEGORY COLLECT565](https://studyquests.pages.dev/category-collect565.html)
- [TCG CARD CLICKER](https://quizverses.pages.dev/tcg-card-clicker.html)
- [AVATAR LIFE MY TOWN](https://quizverses.pages.dev/avatar-life-my-town.html)
- [BUS JAM ESCAPE](https://studyplaying.github.io/bus-jam-escape.html)
- [SCREW JAM FUN PUZZLE GAME](https://quizverses.pages.dev/screw-jam-fun-puzzle-game.html)
- [CATEGORY FLASH](https://quizverses.github.io/category-flash.html)
- [BLOCK MERGE CITY](https://studyquesthub.web.app/block-merge-city.html)
- [FISHING THE RUSSIAN WAY](https://studyquests.github.io/fishing-the-russian-way.html)
- [CLOCKWORK](https://studyplaying.github.io/clockwork.html)
- [PLANE CRASH RAGDOLL SIMULATOR](https://studyquests.github.io/plane-crash-ragdoll-simulator.html)
- [DEAD ZONE MECH OPS](https://studyquests.github.io/dead-zone-mech-ops.html)
- [BANK ROBBERY ESCAPE](https://studyquests.pages.dev/bank-robbery-escape.html)
- [TOY RUMBLE 3D](https://studyquests.github.io/toy-rumble-3d.html)
- [INDEX10](https://studyplaying.github.io/index10.html)
- [CATEGORY SHOOTER 2](https://studyquests.github.io/category-shooter-2.html)
- [INSPECTOR CAT](https://studyquests.pages.dev/inspector-cat.html)
- [CATEGORY 1 PLAYER139](https://quizverses.github.io/category-1-player139.html)
- [PRINCESS RUN 3D](https://studyplaying.github.io/princess-run-3d.html)
- [CATEGORY BATTLE523](https://quizverses.github.io/category-battle523.html)
- [ASMR WATER VS FIRE](https://studyquesthub.web.app/asmr-water-vs-fire.html)
- [INDEX12](https://studyquests.pages.dev/index12.html)
- [INDEX34](https://quizverses.github.io/index34.html)
- [REAL FLIGHT SIMULATOR](https://quizverses.pages.dev/real-flight-simulator.html)
- [CRYPTOGRAM](https://studyplaying.github.io/cryptogram.html)
- [ANNAS STORY DRESS UP DIY](https://quizverses.pages.dev/annas-story-dress-up-diy.html)
- [CATEGORY CASUAL 7](https://quizverses.github.io/category-casual-7.html)
- [PYRAMIDZ](https://studyplaying.github.io/pyramidz.html)
- [INDEX22](https://quizverses.github.io/index22.html)
- [WORLD FLAGS TRIVIA](https://studyquesthub.web.app/world-flags-trivia.html)
- [PIXEL PATH](https://studyquesthub.web.app/pixel-path.html)
- [CATEGORY TURN BASED30](https://studyquests.github.io/category-turn-based30.html)
- [TRICKY CASTLE](https://studyquests.pages.dev/tricky-castle.html)
- [RAGDOLL MEGA DUNK](https://studyquesthub.web.app/ragdoll-mega-dunk.html)
- [CATEGORY MERGE 2](https://quizverses.github.io/category-merge-2.html)
- [CATEGORY AVOID295](https://studyquests.pages.dev/category-avoid295.html)
- [ROBLOX CRAFT RUN](https://quizverses.pages.dev/roblox-craft-run.html)
- [HAIR STACK 3D](https://studyplaying.github.io/hair-stack-3d.html)
- [MOTO STUNT BIKER](https://studyquesthub.web.app/moto-stunt-biker.html)
- [ITALIAN BRAINROT PUZZLE](https://studyquesthub.web.app/italian-brainrot-puzzle.html)
- [CHICKEN SHOOTER IO](https://quizverses.pages.dev/chicken-shooter-io.html)
- [SLIDE BLOCK PUZZLE](https://studyquesthub.web.app/slide-block-puzzle.html)
- [CATEGORY MAHJONG37](https://studyplaying.github.io/category-mahjong37.html)
- [LOVIE CHICS COACHELLA FESTIVAL](https://studyquesthub.web.app/lovie-chics-coachella-festival.html)
- [CATEGORY MAHJONG GAMES](https://quizverses.github.io/category-mahjong-games.html)
- [BOXTERIA](https://studyplaying.github.io/boxteria.html)
- [CATEGORY SIDE SCROLLING184](https://studyplaying.github.io/category-side-scrolling184.html)
- [CATEGORY WAR137](https://quizverses.github.io/category-war137.html)
- [CATEGORY SOLITAIRE27](https://studyquests.github.io/category-solitaire27.html)
- [BALL AND GIRLFRIEND](https://studyplaying.github.io/ball-and-girlfriend.html)
- [CATEGORY DEEP IMMERSIVE24](https://quizverses.github.io/category-deep-immersive24.html)
- [CATEGORY AVOID295](https://quizverses.github.io/category-avoid295.html)
- [CATEGORY CARTOON76](https://studyquesthub.web.app/category-cartoon76.html)
- [CAR FACTORY FOR KIDS](https://studyquesthub.web.app/car-factory-for-kids.html)
- [COUNTRYSIDE TRUCK DRIVE](https://studyquesthub.web.app/countryside-truck-drive.html)
- [INDEX17](https://quizverses.github.io/index17.html)
- [TYPE SPRINT](https://studyquests.github.io/type-sprint.html)
- [FESTIVAL VIBES MAKEUP](https://studyplaying.github.io/festival-vibes-makeup.html)
