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
- [CRYPTOGRAM](https://themindzone.pages.dev/cryptogram.html)
- [TURNFIGHT COM UAP](https://studyplayings.web.app/turnfight-com-uap.html)
- [STICKMAN DUO ESCAPE THE TOMB](https://studyquests.pages.dev/stickman-duo-escape-the-tomb.html)
- [STICKMAN ESCAPE SCHOOL](https://studyplaying.github.io/stickman-escape-school.html)
- [CATEGORY DRESS UP97](https://thelearnquesters.pages.dev/category-dress-up97.html)
- [CAT PANCAKE DINER](https://learnquester.pages.dev/cat-pancake-diner.html)
- [SPLIT SHOT BALL ADVENTURE](https://learnquester.pages.dev/split-shot-ball-adventure.html)
- [CATEGORY PHYSICS371](https://learnquesters.pages.dev/category-physics371.html)
- [CLINIC CLEANUP CREW](https://learnquester.pages.dev/clinic-cleanup-crew.html)
- [ARROW COUNT MASTER](https://quizverses-9d2f2.web.app/arrow-count-master.html)
- [SAVE MY HERO](https://studyquests.github.io/save-my-hero.html)
- [ROAD OF FURY 4](https://learnquester.pages.dev/road-of-fury-4.html)
- [BLOCK BUILDER JAM](https://studyquests.github.io/block-builder-jam.html)
- [CATEGORY DRESS UP97](https://learnquesters.pages.dev/category-dress-up97.html)
- [CATEGORY BIKE 3](https://quizverses.github.io/category-bike-3.html)
- [HIDDEN OBJECTS ISLAND](https://learnquester.pages.dev/hidden-objects-island.html)
- [ZEN TILE](https://learnquester.pages.dev/zen-tile.html)
- [DESSERT DIY](https://learnquester.pages.dev/dessert-diy.html)
- [MINETAP](https://quizverses.github.io/minetap.html)
- [SCREW MATCH](https://studyquests.github.io/screw-match.html)
- [INDEX7](https://studyquesthub.web.app/index7.html)
- [CATEGORY FLASH](https://studyquests.github.io/category-flash.html)
- [DICTATOR SIMULATOR 1984](https://learnquester.pages.dev/dictator-simulator-1984.html)
- [MEGA ESCAPE CAR PARKING PUZZLE](https://learnquester.pages.dev/mega-escape-car-parking-puzzle.html)
- [CATEGORY BIKE 2](https://learnquesters.pages.dev/category-bike-2.html)
- [CATEGORY AGILITY 3](https://studyquests.github.io/category-agility-3.html)
- [DEFORM IT](https://learnquester.pages.dev/deform-it.html)
- [STICK FIGHT THE CHAOS](https://studyquests.pages.dev/stick-fight-the-chaos.html)
- [CATEGORY BASKETBALL](https://learnquesters.pages.dev/category-basketball.html)
- [TERMS](https://brainquests.vercel.app/terms.html)
- [JUMPER](https://studyquesthub.web.app/jumper.html)
- [DRIVER MASTER SIMULATOR](https://learnquester.pages.dev/driver-master-simulator.html)
- [FLAMES FORTUNE](https://learnquester.pages.dev/flames-fortune.html)
- [SUPER ONION BOY 2](https://studyquests.github.io/super-onion-boy-2.html)
- [CATEGORY BUBBLE SHOOTER](https://learnquesters.pages.dev/category-bubble-shooter.html)
- [MYSTIC OBJECT HUNT](https://learnquester.pages.dev/mystic-object-hunt.html)
- [CIRCLE RUN ENDLESS](https://studyquests.pages.dev/circle-run-endless.html)
- [INDEX3](https://thelearnquesters.pages.dev/index3.html)
- [PRIVACY](https://cryptotify.netlify.app/privacy.html)
- [CAT ESCAPE HIDE AND SEEK](https://studyquesthub.web.app/cat-escape-hide-and-seek.html)
- [WOLF LIFE SIMULATOR](https://learnquester.pages.dev/wolf-life-simulator.html)
- [CATEGORY CASUAL 9](https://studyquesthub.web.app/category-casual-9.html)
- [FLOOF MY PET HOUSE](https://studyquests.github.io/floof-my-pet-house.html)
- [ROBIN HOOD ARCHER](https://learnquesters.pages.dev/robin-hood-archer.html)
- [CATEGORY BLOODY29](https://quizverses.github.io/category-bloody29.html)
- [STELLAR MINES SPACE MINER](https://studyquests.github.io/stellar-mines-space-miner.html)
- [CATEGORY DESTROY](https://thelearnquesters.pages.dev/category-destroy.html)
- [PORTAL TD TOWER DEFENSE](https://studyquesthub.web.app/portal-td-tower-defense.html)
- [CATEGORY CONTROLLER 3](https://quizverses.github.io/category-controller-3.html)
- [NUMBER MERGE 10](https://learnquester.pages.dev/number-merge-10.html)
- [THE BASEMENT ISNT THAT HAUNTED](https://quizverses.github.io/the-basement-isnt-that-haunted.html)
- [INDEX6](https://learnquesters.pages.dev/index6.html)
- [CATEGORY SIDE SCROLLING184](https://quizverses.github.io/category-side-scrolling184.html)
- [CATEGORY FPS 3](https://thelearnquesters.pages.dev/category-fps-3.html)
- [ANIMAL MERGE BUBBLE SHOOTER](https://quizverses.github.io/animal-merge-bubble-shooter.html)
- [SITEMAP](https://quizverses.github.io/sitemap.html)
- [CATEGORY BOOKMARK](https://studyplaying.github.io/category-bookmark.html)
- [FACE CHANGES](https://learnquesters.pages.dev/face-changes.html)
- [SUPERMARKET SIMULATOR DREAM STORE](https://studyquests.pages.dev/supermarket-simulator-dream-store.html)
- [MOJO EMOJI](https://studyquests.pages.dev/mojo-emoji.html)
- [ALPHABET MERGE AND FIGHT](https://studyquesthub.web.app/alphabet-merge-and-fight.html)
- [INDEX37](https://thelearnquesters.pages.dev/index37.html)
- [CATEGORY POINT AND CLICK124](https://learnquesters.pages.dev/category-point-and-click124.html)
- [CLEANING SIMULATOR](https://learnquesters.pages.dev/cleaning-simulator.html)
- [REAL STREET FIGHTER 3D](https://learnquesters.pages.dev/real-street-fighter-3d.html)
- [HOMO EVOLUTION](https://learnquester.pages.dev/homo-evolution.html)
- [INDEX18](https://studyquesthub.web.app/index18.html)
- [CONTACT](https://quizverses-9d2f2.web.app/contact.html)
- [CHICKEN WARS MERGE GUNS](https://quizverses.github.io/chicken-wars-merge-guns.html)
- [MEGA LAMBA RAMP](https://learnquesters.pages.dev/mega-lamba-ramp.html)
- [INDEX25](https://thelearnquesters.pages.dev/index25.html)
- [ARROWTIX TRAIN YOUR BRAIN](https://learnquester.pages.dev/arrowtix-train-your-brain.html)
- [CATEGORY MERGE](https://learnquesters.pages.dev/category-merge.html)
- [INDEX10](https://thelearnquesters.pages.dev/index10.html)
- [SQUID GAME MEMORY CARD MATCH](https://studyquests.github.io/squid-game-memory-card-match.html)
- [BUBBLE SHOOTER POP](https://quizverses.github.io/bubble-shooter-pop.html)
- [MY GARDEN JOURNEY](https://learnquester.pages.dev/my-garden-journey.html)
- [HOME PIN 1](https://quizverses.github.io/home-pin-1.html)
- [HORROR SCHOOL DETECTIVE STORY](https://studyquests.github.io/horror-school-detective-story.html)
- [THE TRENDY MERMAID](https://studyquests.github.io/the-trendy-mermaid.html)
- [CATEGORY RACING DRIVING](https://learnquesters.pages.dev/category-racing-driving.html)
- [ARCADE GP](https://learnquesters.pages.dev/arcade-gp.html)
- [DELIVERY NOW](https://quizverses.github.io/delivery-now.html)
- [CATEGORY MERGE221](https://studyquesthub.web.app/category-merge221.html)
- [ZOMBIE REDEMPTION](https://studyquests.github.io/zombie-redemption.html)
- [MR DISC SLINGSHOT STRIKE](https://learnquester.pages.dev/mr-disc-slingshot-strike.html)
- [SINGLE STROKE LINE DRAW](https://learnquesters.pages.dev/single-stroke-line-draw.html)
- [HORROR MINECRAFT PARTYTIME](https://studyplaying.github.io/horror-minecraft-partytime.html)
- [MICKEY RUN ADVENTURE GAME](https://studyquesthub.web.app/mickey-run-adventure-game.html)
- [CATEGORY DESTROY256](https://studyquests.github.io/category-destroy256.html)
- [DOWNHILL CAR RIDE CRASH TEST](https://studyplayings.web.app/downhill-car-ride-crash-test.html)
- [HALLOWEEN CHALLENGE](https://studyplayings.web.app/halloween-challenge.html)
- [CATEGORY 3D1 371](https://studyquests.github.io/category-3d1-371.html)
- [OBBY PINATA PARTY](https://studyquests.pages.dev/obby-pinata-party.html)
- [GRIDDLERS DELUXE](https://studyquests.pages.dev/griddlers-deluxe.html)
- [CATEGORY DESTROY256](https://thelearnquesters.pages.dev/category-destroy256.html)
- [CATEGORY STICKMAN 2](https://studyplayings.web.app/category-stickman-2.html)
- [SQUARE WORLD 3D](https://studyplaying.github.io/square-world-3d.html)
- [GEOMETRY VIBES MONSTER](https://quizverses.github.io/geometry-vibes-monster.html)
- [ELLIE AND FRIENDS VENICE CARNIVAL](https://learnquesters.pages.dev/ellie-and-friends-venice-carnival.html)
- [CATEGORY MMO25](https://studyplayings.pages.dev/category-mmo25.html)
- [INDEX23](https://quizverses.github.io/index23.html)
- [CAMERAMAN VS TOILETS PUZZLE](https://learnquesters.pages.dev/cameraman-vs-toilets-puzzle.html)
- [BUTTERFLY KYODAI DELUXE 2](https://learnquester.pages.dev/butterfly-kyodai-deluxe-2.html)
- [GRIDDLERS DELUXE](https://studyplaying.github.io/griddlers-deluxe.html)
- [CATEGORY MOUSE1 697](https://quizverses.github.io/category-mouse1-697.html)
- [BALLOON MATCH 3D](https://learnquester.pages.dev/balloon-match-3d.html)
- [3D SUPER ROLLING BALL RACE](https://studyquests.pages.dev/3d-super-rolling-ball-race.html)
- [FASHION VALKYRIES SAGA OF STYLE](https://studyquests.pages.dev/fashion-valkyries-saga-of-style.html)
- [VEHICLE FUN RACE](https://quizverses.github.io/vehicle-fun-race.html)
- [FIND THE GHOST CAT](https://learnquester.github.io/find-the-ghost-cat.html)
- [DARLING DOLL](https://studyquests.github.io/darling-doll.html)
- [SAND BLAST](https://studyquesthub.web.app/sand-blast.html)
- [MR THROW](https://quizverses.github.io/mr-throw.html)
- [TUNG SAHUR BOTS CHASE ROOM](https://learnquester.pages.dev/tung-sahur-bots-chase-room.html)
- [MINI GAMES CASUAL COLLECTION](https://theskillquest.pages.dev/mini-games-casual-collection.html)
- [HIGHSCHOOL MEAN GIRLS 3](https://themindplay.github.io/highschool-mean-girls-3.html)
- [MOJO EMOJI](https://studyplaying.github.io/mojo-emoji.html)
- [PRINCESS WINTER ICE SKATING OUTFITS](https://thequizzone.pages.dev/princess-winter-ice-skating-outfits.html)
- [MONSTER IMPACT](https://studyquesthub.web.app/monster-impact.html)
- [RAGDOLL BOUNCE](https://quizverses.github.io/ragdoll-bounce.html)
- [I8 CITY DRIVER](https://theskillquest.pages.dev/i8-city-driver.html)
- [ONLINE PORTAL](https://cryptotify9.onrender.com/)
- [IDLE TRADE ROUTES](https://studyplayings.pages.dev/idle-trade-routes.html)
- [SQUARE PUNKI LONG HAND](https://quizverses.github.io/square-punki-long-hand.html)
- [BUBBLE BALL](https://studyplayings.web.app/bubble-ball.html)
- [BIG BLOCK BLAST](https://themindzone.pages.dev/big-block-blast.html)
- [MAGIC TRI PEAKS SOLITAIRE](https://thelearnquesters.pages.dev/magic-tri-peaks-solitaire.html)
- [MR CAPPUCCINO ASSASSINO](https://theskillquest.pages.dev/mr-cappuccino-assassino.html)
- [ANACONDA RUNNER](https://thelearnquesters.pages.dev/anaconda-runner.html)
