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
- [FUNNY RAGDOLL WRESTLERS](https://themindzone.pages.dev/funny-ragdoll-wrestlers.html)
- [MERGE FUSION](https://quizverses.github.io/merge-fusion.html)
- [TILE FARM STORY MATCHING GAME](https://studyplayings.web.app/tile-farm-story-matching-game.html)
- [CATEGORY MISSION207](https://studyquesthub.web.app/category-mission207.html)
- [MR BOUNCE](https://quizverses.pages.dev/mr-bounce.html)
- [POP ADVENTURE](https://studyplayings.web.app/pop-adventure.html)
- [BUBBLE SKY](https://studyquests.pages.dev/bubble-sky.html)
- [KAWAII FRIENDS TILES MATCHER](https://studyplayings.pages.dev/kawaii-friends-tiles-matcher.html)
- [CATEGORY PIXEL313](https://studyquests.pages.dev/category-pixel313.html)
- [SMARTLE](https://quizverses.github.io/smartle.html)
- [INCREDIBLE KIDS DENTIST](https://studyquests.github.io/incredible-kids-dentist.html)
- [FLYING BILL](https://studyquesthub.web.app/flying-bill.html)
- [INDEX11](https://studyplayings.pages.dev/index11.html)
- [CATEGORY SIMULATION 4](https://quizverses.github.io/category-simulation-4.html)
- [AVATAR LIFE MY TOWN](https://quizverses.pages.dev/avatar-life-my-town.html)
- [BLOCK MERGE CITY](https://studyquesthub.web.app/block-merge-city.html)
- [RUNNING LATE](https://studyquests.github.io/running-late.html)
- [CATEGORY CASUAL971](https://studyplayings.pages.dev/category-casual971.html)
- [WORMS ZONE](https://studyplayings.web.app/worms-zone.html)
- [CATEGORY STICKMAN175](https://studyplayings.pages.dev/category-stickman175.html)
- [PRACTICE ON ME](https://quizverses.github.io/practice-on-me.html)
- [CATEGORY SNAKE40](https://studyquests.github.io/category-snake40.html)
- [BROOMCRAFT MYSTIC EVASION](https://studyplayings.web.app/broomcraft-mystic-evasion.html)
- [CAR JAM ESCAPE](https://quizverses.github.io/car-jam-escape.html)
- [BLOCKS BREAKER](https://studyplayings.web.app/blocks-breaker.html)
- [TAP IT AWAY 3D](https://studyquesthub.web.app/tap-it-away-3d.html)
- [DOOMSDAY ZOMBIE TD](https://studyquesthub.web.app/doomsday-zombie-td.html)
- [MEMEVOIO](https://quizverses.github.io/memevoio.html)
- [STICKMAN HALLOWEEN SURVIVE](https://studyplayings.web.app/stickman-halloween-survive.html)
- [CATEGORY SIMULATION 2](https://studyplayings.web.app/category-simulation-2.html)
- [PRACTICE ON ME](https://studyquesthub.web.app/practice-on-me.html)
- [CATEGORY 3D1 371](https://studyquests.github.io/category-3d1-371.html)
- [BLOOM SORT 2 BEE PUZZLE](https://quizverses.github.io/bloom-sort-2-bee-puzzle.html)
- [ANIMAL TRANSFORM RACE](https://studyquests.pages.dev/animal-transform-race.html)
- [X TO Y ALMOST IMPOSSIBLE](https://studyplayings.pages.dev/x-to-y-almost-impossible.html)
- [BOWLING STARS](https://quizverses.github.io/bowling-stars.html)
- [FURY ROAD ZOMBIE CRASH](https://studyquests.github.io/fury-road-zombie-crash.html)
- [MR BEAN JUMP](https://studyquesthub.web.app/mr-bean-jump.html)
- [CATEGORY FREE](https://studyquests.github.io/category-free.html)
- [FIND THE SPRUNKI](https://studyquests.github.io/find-the-sprunki.html)
- [MAGIC CHRISTMAS TREE MATCH 3](https://quizverses.github.io/magic-christmas-tree-match-3.html)
- [FIGHT TRIVIA](https://studyquests.pages.dev/fight-trivia.html)
- [FROG BYTE](https://studyquests.github.io/frog-byte.html)
- [GEOMETRY VIBES MONSTER](https://quizverses.github.io/geometry-vibes-monster.html)
- [CATEGORY RPG80](https://studyquests.pages.dev/category-rpg80.html)
- [HYPER NURSE HOSPITAL GAMES](https://studyquests.pages.dev/hyper-nurse-hospital-games.html)
- [CAPYBARA GO](https://quizverses.github.io/capybara-go.html)
- [CATEGORY SURVIVAL366](https://quizverses.github.io/category-survival366.html)
- [CIRCLE RUN ENDLESS](https://studyquests.github.io/circle-run-endless.html)
- [FORMULA RACING GAMES CAR GAME](https://studyplayings.web.app/formula-racing-games-car-game.html)
- [CATEGORY SOLITAIRE27](https://studyplayings.web.app/category-solitaire27.html)
- [BULLET SUPERHERO](https://quizverses.github.io/bullet-superhero.html)
- [CATEGORY TANK](https://studyplayings.web.app/category-tank.html)
- [CATEGORY POINT AND CLICK124](https://studyquests.github.io/category-point-and-click124.html)
- [FRUIT BALLS JUICY FUSION](https://studyquesthub.web.app/fruit-balls-juicy-fusion.html)
- [PUSH THE FROG](https://studyquesthub.web.app/push-the-frog.html)
- [LOL SURPRISE GAME ZONE](https://studyquests.pages.dev/lol-surprise-game-zone.html)
- [MONEY PING PONG](https://quizverses.github.io/money-ping-pong.html)
- [US ARMY CAR GAMES TRUCK DRIVING](https://quizverses.github.io/us-army-car-games-truck-driving.html)
- [CATEGORY PUZZLE 3](https://studyplayings.pages.dev/category-puzzle-3.html)
- [CHAMPIONS FC](https://studyquests.pages.dev/champions-fc.html)
- [CATEGORY MAHJONG CONNECT](https://studyquests.pages.dev/category-mahjong-connect.html)
- [CATEGORY POOL](https://studyquests.pages.dev/category-pool.html)
- [CATEGORY ROGUELIKE38](https://studyquests.pages.dev/category-roguelike38.html)
- [RAGDOLL FOOTBALL 2 PLAYERS](https://studyplayings.web.app/ragdoll-football-2-players.html)
- [TERMS](https://studyquests.pages.dev/terms.html)
- [PUSH PUSH CAT](https://studyquesthub.web.app/push-push-cat.html)
- [CATEGORY STICKMAN](https://studyquests.pages.dev/category-stickman.html)
- [BRIDGE FIGHT](https://studyquests.pages.dev/bridge-fight.html)
- [TROPICAL MATCH](https://studyplayings.pages.dev/tropical-match.html)
- [CATEGORY RACING DRIVING 2](https://studyquests.pages.dev/category-racing-driving-2.html)
- [SUDOBLOCK DAILY](https://studyquests.github.io/sudoblock-daily.html)
- [VEX HYPER DASH](https://studyquests.github.io/vex-hyper-dash.html)
- [CATEGORY SOLITAIRE27](https://studyquests.github.io/category-solitaire27.html)
- [MAHJONG STACK](https://quizverses.github.io/mahjong-stack.html)
- [CATEGORY SIMULATION 2](https://studyquests.pages.dev/category-simulation-2.html)
- [QUBE 2048 ELF](https://quizverses.github.io/qube-2048-elf.html)
- [CATEGORY PLATFORM260](https://studyquests.github.io/category-platform260.html)
- [DEFORM IT](https://studyquesthub.web.app/deform-it.html)
- [COUNT AND BOUNCE](https://studyplayings.pages.dev/count-and-bounce.html)
- [SHEEP SHEEP DUCK](https://quizverses.pages.dev/sheep-sheep-duck.html)
- [DRAW A PATH TO THE FINISH LINE](https://studyquests.github.io/draw-a-path-to-the-finish-line.html)
- [STAR ATTACK 3D](https://studyquesthub.web.app/star-attack-3d.html)
- [STICKMAN ARCHER SHOOTING ARROWS AT REDS](https://studyquests.github.io/stickman-archer-shooting-arrows-at-reds.html)
- [BOARD KINGS BOARD DICE](https://studyplayings.web.app/board-kings-board-dice.html)
- [MOTO STUNT BIKER](https://studyquesthub.web.app/moto-stunt-biker.html)
- [WITCH CRAFT POTION SORT](https://studyquests.github.io/witch-craft-potion-sort.html)
- [100 DOORS PUZZLE BOX](https://studyquests.pages.dev/100-doors-puzzle-box.html)
- [BASKETBALL STARS 2026](https://studyplayings.pages.dev/basketball-stars-2026.html)
- [CATEGORY THINKY 3](https://quizverses.github.io/category-thinky-3.html)
- [CATEGORY ADVENTURE 3](https://studyplayings.web.app/category-adventure-3.html)
- [FUN GOLF](https://studyquests.github.io/fun-golf.html)
- [BUBBLE ESCAPE](https://quizverses.pages.dev/bubble-escape.html)
- [QUACKVENTURE](https://studyquests.github.io/quackventure.html)
- [SQUID GAME ORIGINAL](https://quizverses.github.io/squid-game-original.html)
- [CATEGORY TOP DOWN251](https://studyquests.github.io/category-top-down251.html)
- [HIT KNOCK DOWN](https://studyquests.github.io/hit-knock-down.html)
- [GOAL RUSH](https://quizverses.pages.dev/goal-rush.html)
- [GRANNY 3 RETURN THE SCHOOL](https://studyquests.github.io/granny-3-return-the-school.html)
- [BUBBLE SKY](https://quizverses.github.io/bubble-sky.html)
- [ORGANIZE IT](https://studyquests.github.io/organize-it.html)
- [CATEGORY STRATEGY](https://studyquests.pages.dev/category-strategy.html)
- [LOVE TILE TRIO](https://quizverses.github.io/love-tile-trio.html)
- [ZIG SNAKE](https://quizverses.github.io/zig-snake.html)
- [CITYQUEST](https://studyquesthub.web.app/cityquest.html)
- [CATEGORY RPG](https://studyquests.pages.dev/category-rpg.html)
- [CATEGORY JIGSAW10](https://studyplayings.pages.dev/category-jigsaw10.html)
- [EGG DASH](https://studyplayings.web.app/egg-dash.html)
- [CHRISTMAS SNOWBALL ARENA](https://quizverses.pages.dev/christmas-snowball-arena.html)
- [BRAT GIRL SUMMER](https://studyplaying.github.io/brat-girl-summer.html)
- [CATEGORY FPS](https://studyquests.pages.dev/category-fps.html)
- [TREASURE SEEKER](https://quizverses.pages.dev/treasure-seeker.html)
- [BRAT GIRL SUMMER](https://quizverses.github.io/brat-girl-summer.html)
- [CUBE TO HOLE PUZZLE](https://studyplaying.github.io/cube-to-hole-puzzle.html)
- [CATEGORY TANK58](https://studyplayings.web.app/category-tank58.html)
- [SLIME ATTACK PUZZLE](https://studyplayings.web.app/slime-attack-puzzle.html)
- [VEGA MIX FAIRY TOWN](https://studyquests.github.io/vega-mix-fairy-town.html)
- [JELLY RUN 2048](https://quizverses.github.io/jelly-run-2048.html)
- [GOLF MINI](https://quizverses.github.io/golf-mini.html)
- [CATEGORY DRAWING](https://thelearnquesters.pages.dev/category-drawing.html)
- [JELLY TOWER CRUSH](https://learnquester.pages.dev/jelly-tower-crush.html)
- [LABUBU COLORING ADVENTURE](https://quizverses.github.io/labubu-coloring-adventure.html)
- [CATEGORY OBSTACLE299](https://learnquester.pages.dev/category-obstacle299.html)
- [MAKEUP TRENDS THEN AND NOW](https://studyquests.github.io/makeup-trends-then-and-now.html)
- [HARD PUZZLE](https://quizverses.github.io/hard-puzzle.html)
- [TILE FARM STORY MATCHING GAME](https://quizverses.github.io/tile-farm-story-matching-game.html)
- [4 HEXA](https://quizverses.github.io/4-hexa.html)
- [CATEGORY SURVIVAL366](https://studyplayings.web.app/category-survival366.html)
- [CATEGORY SPACE](https://quizverses.github.io/category-space.html)
- [DIRTY MONEY THE RICH GET RICH](https://quizverses.github.io/dirty-money-the-rich-get-rich.html)
