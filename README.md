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
- [OCTOPUS INVASION](https://themindplay.github.io/octopus-invasion.html)
- [MATH QUEST](https://studyquesthub.web.app/math-quest.html)
- [CATEGORY CARE](https://studyplaying.github.io/category-care.html)
- [SLIDE THEM AWAY](https://studyquesthub.web.app/slide-them-away.html)
- [SCREW PUZZLE MASTER](https://quizverses-9d2f2.web.app/screw-puzzle-master.html)
- [CATEGORY DOG18](https://quizverses-9d2f2.web.app/category-dog18.html)
- [CATEGORY BASKETBALL](https://studyquests.pages.dev/category-basketball.html)
- [FIND OBJECTS HIDDEN ITEM](https://studyquests.pages.dev/find-objects-hidden-item.html)
- [CATEGORY PREMIUM PERKS71](https://quizverses.github.io/category-premium-perks71.html)
- [CATEGORY JUMPING147](https://quizverses.github.io/category-jumping147.html)
- [AIRPORT CONTROLLER](https://studyquesthub.web.app/airport-controller.html)
- [POPPING SUSHI](https://learnquester.github.io/popping-sushi.html)
- [DARLING DOLL](https://learnquesters.pages.dev/darling-doll.html)
- [INDEX6](https://thelearnquesters.pages.dev/index6.html)
- [INDEX11](https://thelearnquesters.pages.dev/index11.html)
- [HOLIDAY HEX SORT](https://learnquester.github.io/holiday-hex-sort.html)
- [CATEGORY DRAGON22](https://thelearnquesters.pages.dev/category-dragon22.html)
- [INDEX29](https://thelearnquesters.pages.dev/index29.html)
- [CATEGORY ESCAPE 2](https://thelearnquesters.pages.dev/category-escape-2.html)
- [MINE SWEEPER](https://learnquester.github.io/mine-sweeper.html)
- [INDEX17](https://thelearnquesters.pages.dev/index17.html)
- [INDEX5](https://thelearnquesters.pages.dev/index5.html)
- [CATEGORY FPS174](https://thelearnquester.web.app/category-fps174.html)
- [CATEGORY SOLITAIRE](https://thelearnquester.web.app/category-solitaire.html)
- [CATEGORY JUMPING147](https://thelearnquester.web.app/category-jumping147.html)
- [CATEGORY BUILDING179](https://thelearnquesters.pages.dev/category-building179.html)
- [TAP GO DELUXE](https://thelearnquester.web.app/tap-go-deluxe.html)
- [INDEX24](https://thelearnquesters.pages.dev/index24.html)
- [GIRLS FUN NAIL SALON](https://thelearnquester.web.app/girls-fun-nail-salon.html)
- [INDEX37](https://thelearnquesters.pages.dev/index37.html)
- [CATEGORY ESCAPE](https://thelearnquesters.pages.dev/category-escape.html)
- [NINE CARDS OF WINTER](https://learnquesters.pages.dev/nine-cards-of-winter.html)
- [CATEGORY FPS GAME](https://thelearnquesters.pages.dev/category-fps-game.html)
- [FURRY WEDDING PROPOSAL](https://learnquesters.pages.dev/furry-wedding-proposal.html)
- [ARROW WAVE](https://thelearnquester.web.app/arrow-wave.html)
- [DRAW THE WEAPON](https://learnquesters.pages.dev/draw-the-weapon.html)
- [BLOCKY ARCHER RUN](https://learnquesters.pages.dev/blocky-archer-run.html)
- [CATEGORY PUZZLE 7](https://quizverses.github.io/category-puzzle-7.html)
- [WAR LANDS](https://learnquester.pages.dev/war-lands.html)
- [TAPTAPBOOM](https://learnquester.pages.dev/taptapboom.html)
- [CATEGORY DRESS UP 2](https://thelearnquester.web.app/category-dress-up-2.html)
- [OFFROAD MUDDY TRUCKS](https://studyquesthub.web.app/offroad-muddy-trucks.html)
- [CATEGORY IDLE](https://thelearnquester.web.app/category-idle.html)
- [WORD SEARCH WITH HINTS](https://thelearnquester.web.app/word-search-with-hints.html)
- [CATEGORY INCREMENTAL388](https://thelearnquester.web.app/category-incremental388.html)
- [CATEGORY EDUCATIONAL25](https://thelearnquesters.pages.dev/category-educational25.html)
- [CATEGORY BUSINESS135](https://studyquests.pages.dev/category-business135.html)
- [CATEGORY PARTY23](https://thelearnquester.web.app/category-party23.html)
- [CANDY LOVE](https://learnquesters.pages.dev/candy-love.html)
- [TOYTOPIA](https://learnquesters.pages.dev/toytopia.html)
- [CATEGORY CAR 2](https://learnquester.pages.dev/category-car-2.html)
- [WAR LANDS](https://studyquests.pages.dev/war-lands.html)
- [GEOMETRY VIBES X ARROW](https://learnquester.pages.dev/geometry-vibes-x-arrow.html)
- [TRIANGLE WAY](https://learnquester.pages.dev/triangle-way.html)
- [HYPERSPACE   QUANTUM FRACTURE FEZ](https://thelearnquester.web.app/hyperspace---quantum-fracture-fez.html)
- [PRIVACY](https://studyquests.pages.dev/privacy.html)
- [STRAWBERRY HERO](https://studyquests.pages.dev/strawberry-hero.html)
- [COLORSFORMS](https://studyquests.pages.dev/colorsforms.html)
- [CATEGORY HORROR90](https://quizverses.github.io/category-horror90.html)
- [ELEMENTZ](https://thelearnquester.web.app/elementz.html)
- [CAR PARKING SIMULATOR](https://thelearnquester.web.app/car-parking-simulator.html)
- [BUBBLE SHOOTER NEON](https://learnquesters.pages.dev/bubble-shooter-neon.html)
- [CATEGORY AVOID295](https://studyquests.pages.dev/category-avoid295.html)
- [ARROW ESCAPE MASTER](https://quizverses.github.io/arrow-escape-master.html)
- [SUMMER CONNECT](https://thelearnquester.web.app/summer-connect.html)
- [OBBY ON A BIKE](https://learnquester.pages.dev/obby-on-a-bike.html)
- [CATEGORY PROXY LIST](https://thelearnquester.web.app/category-proxy-list.html)
- [VOXIOM IO](https://studyquesthub.web.app/voxiom-io.html)
- [CATEGORY SORTING44](https://thelearnquester.web.app/category-sorting44.html)
- [BLOCK DIGGER](https://thelearnquester.web.app/block-digger.html)
- [CATEGORY SOCCER 2](https://thelearnquester.web.app/category-soccer-2.html)
- [PUZZLES BALLS MERGE THE NEW YEAR](https://quizverses.github.io/puzzles-balls-merge-the-new-year.html)
- [DINOSAURS VS ASTEROIDS](https://learnquesters.pages.dev/dinosaurs-vs-asteroids.html)
- [CATEGORY PUZZLE 4](https://quizverses.github.io/category-puzzle-4.html)
- [COLOR DASH](https://thelearnquester.web.app/color-dash.html)
- [GEOMETRY VIBES 3D](https://studyquests.pages.dev/geometry-vibes-3d.html)
- [CATEGORY QUIZ](https://learnquester.pages.dev/category-quiz.html)
- [COOL MAN](https://studyquests.pages.dev/cool-man.html)
- [CATEGORY STICKMAN](https://thelearnquester.web.app/category-stickman.html)
- [CATEGORY MISSION206](https://quizverses.github.io/category-mission206.html)
- [CATEGORY MOUSE1 707](https://quizverses.github.io/category-mouse1-707.html)
- [CATEGORY SPACE57](https://quizverses.github.io/category-space57.html)
- [BUNNY BLOX](https://studyquesthub.web.app/bunny-blox.html)
- [INDEX34](https://thelearnquesters.pages.dev/index34.html)
- [SPRUNKI 3D SHOOTER](https://studyquests.pages.dev/sprunki-3d-shooter.html)
- [MR LONG LEGS](https://studyquesthub.web.app/mr-long-legs.html)
- [CATEGORY PLATFORM260](https://thelearnquester.web.app/category-platform260.html)
- [MERGE FRUIT](https://studyquesthub.web.app/merge-fruit.html)
- [SHELL STRIKERS](https://studyquests.pages.dev/shell-strikers.html)
- [BUBBLE SHOOTER FREE 3](https://thelearnquester.web.app/bubble-shooter-free-3.html)
- [FARM BLOCK](https://quizverses.github.io/farm-block.html)
- [SAFE MERGE](https://learnquester.pages.dev/safe-merge.html)
- [DUNGEON MASTER CULT CRAFT](https://quizverses.github.io/dungeon-master-cult-craft.html)
- [CATEGORY MATCH 3](https://thelearnquester.web.app/category-match-3.html)
- [RAGDOLL JUMP](https://learnquesters.pages.dev/ragdoll-jump.html)
- [CATEGORY SNAKE](https://quizverses.github.io/category-snake.html)
- [FUN GOLF](https://learnquester.pages.dev/fun-golf.html)
- [PUMPKING VS MUMMY](https://quizverses.github.io/pumpking-vs-mummy.html)
- [CATEGORY MERGE GAME](https://learnquester.pages.dev/category-merge-game.html)
- [DOLLYS RESTAURANT ORGANIZING](https://studyquests.pages.dev/dollys-restaurant-organizing.html)
- [UNLOCK THE BOLTS](https://studyquests.pages.dev/unlock-the-bolts.html)
- [ARMY COMMANDER CRAFT](https://studyquesthub.web.app/army-commander-craft.html)
- [MARBLE BUBBLE LEGEND](https://learnquester.github.io/marble-bubble-legend.html)
- [SCREW MASTERS 3D PUZZLE](https://studyquests.pages.dev/screw-masters-3d-puzzle.html)
- [MINICRAFT CHEF CAKE WARS](https://thelearnquester.web.app/minicraft-chef-cake-wars.html)
- [CATEGORY POINT AND CLICK124](https://learnquesters.pages.dev/category-point-and-click124.html)
- [MEGA RAMP CAR STUNTS](https://quizverses.github.io/mega-ramp-car-stunts.html)
- [ANIMAL SWIPE](https://quizverses.github.io/animal-swipe.html)
- [FESTIVAL VIBES MAKEUP](https://learnquester.pages.dev/festival-vibes-makeup.html)
- [SLIDEE](https://learnquester.github.io/slidee.html)
- [FARM MAHJONG 3D](https://thelearnquester.web.app/farm-mahjong-3d.html)
- [FRUIT CATCHER](https://learnquester.pages.dev/fruit-catcher.html)
- [CATEGORY HAPARA](https://thelearnquester.web.app/category-hapara.html)
- [CATEGORY SURVIVAL366](https://learnquester.pages.dev/category-survival366.html)
- [CATEGORY DRAWING34](https://thelearnquesters.pages.dev/category-drawing34.html)
- [KABOOM MINER](https://learnquester.github.io/kaboom-miner.html)
- [CATEGORY SPACE](https://quizverses.github.io/category-space.html)
- [STICKMAN DUO ESCAPE THE TOMB](https://studyquests.pages.dev/stickman-duo-escape-the-tomb.html)
- [MIRRORS PUZZLE](https://studyquests.pages.dev/mirrors-puzzle.html)
- [CATEGORY SNAKE](https://thelearnquester.web.app/category-snake.html)
- [TARCAT](https://learnquester.pages.dev/tarcat.html)
- [DUSTY CAT](https://quizverses.github.io/dusty-cat.html)
- [RACE TIME](https://learnquester.github.io/race-time.html)
- [WORDS FROM WORDS SEA](https://quizverses.github.io/words-from-words-sea.html)
- [NAIL QUEEN](https://studyquests.pages.dev/nail-queen.html)
- [BLOCKS BREAKER](https://studyquesthub.web.app/blocks-breaker.html)
- [INDEX10](https://thelearnquesters.pages.dev/index10.html)
- [CATEGORY BUILDING](https://thelearnquesters.pages.dev/category-building.html)
- [PERFECT SHOT](https://learnquester.github.io/perfect-shot.html)
- [SAILOR CHIC VS PIRATE CHARM](https://studyquesthub.web.app/sailor-chic-vs-pirate-charm.html)
