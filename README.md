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
- [ROYAL PUZZLE BURST](https://mindconvertpt.pages.dev/royal-puzzle-burst.html)
- [BOLTS](https://eduquestspt.pages.dev/bolts.html)
- [CATEGORY PARTY23](https://eduquests.onrender.com/category-party23.html)
- [2 3 4 PLAYER GAMES](https://eduquests.netlify.app/2-3-4-player-games.html)
- [MINI SCRAPBOOK PAPER](https://eduquestses.pages.dev/mini-scrapbook-paper.html)
- [DRAW AND ESCAPE](https://eduquestkr.pages.dev/draw-and-escape.html)
- [MY CITY HOSPITAL](https://quizzesarena.github.io/my-city-hospital.html)
- [HEADLESS JOE](https://ieduquests.web.app/headless-joe.html)
- [SPOTDIFFERS](https://eduquestsjp.pages.dev/spotdiffers.html)
- [CHICKEN BLAST](https://brainquests.pages.dev/chicken-blast.html)
- [CHICKEN WILD RUN](https://quizzesarena.web.app/chicken-wild-run.html)
- [MATCH MASTERS](https://quizzesarena.onrender.com/match-masters.html)
- [CATEGORY DEFENSE176](https://quizzesarena.onrender.com/category-defense176.html)
- [TINY FIGHTER UNSTOPPABLE RUN](https://eduquests.github.io/tiny-fighter-unstoppable-run.html)
- [CATEGORY COLOR197](https://welearnaction.onrender.com/category-color197.html)
- [POPPING CANDIES](https://eduquests.onrender.com/popping-candies.html)
- [CODEQUEST](https://brainquests.pages.dev/codequest.html)
- [CANDY BATTLE SWEET SURVIVORS](https://eduquestkr.pages.dev/candy-battle-sweet-survivors.html)
- [DISASSEMBLE THE PICTURE PUZZLE](https://eduquestsjp.pages.dev/disassemble-the-picture-puzzle.html)
- [ACE CAR RACING](https://quizzesarena.onrender.com/ace-car-racing.html)
- [OHPEACH IT](https://eduquestkr.pages.dev/ohpeach-it.html)
- [SHAPE TRANSFORM BLOB RACING](https://ieduquests.web.app/shape-transform-blob-racing.html)
- [ITALIAN BRAINROT IN GEOMETRY DASH](https://quizzesarena.github.io/italian-brainrot-in-geometry-dash.html)
- [COUNT MASTERS SUPERHERO](https://quizzesarena.github.io/count-masters-superhero.html)
- [PIXEL PATH](https://eduquestkr.pages.dev/pixel-path.html)
- [CATEGORY FREE](https://brainquests.pages.dev/category-free.html)
- [CATEGORY CASUAL969](https://eduquests.onrender.com/category-casual969.html)
- [DRAW AND ESCAPE](https://eduquestsfr.pages.dev/draw-and-escape.html)
- [CUTE COLORING GAMES](https://eduquestsfr.pages.dev/cute-coloring-games.html)
- [BRAIN TEST IQ CHALLENGE 2](https://eduquestkr.pages.dev/brain-test-iq-challenge-2.html)
- [FOONO ONLINE MULTIPLAYER CARD GAME](https://eduquestsjp.pages.dev/foono-online-multiplayer-card-game.html)
- [SUMMER MAZE](https://learnaction.netlify.app/summer-maze.html)
- [INDEX16](https://welearnaction.onrender.com/index16.html)
- [CATEGORY 204828](https://brainquests.pages.dev/category-204828.html)
- [GUESS THE DRAWING](https://ieduquests.web.app/guess-the-drawing.html)
- [INDEX33](https://eduquests.pages.dev/index33.html)
- [CATEGORY MAHJONG 2](https://eduquests.onrender.com/category-mahjong-2.html)
- [FISH STORY 3](https://learnaction.netlify.app/fish-story-3.html)
- [POTION MERGE WITCH](https://eduquests.github.io/potion-merge-witch.html)
- [INDEX37](https://eduquestses.pages.dev/index37.html)
- [STICKER PUZZLE BOOK](https://quizzesarena.onrender.com/sticker-puzzle-book.html)
- [FIX DA BRAINROT](https://eduquestkr.pages.dev/fix-da-brainrot.html)
- [ITALIAN BRAINROT DRAG MERGE PUZZLE](https://eduquestsjp.pages.dev/italian-brainrot-drag-merge-puzzle.html)
- [INDEX21](https://quizzesarena.onrender.com/index21.html)
- [HEXON RUSH](https://ieduquests.web.app/hexon-rush.html)
- [PUZZLE BLOCKS](https://eduquestsfr.pages.dev/puzzle-blocks.html)
- [CONTRACT DEER HUNTER](https://eduquests.github.io/contract-deer-hunter.html)
- [MAHJONG CONNECT FISH WORLD](https://eduquestsfr.pages.dev/mahjong-connect-fish-world.html)
- [BATTLE TANKS FIRESTORM](https://ieduquests.web.app/battle-tanks-firestorm.html)
- [STICKMAN ARCHERO FIGHT STICK SHADOW FIGHT WAR](https://learnaction.netlify.app/stickman-archero-fight-stick-shadow-fight-war.html)
- [SITEMAP](https://brainquests.netlify.app/sitemap.html)
- [METAL GUNS FURY](https://ieduquests.web.app/metal-guns-fury.html)
- [CELEBRITY AESTHETIC CHALLENGE](https://learnaction.netlify.app/celebrity-aesthetic-challenge.html)
- [MONKEY BUBBLE DEFENSE](https://quizzesarena.github.io/monkey-bubble-defense.html)
- [SMART DOTS RELOADED](https://quizzesarena.github.io/smart-dots-reloaded.html)
- [AUTO NINJA](https://eduquestsfr.pages.dev/auto-ninja.html)
- [IDLE ANIMAL ANATOMY](https://eduquests.github.io/idle-animal-anatomy.html)
- [SNIPER SHOOTER 2](https://eduquestsfr.pages.dev/sniper-shooter-2.html)
- [SLOPE EMOJI 2](https://eduquestsfr.pages.dev/slope-emoji-2.html)
- [CATEGORY HERO72](https://eduquestsjp.pages.dev/category-hero72.html)
- [SPLIT SHOT BALL ADVENTURE](https://eduquestsfr.pages.dev/split-shot-ball-adventure.html)
- [SPEEDRUN PLATFORMER](https://eduquestsfr.pages.dev/speedrun-platformer.html)
- [ONLINE PORTAL](https://cryptotify.pages.dev/)
- [SITEMAP](https://thequizzone.pages.dev/sitemap.html)
- [WOODLAND SLIDE](https://eduquestsfr.pages.dev/woodland-slide.html)
- [HIDDEN OBJECTS ISLAND](https://eduquestsfr.pages.dev/hidden-objects-island.html)
- [BOUNCE DUNK BASKETBALL](https://eduquests.github.io/bounce-dunk-basketball.html)
- [ARCHER DUNGEON HERO](https://quizzesarena.github.io/archer-dungeon-hero.html)
- [NEKOS ADVENTURE](https://eduquests.onrender.com/nekos-adventure.html)
- [CATEGORY FREE DRESS UP GAMES](https://quizzesarena.web.app/category-free-dress-up-games.html)
- [BANK ROBBERY 3](https://eduquestsfr.pages.dev/bank-robbery-3.html)
- [BATTLE OF PIRATE CARIBBEAN BATTLE](https://eduquestsfr.pages.dev/battle-of-pirate-caribbean-battle.html)
- [HAPPY FARM THE CROP](https://eduquestsfr.pages.dev/happy-farm-the-crop.html)
- [CATEGORY MOBILE2 112 2](https://quizzesarena.web.app/category-mobile2-112-2.html)
- [BRICK GAME CLASSIC](https://eduquestsjp.pages.dev/brick-game-classic.html)
- [BUS COLOR JAM](https://eduquests.onrender.com/bus-color-jam.html)
- [MINI GAMES PUZZLE COLLECTION](https://ieduquests.web.app/mini-games-puzzle-collection.html)
- [CELEBRITY SPRING MANICURE DESIGN](https://brainquests.pages.dev/celebrity-spring-manicure-design.html)
- [CATEGORY COLOR](https://eduquestsjp.pages.dev/category-color.html)
- [CARJAMCOLOR](https://eduquests.onrender.com/carjamcolor.html)
- [ONLINE PORTAL](https://ilearnworldkr.pages.dev/)
- [CATEGORY GROW99](https://eduquestses.pages.dev/category-grow99.html)
- [ANIMAL SWIPE](https://brainquests.pages.dev/animal-swipe.html)
- [CATEGORY INCREMENTAL388](https://eduquestses.pages.dev/category-incremental388.html)
- [MART PUZZLE SHOPPING SORT](https://eduquestkr.pages.dev/mart-puzzle-shopping-sort.html)
- [FIGHTER STICK HERO](https://brainquests.pages.dev/fighter-stick-hero.html)
- [EMERGENCY JAM](https://eduquestkr.pages.dev/emergency-jam.html)
- [TIMEWALKER SURVIVE](https://eduquests.onrender.com/timewalker-survive.html)
- [CATEGORY CAR 3](https://eduquestses.pages.dev/category-car-3.html)
- [MATH STARS](https://ieduquests.web.app/math-stars.html)
- [DAILY MATCH](https://eduquestsfr.pages.dev/daily-match.html)
- [STOP THE BULLET](https://brainquests.pages.dev/stop-the-bullet.html)
- [SPRUNKI GETS SURGERY](https://eduquests.github.io/sprunki-gets-surgery.html)
- [TANK STARS BATTLE ARENA](https://ieduquests.web.app/tank-stars-battle-arena.html)
- [FAT CAT LIFE](https://brainquests.pages.dev/fat-cat-life.html)
- [LABUBA HALLOWEEN INFESTATION](https://eduquestkr.pages.dev/labuba-halloween-infestation.html)
- [CATEGORY MMO24](https://eduquestsjp.pages.dev/category-mmo24.html)
- [MERGE FLOWERS](https://eduquestsjp.pages.dev/merge-flowers.html)
- [MERGE SQUARES](https://ieduquests.web.app/merge-squares.html)
- [STEALTH MASTER SNEAK CAT](https://eduquestkr.pages.dev/stealth-master-sneak-cat.html)
- [ULTIMATE BRAINROT CLICKER](https://brainquests.pages.dev/ultimate-brainrot-clicker.html)
- [CATEGORY BUSINESS137](https://eduquestses.pages.dev/category-business137.html)
- [PET TILE MASTER](https://eduquestsfr.pages.dev/pet-tile-master.html)
- [GEM DEEP DIGGER](https://brainquests.pages.dev/gem-deep-digger.html)
- [CATEGORY FPS GAMES](https://welearnaction.onrender.com/category-fps-games.html)
- [SPIDER EVOLUTION](https://eduquestsfr.pages.dev/spider-evolution.html)
- [DTA BEST THIEF](https://brainquests.pages.dev/dta-best-thief.html)
- [POXEL IO](https://brainquests.pages.dev/poxel-io.html)
- [WILD WEST MATCH 2 THE GOLD RUSH](https://brainquests.pages.dev/wild-west-match-2-the-gold-rush.html)
- [BLOCK PUZZLE KING](https://eduquests.github.io/block-puzzle-king.html)
- [CHALLENGE YOUR FRIENDS](https://eduquestsfr.pages.dev/challenge-your-friends.html)
- [HOLE DEFENSE](https://eduquests.github.io/hole-defense.html)
- [LAST UFO DEFENSE](https://eduquests.pages.dev/last-ufo-defense.html)
- [FLOWER FAIRY ADVENTURE STORY](https://eduquestkr.pages.dev/flower-fairy-adventure-story.html)
- [MERGE SMITH](https://learnaction.netlify.app/merge-smith.html)
- [MONSTER MERGE LEGENDS ALIVE](https://eduquestses.pages.dev/monster-merge-legends-alive.html)
- [GEOMETRY RUSH](https://learnaction.netlify.app/geometry-rush.html)
- [MERMAIDS SPOT THE DIFFERENCES](https://eduquestkr.pages.dev/mermaids-spot-the-differences.html)
- [BUBBLY LAB](https://eduquests.pages.dev/bubbly-lab.html)
- [GROW WARSIO](https://eduquestses.pages.dev/grow-warsio.html)
- [RACE TIME](https://ieduquests.web.app/race-time.html)
- [POOPY ESCAPE THE PRISON](https://eduquests.pages.dev/poopy-escape-the-prison.html)
- [WORM HUNT](https://eduquestsfr.pages.dev/worm-hunt.html)
- [LOVE ARCHER](https://eduquests.pages.dev/love-archer.html)
- [EYE ART PERFECT MAKEUP ARTIST](https://eduquestsfr.pages.dev/eye-art-perfect-makeup-artist.html)
- [OBBY TOWER](https://eduquestsjp.pages.dev/obby-tower.html)
- [PORTAL TD TOWER DEFENSE](https://brainquests.pages.dev/portal-td-tower-defense.html)
- [COOKIE LAND](https://eduquestsfr.pages.dev/cookie-land.html)
- [CATEGORY CONTROLLER 2](https://eduquests.pages.dev/category-controller-2.html)
- [SORT GAMES CHALLENGE](https://eduquestkr.pages.dev/sort-games-challenge.html)
