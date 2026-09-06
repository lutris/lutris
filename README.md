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
- [PALKOVIL THE WAY HOME](https://learnquester.github.io/palkovil-the-way-home.html)
- [2 3 4 PLAYER GAMES](https://studyquesthub.web.app/2-3-4-player-games.html)
- [CATEGORY MOUSE](https://studyplayings.pages.dev/category-mouse.html)
- [REAL RACING 3D](https://iskillquest.pages.dev/real-racing-3d.html)
- [BARBEE SUMMER VACATION](https://learnquester.github.io/barbee-summer-vacation.html)
- [SOLITAIRE KLONDIKE](https://studyplayings.pages.dev/solitaire-klondike.html)
- [ITALIAN BRAINROT BABY CLICKER](https://quizverses.github.io/italian-brainrot-baby-clicker.html)
- [BLOCKSSS](https://quizverses.github.io/blocksss.html)
- [INDEX19](https://quizverses.github.io/index19.html)
- [MAHJONG PET QUEST](https://quizverses.pages.dev/mahjong-pet-quest.html)
- [CATEGORY EDUCATIONAL25](https://studyplayings.pages.dev/category-educational25.html)
- [CATEGORY FPS 2](https://quizverses.github.io/category-fps-2.html)
- [CANDY POP MANIA](https://learnquester.github.io/candy-pop-mania.html)
- [BATTLESHIP](https://learnquester.github.io/battleship.html)
- [JUST LUDO](https://learnquester.github.io/just-ludo.html)
- [KILLER ESCAPE HUGGY EXTREME](https://learnquester.github.io/killer-escape-huggy-extreme.html)
- [HERO PIPE](https://quizverses.pages.dev/hero-pipe.html)
- [MEAN GIRLS GRADUATION DAY](https://studyplayings.web.app/mean-girls-graduation-day.html)
- [CUT GRASS](https://studyquests.github.io/cut-grass.html)
- [ROBYBOX SPACE STATION WAREHOUSE](https://quizverses.github.io/robybox-space-station-warehouse.html)
- [WORD ART COLOR BOOK PUZZLE](https://studyquests.github.io/word-art-color-book-puzzle.html)
- [OFFICE BRAWL ROOM SMASH](https://studyplayings.web.app/office-brawl-room-smash.html)
- [MINI GAMES CASUAL COLLECTION](https://quizverses.pages.dev/mini-games-casual-collection.html)
- [ESCAPE ROOM MYSTERY KEY](https://learnquester.github.io/escape-room-mystery-key.html)
- [MAKE AMERICA GREAT AGAIN](https://quizverses.pages.dev/make-america-great-again.html)
- [CATEGORY CONTROLLER](https://quizverses.github.io/category-controller.html)
- [LOST PUPPY RESCUE AND CARE](https://studyquests.github.io/lost-puppy-rescue-and-care.html)
- [CATEGORY SOCCER 3](https://quizverses.github.io/category-soccer-3.html)
- [ITILEZEN SORT PUZZLE](https://studyplayings.web.app/itilezen-sort-puzzle.html)
- [CATEGORY CARE](https://quizverses-9d2f2.web.app/category-care.html)
- [INDEX17](https://studyplayings.pages.dev/index17.html)
- [INDEX14](https://studyplayings.pages.dev/index14.html)
- [CATEGORY POOL 2](https://quizverses.pages.dev/category-pool-2.html)
- [WAVE CHIC OCEAN FASHION FRENZY](https://quizverses-9d2f2.web.app/wave-chic-ocean-fashion-frenzy.html)
- [KEY QUEST](https://learnquester.github.io/key-quest.html)
- [COLOR MIX JELLY MERGE](https://studyquests.github.io/color-mix-jelly-merge.html)
- [BALL PAINT 3D](https://studyquests.github.io/ball-paint-3d.html)
- [GALAXY CARNAGE](https://learnquester.github.io/galaxy-carnage.html)
- [MUSIC RUSH](https://studyplayings.web.app/music-rush.html)
- [ZOMBIE SHOOTING KING](https://quizverses-9d2f2.web.app/zombie-shooting-king.html)
- [CATEGORY CAN T STOP PLAYING215](https://quizverses.github.io/category-can-t-stop-playing215.html)
- [NINJA OBBY PARKOUR](https://quizverses.github.io/ninja-obby-parkour.html)
- [TWO RX7 DRIFTERS](https://quizverses.github.io/two-rx7-drifters.html)
- [SPRUNKI POPIT](https://studyplayings.web.app/sprunki-popit.html)
- [BLIND BOAT SHOOTING MASTER](https://learnquester.github.io/blind-boat-shooting-master.html)
- [BMG CRASHDAY 2025](https://learnquester.github.io/bmg-crashday-2025.html)
- [BANK ROBBERY ESCAPE](https://quizverses.github.io/bank-robbery-escape.html)
- [FAST LAP](https://studyplayings.web.app/fast-lap.html)
- [CROWN CANNON](https://studyquests.github.io/crown-cannon.html)
- [LAST TO LEAVE CIRCLE OBBY](https://quizverses.pages.dev/last-to-leave-circle-obby.html)
- [BRIDGE FIGHT](https://quizverses.github.io/bridge-fight.html)
- [NIGHT CLUB SECURITY](https://learnquester.github.io/night-club-security.html)
- [RAGDOLL SHOW THROW BREAK AND DESTROY](https://studyplayings.web.app/ragdoll-show-throw-break-and-destroy.html)
- [CATEGORY MMO25](https://studyplayings.pages.dev/category-mmo25.html)
- [CATEGORY STRATEGY](https://studyplayings.pages.dev/category-strategy.html)
- [INDEX13](https://quizverses.pages.dev/index13.html)
- [CATEGORY ADVENTURE](https://thelearnquester.web.app/category-adventure.html)
- [BACKGAMMON DUEL](https://quizverses.pages.dev/backgammon-duel.html)
- [DOP PUZZLE ERASE MASTER](https://studyplayings.web.app/dop-puzzle-erase-master.html)
- [CATEGORY ANIMAL216](https://studyquesthub.web.app/category-animal216.html)
- [POKER QUEST](https://studyquests.github.io/poker-quest.html)
- [TROPICAL MATCH](https://studyquests.github.io/tropical-match.html)
- [CAR CARE REPAIR DUDU MECHANIC](https://quizverses.pages.dev/car-care-repair-dudu-mechanic.html)
- [INDEX30](https://studyquests.github.io/index30.html)
- [INDEX8](https://studyplayings.pages.dev/index8.html)
- [CINDERELLA DRESS UP GIRL GAMES](https://studyplayings.web.app/cinderella-dress-up-girl-games.html)
- [X TO Y ALMOST IMPOSSIBLE](https://quizverses.github.io/x-to-y-almost-impossible.html)
- [LAMBO TRAFFIC RACER](https://studyquests.github.io/lambo-traffic-racer.html)
- [BLACK CAT STACKING POP](https://quizverses.github.io/black-cat-stacking-pop.html)
- [CATEGORY MAKEUP CATEGORY](https://quizverses.pages.dev/category-makeup-category.html)
- [ZOMBIE RODEO MULTIPLICATION](https://studyplayings.web.app/zombie-rodeo-multiplication.html)
- [FURY OF THE STEAMPUNK PRINCESS](https://studyplayings.web.app/fury-of-the-steampunk-princess.html)
- [CAFE OWNER BUSINESS SIMULATOR](https://studyquests.github.io/cafe-owner-business-simulator.html)
- [CATEGORY FLASH 2](https://studyquesthub.web.app/category-flash-2.html)
- [FORMULA RACING GAMES CAR GAME](https://studyquests.github.io/formula-racing-games-car-game.html)
- [FEET DOCTOR URGENCY CARE](https://learnquester.github.io/feet-doctor-urgency-care.html)
- [ECHOLOCATION SHOOTER](https://quizverses.pages.dev/echolocation-shooter.html)
- [CATEGORY ART](https://quizverses.pages.dev/category-art.html)
- [TINY FARM](https://quizverses.pages.dev/tiny-farm.html)
- [STICKMAN HALLOWEEN SURVIVE](https://studyplayings.web.app/stickman-halloween-survive.html)
- [GET READY WITH ME CONCERT DAY](https://studyquests.github.io/get-ready-with-me-concert-day.html)
- [GUN RUSH](https://quizverses.pages.dev/gun-rush.html)
- [ARCHERY RAGDOLL](https://learnquester.github.io/archery-ragdoll.html)
- [ITALIAN BRAINROT QUIZ](https://learnquester.github.io/italian-brainrot-quiz.html)
- [MOBILE PHONE CASE DIY](https://studyplayings.web.app/mobile-phone-case-diy.html)
- [CATEGORY COLLECT565](https://thelearnquester.web.app/category-collect565.html)
- [BINGO HALLOWEEN](https://learnquester.github.io/bingo-halloween.html)
- [KICK THE NOOBIK 3D](https://studyplayings.web.app/kick-the-noobik-3d.html)
- [TYPE SPRINT](https://quizverses.github.io/type-sprint.html)
- [CATEGORY CASUAL](https://thelearnquester.web.app/category-casual.html)
- [MERGE SQUARES](https://quizverses.pages.dev/merge-squares.html)
- [CYBER ARROW](https://learnquester.github.io/cyber-arrow.html)
- [ROBOT RUNNER FIGHT](https://studyquests.github.io/robot-runner-fight.html)
- [SORTSTORE](https://studyquests.github.io/sortstore.html)
- [CATEGORY BASKETBALL 3](https://studyquests.github.io/category-basketball-3.html)
- [LEAP OF LIFE](https://studyplayings.pages.dev/leap-of-life.html)
- [INDEX4](https://thelearnquester.web.app/index4.html)
- [LABUBU MERGE](https://learnquester.github.io/labubu-merge.html)
- [CATEGORY SORTING44](https://thelearnquester.web.app/category-sorting44.html)
- [MINI GOLF BATTLE](https://studyplayings.web.app/mini-golf-battle.html)
- [TIED UP](https://studyplayings.web.app/tied-up.html)
- [CATEGORY CASUAL 4](https://thelearnquester.web.app/category-casual-4.html)
- [CATEGORY CASUAL 5](https://quizverses.github.io/category-casual-5.html)
- [ELLIE AND FRIENDS GET READY FOR FIRST DATE](https://learnquester.github.io/ellie-and-friends-get-ready-for-first-date.html)
- [WORD MINE](https://learnquester.github.io/word-mine.html)
- [IDOL LIVESTREAM DOLL DRESS UP](https://learnquester.github.io/idol-livestream-doll-dress-up.html)
- [CATEGORY COLLECT565](https://studyquesthub.web.app/category-collect565.html)
- [OBBY POGO PARKOUR](https://quizverses.github.io/obby-pogo-parkour.html)
- [BLACK PINK HALLOWEEN CONCERT](https://quizverses.pages.dev/black-pink-halloween-concert.html)
- [PARKING DRIVER](https://quizverses.pages.dev/parking-driver.html)
- [PET CONNECT MATCH](https://learnquester.github.io/pet-connect-match.html)
- [CATEGORY DRESS UP](https://quizverses.github.io/category-dress-up.html)
- [CATEGORY ESCAPE](https://thelearnquester.web.app/category-escape.html)
- [INDEX5](https://thelearnquester.web.app/index5.html)
- [TILE HEX WORLD RED VS BLUE](https://studyquesthub.web.app/tile-hex-world-red-vs-blue.html)
- [LITTLE BUGS](https://quizverses.github.io/little-bugs.html)
- [CATEGORY CAN T STOP PLAYING212](https://studyquesthub.web.app/category-can-t-stop-playing212.html)
- [IDLE FACTORY DOMINATION](https://studyplayings.web.app/idle-factory-domination.html)
- [CATEGORY POOL 2](https://studyplayings.pages.dev/category-pool-2.html)
- [CATEGORY BUILDING179](https://studyquests.github.io/category-building179.html)
- [CATEGORY PREMIUM PERKS71](https://studyquests.github.io/category-premium-perks71.html)
- [HAPPY FLUFFY CUBES](https://studyplayings.web.app/happy-fluffy-cubes.html)
- [ROBOT TERMINATOR T REX](https://studyquests.github.io/robot-terminator-t-rex.html)
- [SHIP CONTROL 3D](https://studyquesthub.web.app/ship-control-3d.html)
- [CATEGORY RELAXING221](https://thelearnquester.web.app/category-relaxing221.html)
- [WORM OUT BRAIN TEASER GAMES](https://studyplayings.web.app/worm-out-brain-teaser-games.html)
- [BUBBLE SHOOTER PANDA BLAST](https://learnquester.github.io/bubble-shooter-panda-blast.html)
- [THEO MORINIS MAGICAL RESORT](https://learnquester.github.io/theo-morinis-magical-resort.html)
- [ARCADE ROPE](https://studyquests.github.io/arcade-rope.html)
- [CATEGORY FOOD95](https://studyplayings.pages.dev/category-food95.html)
