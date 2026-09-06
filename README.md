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
- [BLOCK MERGE CITY](https://studyquests.pages.dev/block-merge-city.html)
- [MR BULLET STEALTH NINJA KILLSTREAK](https://quizverses.pages.dev/mr-bullet-stealth-ninja-killstreak.html)
- [CATEGORY FASHION105](https://quizverses-9d2f2.web.app/category-fashion105.html)
- [FEED THE PARROT](https://quizverses.pages.dev/feed-the-parrot.html)
- [MAHJONG RIDDLES EGYPT](https://quizverses.github.io/mahjong-riddles-egypt.html)
- [TRIANGLE WAY](https://quizverses.pages.dev/triangle-way.html)
- [CRAZY SCREW KING](https://studyquests.github.io/crazy-screw-king.html)
- [BLOCK ESCAPE](https://quizverses.github.io/block-escape.html)
- [KOKO LOCO BLOCK BLAST](https://quizverses.github.io/koko-loco-block-blast.html)
- [PUZZLE MASTERS TRAVELERS](https://quizverses.github.io/puzzle-masters-travelers.html)
- [RENT OUT LANDLORD TYCOON](https://quizverses-9d2f2.web.app/rent-out-landlord-tycoon.html)
- [STICKMAN ROCKET](https://iskillplay.web.app/stickman-rocket.html)
- [CATEGORY MOUSE1 697](https://themindplays.pages.dev/category-mouse1-697.html)
- [ANIMAL LINK](https://themindplaying.web.app/animal-link.html)
- [MAHJONG SOLITAIRE ZODIAC](https://themindplaying.web.app/mahjong-solitaire-zodiac.html)
- [FLYING BILL](https://studyquests.github.io/flying-bill.html)
- [NUMBER MERGE MASTER](https://themindplaying.web.app/number-merge-master.html)
- [PYRAMIDZ2](https://themindplaying.web.app/pyramidz2.html)
- [CATEGORY CASUAL](https://studyquests.pages.dev/category-casual.html)
- [FLAPPY RUSH](https://quizverses.github.io/flappy-rush.html)
- [JUNGLE MATCH ADVENTURES](https://themindplays.pages.dev/jungle-match-adventures.html)
- [BUS DRIVER SIMULATOR 3D](https://quizverses.pages.dev/bus-driver-simulator-3d.html)
- [MOTO STUNTS DRIVING RACING](https://themindplays.pages.dev/moto-stunts-driving-racing.html)
- [MUSTANG CITY DRIVER](https://themindplaying.web.app/mustang-city-driver.html)
- [DIGITAL CIRCUS IO](https://themindplaying.web.app/digital-circus-io.html)
- [TOW N GO](https://quizverses.github.io/tow-n-go.html)
- [LITTLE ALCHEMY 2](https://skillplay.github.io/little-alchemy-2.html)
- [MAHJONG TOUR](https://themindplay.pages.dev/mahjong-tour.html)
- [SAMURAI MADNESS](https://themindplays.pages.dev/samurai-madness.html)
- [WORD SEARCH WITH HINTS](https://studyquests.github.io/word-search-with-hints.html)
- [VALENTINE S DAY COUPLE DATE](https://skillplay.github.io/valentine-s-day-couple-date.html)
- [BRICKS BREAKER](https://themindplay.pages.dev/bricks-breaker.html)
- [HIT BALL](https://quizverses.github.io/hit-ball.html)
- [KINDER GARDEN](https://quizverses.github.io/kinder-garden.html)
- [BUBBLE SHOOTER WILD WEST](https://themindplays.pages.dev/bubble-shooter-wild-west.html)
- [CATEGORY FOOD](https://themindplays.pages.dev/category-food.html)
- [PET SALON](https://quizverses.github.io/pet-salon.html)
- [CATEGORY MOUSE1 697](https://skillplay.github.io/category-mouse1-697.html)
- [NUGGET MAN SURVIVAL PUZZLE](https://themindplays.pages.dev/nugget-man-survival-puzzle.html)
- [HIT BALL](https://themindplay.pages.dev/hit-ball.html)
- [HOME RUN BOY](https://themindplay.pages.dev/home-run-boy.html)
- [CATEGORY FASHION](https://studyquests.pages.dev/category-fashion.html)
- [CATEGORY COLOR](https://studyplaying.github.io/category-color.html)
- [VR WORLD](https://quizverses-9d2f2.web.app/vr-world.html)
- [CATEGORY SOCCER](https://skillplay.github.io/category-soccer.html)
- [BUBBLE ESCAPE](https://quizverses.pages.dev/bubble-escape.html)
- [BEAR VS HUMANS](https://quizverses.pages.dev/bear-vs-humans.html)
- [HYPER KNIGHT](https://themindplaying.web.app/hyper-knight.html)
- [FENNEC THE FOX CLICK ADVENTURE](https://themindplaying.web.app/fennec-the-fox-click-adventure.html)
- [JEWEL MINER QUEST](https://themindplaying.web.app/jewel-miner-quest.html)
- [SOLITAIRE KLONDIKE](https://themindplay.pages.dev/solitaire-klondike.html)
- [CATEGORY RACING DRIVING 2](https://quizverses-9d2f2.web.app/category-racing-driving-2.html)
- [FILL THE BOTTLE](https://themindplay.pages.dev/fill-the-bottle.html)
- [CATEGORY MINECRAFT](https://skillplay.github.io/category-minecraft.html)
- [CATEGORY PHYSICS371](https://skillplay.github.io/category-physics371.html)
- [IDLE BARBER SHOP](https://quizverses.pages.dev/idle-barber-shop.html)
- [CATEGORY LOGIC538](https://studyquests.pages.dev/category-logic538.html)
- [CATEGORY MERGE221](https://themindplays.pages.dev/category-merge221.html)
- [DUSTY MAZE HUNTER](https://themindplaying.web.app/dusty-maze-hunter.html)
- [CATEGORY PLATFORM260](https://studyquests.pages.dev/category-platform260.html)
- [PERFECT SHOT](https://studyquests.pages.dev/perfect-shot.html)
- [CATEGORY FARMING87](https://themindplays.pages.dev/category-farming87.html)
- [2048 SORT FACTORY](https://quizverses.github.io/2048-sort-factory.html)
- [FRUIT MAHJONG 3D](https://quizverses-9d2f2.web.app/fruit-mahjong-3d.html)
- [SNEAKY FRIENDS](https://skillplay.github.io/sneaky-friends.html)
- [SKATING PARK](https://quizverses-9d2f2.web.app/skating-park.html)
- [CATEGORY COOKING](https://skillplay.github.io/category-cooking.html)
- [SKATING PARK](https://themindplays.pages.dev/skating-park.html)
- [NOOB SKYBLOCK SURVIVAL](https://themindplaying.web.app/noob-skyblock-survival.html)
- [CRYPTOGRAM WORD BRAIN PUZZLE](https://themindplays.pages.dev/cryptogram-word-brain-puzzle.html)
- [DOWNTOWN PARKOUR DRIVE](https://themindplays.pages.dev/downtown-parkour-drive.html)
- [GOOBER DASH](https://themindplay.pages.dev/goober-dash.html)
- [GRANNY GTA VEGAS](https://studyquests.pages.dev/granny-gta-vegas.html)
- [FASHIONISTA CHRISTMAS EVE PARTY](https://quizverses.pages.dev/fashionista-christmas-eve-party.html)
- [CATEGORY WEBGAME](https://themindplays.pages.dev/category-webgame.html)
- [BUS STOP COLOR JAM](https://quizverses.pages.dev/bus-stop-color-jam.html)
- [MEGA ESCAPE CAR PARKING PUZZLE](https://themindplays.pages.dev/mega-escape-car-parking-puzzle.html)
- [HOTEL FEVER TYCOON](https://quizverses.pages.dev/hotel-fever-tycoon.html)
- [BALLS VS LASERS](https://studyquests.github.io/balls-vs-lasers.html)
- [MERGE BLOCKS 2048 STYLE](https://quizverses.github.io/merge-blocks-2048-style.html)
- [CATEGORY ARENA255](https://themindplays.pages.dev/category-arena255.html)
- [CATEGORY SHOOTER](https://skillplay.github.io/category-shooter.html)
- [GUN RACING](https://themindplays.pages.dev/gun-racing.html)
- [UPHILL RUSH 13](https://quizverses.pages.dev/uphill-rush-13.html)
- [DOLPHIN COUPLE UNDERWATER DRESS UP](https://themindplay.pages.dev/dolphin-couple-underwater-dress-up.html)
- [FOX COIN MATCH](https://quizverses.github.io/fox-coin-match.html)
- [COLOR BLOCK SORT](https://quizverses-9d2f2.web.app/color-block-sort.html)
- [KICK LUCKY BOXES ONLINE](https://themindplaying.web.app/kick-lucky-boxes-online.html)
- [DRIVER MASTER SIMULATOR](https://themindplaying.web.app/driver-master-simulator.html)
- [SNAKE 2048IO](https://quizverses-9d2f2.web.app/snake-2048io.html)
- [CATEGORY MINIGAMES29](https://themindplaying.web.app/category-minigames29.html)
- [ASMR BEAUTY HOMELESS](https://themindplay.pages.dev/asmr-beauty-homeless.html)
- [SURVIVE THE NIGHT](https://skillplay.github.io/survive-the-night.html)
- [LOL SURPRISE GAME ZONE](https://studyquests.pages.dev/lol-surprise-game-zone.html)
- [EGG ADVENTURE MIRROR WORLD](https://studyquests.github.io/egg-adventure-mirror-world.html)
- [STICKMAN HALLOWEEN SURVIVE](https://themindplay.pages.dev/stickman-halloween-survive.html)
- [DRAW WAR](https://themindplaying.web.app/draw-war.html)
- [HIDDEN OBJECTS ISLAND SECRETS](https://themindplays.pages.dev/hidden-objects-island-secrets.html)
- [MONKEY BUBBLE DEFENSE](https://themindplays.pages.dev/monkey-bubble-defense.html)
- [TARCAT](https://themindplaying.web.app/tarcat.html)
- [FUN GOLF](https://studyquests.github.io/fun-golf.html)
- [PRINCESS ROYAL WEDDING](https://quizverses.github.io/princess-royal-wedding.html)
- [CLASSIC LABYRINTH 3D MAZE](https://iskillplay.web.app/classic-labyrinth-3d-maze.html)
- [FOOTBALL LEGENDS 2026](https://themindzone.pages.dev/football-legends-2026.html)
- [CATEGORY ESCAPE187](https://skillplay.github.io/category-escape187.html)
- [ICE CREAM SORT](https://studyquests.github.io/ice-cream-sort.html)
- [SLOPE EMOJI 2](https://themindplaying.web.app/slope-emoji-2.html)
- [KING KONG KART RACING](https://thequizzone.pages.dev/king-kong-kart-racing.html)
- [THREAD MATCH](https://quizverses-9d2f2.web.app/thread-match.html)
- [SWORDEDIO SPIN AND RUB](https://iskillplay.web.app/swordedio-spin-and-rub.html)
- [CROWD BATTLE GUN RUSH](https://quizverses.pages.dev/crowd-battle-gun-rush.html)
- [GARTEN OF BANBAN 1 ESCAPE](https://quizverses-9d2f2.web.app/garten-of-banban-1-escape.html)
- [LORENZO THE RUNNER](https://quizverses.pages.dev/lorenzo-the-runner.html)
- [BUBBLE SHOOTER BUTTERFLY](https://quizverses.pages.dev/bubble-shooter-butterfly.html)
- [CATEGORY PUZZLE 4](https://skillplay.github.io/category-puzzle-4.html)
- [BOWMASTERS](https://iskillplay.web.app/bowmasters.html)
- [HOT COLD WINTER STYLE](https://studyplaying.github.io/hot-cold-winter-style.html)
- [BUBBITS](https://iskillplay.web.app/bubbits.html)
- [ZOMBIE FRONTIER SHOOTER](https://studyquests.github.io/zombie-frontier-shooter.html)
- [RED HIDE BALL](https://quizverses-9d2f2.web.app/red-hide-ball.html)
- [MONSTER MERGE LEGENDS ALIVE](https://thequizzone.pages.dev/monster-merge-legends-alive.html)
- [TERMS](https://themindplaying.web.app/terms.html)
- [LAST UFO DEFENSE](https://studyquests.pages.dev/last-ufo-defense.html)
- [SQUID GAME HUNTER](https://quizverses.pages.dev/squid-game-hunter.html)
- [LEAP OF LIFE](https://quizverses.github.io/leap-of-life.html)
- [FUN SORTING THROUGH THE SHELVES](https://iskillplay.web.app/fun-sorting-through-the-shelves.html)
- [STACK UP](https://studyquests.github.io/stack-up.html)
- [CRAFTSMAN 3D GANGSTER](https://quizverses.github.io/craftsman-3d-gangster.html)
- [FARM TILES HARVEST](https://quizverses-9d2f2.web.app/farm-tiles-harvest.html)
- [INDEX37](https://theskillquest.pages.dev/index37.html)
