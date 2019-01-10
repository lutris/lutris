==================
Writing installers
==================

See an example installer at the end of this document.

Fetching required files
=======================

The ``files`` section of the installer references every file needed for
installing the game. This section's keys are unique identifier used later in
the ``installer`` section. The value can either be a string containing a URI
pointing at the required file or a dictionary containing the ``filename`` and
``url`` keys. The ``url`` key is equivalent to passing only a string to the
installer and the ``filename`` key will be used to give the local copy another
name. If you need to set referer use ``referer`` key.

If the game contains copyrighted files that cannot be redistributed, the value
should begin with ``N/A``. When the installer encounter this value, it will
prompt the user for the location of the file. To indicate to the user what file
to select, append a message to ``N/A`` like this:
``N/A:Please select the installer for this game``

Examples:

::

    files:
    - file1: https://example.com/gamesetup.exe
    - file2: "N/A:Select the game's setup file"
    - file3:
        url: https://example.com/url-that-doesnt-resolve-to-a-proper-filename
        filename: actual_local_filename.zip
        referer: www.mywebsite.com


If the game makes use of (Windows) Steam data, the value should be
``$WINESTEAM:appid:path/to/data``. This will check that the data is available
or install it otherwise.


Installer meta data
===================

Referencing the main file
---------------------------

For Linux and Wine games, specify the executable file with the ``exe``
directive. The given path is relative to the game directory.
Example: ``exe: game.sh``

For emulator games, in case you don't ask the user to select the rom
directly but make the installer extract it from an archive or something, you
can reference the rom with the ``main_file`` parameter.
Example: ``main_file: game.rom``

For web games, specify the game's URL (or filename) with ``main_file``.
Example: ``main_file: http://www...``

Customizing the game's name
---------------------------

Use the ``custom-name`` directive to override the name of the game. Use this
only if the installer provides a significantly different game from the base
one.
(Note: In a future update, custom names will be added as game aliases so they
can be searchable)

Example: ``custom-name: Quake Champions: Doom Edition``

Presetting game parameters
--------------------------

The ``game`` directive lets you preset game parameters and options. Available
parameters depend on the runner:

*   linux: ``args`` (optional command arguments), ``working_dir``
    (optional working directory, defaults to the exe's dir).

*   wine:  ``args``, ``arch`` (optional WINEARCH), ``prefix`` (optional Wine prefix), ``working_dir`` (optional
    working directory, defaults to the exe's dir).

*   winesteam: ``args``, ``prefix`` (optional Wine prefix).

Example (Windows game):

::

    game:
      exe: drive_c/Game/game.exe
      prefix: $GAMEDIR
      args: -arg

Runner configuration
--------------------

The runner can be preconfigured from the installer.
The name of the directive is the slug name of the runner,
for example ``wine``. Available parameters depend on the runner.
The best way to set this is to add the game to Lutris, tweak the
runner config and then copy it from ``.config/lutris/games/<game name and id>.yml``.

Example for Wine (set wine version for this installer):

::

    wine:
      version: overwatch-2.15-x86_64

System configuration
--------------------

The ``system`` directive lets you preset the system config for the game.

Example (setting some environment variables):

::

    system:
      env:
        __GL_SHADER_DISK_CACHE: '1'
        __GL_THREADED_OPTIMIZATIONS: '1'
        mesa_glthread: 'true'

Requiring additional binaries
-----------------------------

If the game or the installer needs some system binaries to run, you can specify
them in the `require-binaries` directive. The value is a comma-separated list
of required binaries (acting as AND), if one of several binaries are able to
run the program, you can add them as a ``|`` separated list (acting as OR).

Example

::

    # This requires cmake to be installed and either ggc or clang
    require-binaries: cmake, gcc | clang

Mods and add-ons
----------------

Mods and add-ons require that a base game is already installed on the system.
You can let the installer know that you want to install an add-on by specifying
the ``requires`` directive. The value of ``requires`` must be the canonical
slug name of the base game, not one of its aliases. For example, to install the
add-on "The reckoning" for Quake 2, you should add: ``requires: quake-2``

You can also add complex requirements following the same syntax as the
``require-binaries`` directive described above.


Writing the installation script
===============================

After every file needed by the game has been aquired, the actual installation
can take place. A series of directives will tell the installer how to set up
the game correctly. Start the installer section with ``installer:`` then stack
the directives by order of execution (top to bottom).

Displaying an 'Insert disc' dialog
----------------------------------

The ``insert-disc`` command will display a message box to the user requesting
him to insert the game's disc into the optical drive.

Ensure a correct disc detection by specifying a file or folder present on the
disc with the ``requires`` parameter.

The $DISC variable will contain the drive's path for use in subsequent
installer tasks.

A link to CDEmu's homepage and PPA will also be displayed if the program isn't
detected on the machine, otherwise it will be replaced with a button to open
gCDEmu. You can override this default text with the ``message`` parameter.

Example:

::

    - insert-disc:
        requires: diablosetup.exe

Moving files and directories
----------------------------

Move files or directories by using the ``move`` command. ``move``  requires
two parameters: ``src`` (the source file or folder) and ``dst`` (the
destination folder).

The ``src`` parameter can either be a ``file ID`` or a path relative to game
dir. If the parameter value is not found in the list of file ids,
then it must be prefixed by either ``$CACHE`` or ``$GAMEDIR`` to move a file or
directory from the download cache or the game's install dir, respectively.

The ``dst`` parameter should be prefixed by either ``$GAMEDIR`` or ``$HOME``
to move files to path relative to the game dir or the current user's home

If the source is a ``file ID``, it will be updated with the new destination
path. It can then be used in following commands to access the moved file.

The ``move`` command cannot overwrite files.

Example:

::

    - move:
        src: game_file_id
        dst: $GAMEDIR/location

Copying and merging directories
-------------------------------

Both merging and copying actions are done with the ``merge`` or the ``copy`` directive.
It is not important which of these directives is used because ``copy`` is just an alias for ``merge``.
Whether the action does a merge or copy depends on the existence of the
destination directory. When merging into an existing directory, original files
with the same name as the ones present in the merged directory will be
overwritten. Take this into account when writing your script and order your
actions accordingly.

If the source is a ``file ID``, it will be updated with the new destination
path. It can then be used in following commands to access the copied file.

Example:

::

    - merge:
        src: game_file_id
        dst: $GAMEDIR/location

Extracting archives
-------------------

Extracting archives is done with the ``extract`` directive, the ``file``
argument is a ``file id`` or a file path. If the archive should be extracted
in some other location than the ``$GAMEDIR``, you can specify a ``dst``
argument.

You can optionally specify the archive's type with the ``format`` option.
This is useful if the archive's file extension does not match what it should
be. Accepted values for ``format`` are: zip, tgz, gzip and bz2.

Example:

::

    - extract:
        file: game_archive
        dst: $GAMEDIR/datadir/

Making a file executable
------------------------

Marking the file as executable is done with the ``chmodx`` directive. It is often
needed for games that ship in a zip file, which does not retain file
permissions.

Example: ``- chmodx: $GAMEDIR/game_binary``

Executing a file
----------------

Execute files with the ``execute`` directive. Use the ``file`` parameter to
reference a ``file id`` or a path, ``args`` to add command arguments,
``terminal`` (set to "true") to execute in a new terminal window, ``working_dir``
to set the directory to execute the command in (defaults to the install path).
The command is executed within the Lutris Runtime (resolving most shared
library dependencies). The file is made executable if necessary, no need to run
chmodx before. You can also use ``env`` (environment variables), ``exclude_processes`` (space-separated list of processes to exclude from being watched), ``include_processes`` (the opposite of ``exclude_processes``, is used to override Lutris' built-in exclude list) and ``disable_runtime`` (run a process without the Lutris Runtime, useful for running system binaries).

Example:

::

    - execute:
        args: --argh
        file: great_id
        terminal: true
        env:
          key: value

You can use the ``command`` parameter instead of ``file`` and ``args``. This
lets you run bash/shell commands easier. ``bash`` is used and is added to ``include_processes`` internally.

Example:

::

    - execute:
        command: 'echo Hello World! | cat'

Writing files
-------------

Writing text files
~~~~~~~~~~~~~~~~~~

Create or overwrite a file with the ``write_file`` directive. Use the ``file``
(an absolute path or a ``file id``) and ``content`` parameters.

You can also use the optional parameter ``mode`` to specify a file write mode.
Valid values for ``mode`` include ``w`` (the default, to write to a new file)
or ``a`` to append data to an existing file.

Refer to the YAML documentation for reference on how to including multiline
documents and quotes.

Example:

::

    - write_file:
        file: $GAMEDIR/myfile.txt
        content: 'This is the contents of the file.'

Writing into an INI type config file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modify or create a config file with the ``write_config`` directive. A config file
is a text file composed of key=value (or key: value) lines grouped under
[sections]. Use the ``file`` (an absolute path or a ``file id``), ``section``,
``key`` and ``value`` parameters or the ``data`` parameter. Set ``merge: false``
to first truncate the file. Note that the file is entirely rewritten and
comments are left out; Make sure to compare the initial and resulting file to
spot any potential parsing issues.

Example:

::

    - write_config:
        file: $GAMEDIR/myfile.ini
        section: Engine
        key: Renderer
        value: OpenGL

::

    - write_config:
        file: $GAMEDIR/myfile.ini
        data:
          General:
            iNumHWThreads: 2
            bUseThreadedAI: 1


Writing into a JSON type file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modify or create a JSON file with the ``write_json`` directive.
Use the ``file`` (an absolute path or a ``file id``) and ``data`` parameters.
Note that the file is entirely rewritten; Make sure to compare the initial
and resulting file to spot any potential parsing issues. You can set the optional parameter ``merge`` to ``false`` if you want to overwrite the JSON file instead of updating it.

Example:

::

    - write_json:
        file: $GAMEDIR/myfile.json
        data:
          Sound:
            Enabled: 'false'

This writes (or updates) a file with the following content:

::

    {
      "Sound": {
        "Enabled": "false"
      }
    }

Running a task provided by a runner
-----------------------------------

Some actions are specific to some runners, you can call them with the ``task``
command. You must at least provide the ``name`` parameter which is the function
that will be called. Other parameters depend on the task being called. It is
possible to call functions from other runners by prefixing the task name with
the runner's name (e.g., from a dosbox installer you can use the wineexec task
with ``wine.wineexec`` as the task's ``name``)

Currently, the following tasks are implemented:

*   wine / winesteam: ``create_prefix`` Creates an empty Wine prefix at the
    specified path. The other wine/winesteam directives below include the
    creation of the prefix, so in most cases you won't need to use the
    create_prefix command. Parameters are:

    * ``prefix``: the path

    * ``arch``: optional architecture of the prefix, default: win64 unless a
      32bit build is specified in the runner options.

    * ``overrides``: optional dll overrides, format described later

    * ``install_gecko``: optional variable to stop installing gecko

    * ``install_mono``: optional variable to stop installing mono

    Example:

    ::

        - task:
            name: create_prefix
            prefix: $GAMEDIR
            arch: win64

*   wine / winesteam: ``wineexec`` Runs a windows executable. Parameters are
    ``executable`` (``file ID`` or path), ``args`` (optional arguments passed
    to the executable), ``prefix`` (optional WINEPREFIX),
    ``arch`` (optional WINEARCH, required when you created win64 prefix), ``blocking`` (if true, do not run the process in a thread), ``working_dir`` (optional working directory), ``include_processes``  (optional space-separated list of processes to include to
    being watched)
    ``exclude_processes`` (optional space-separated list of processes to exclude from
    being watched), ``env`` (optional environment variables), ``overrides`` (optional dll overrides).

    Example:

    ::

        - task:
            name: wineexec
            prefix: $GAMEDIR
            executable: drive_c/Program Files/Game/Game.exe
            args: --windowed

*   wine / winesteam: ``winetricks`` Runs winetricks with the ``app`` argument.
    ``prefix`` is an optional WINEPREFIX path. You can run many tricks at once by adding more to the ``app`` parameter (space-separated).

    By default Winetricks will run in silent mode but that can cause issues
    with some components such as XNA. In such cases, you can provide the
    option ``silent: false``

    Example:

    ::

        - task:
            name: winetricks
            prefix: $GAMEDIR
            app: nt40

*   wine / winesteam: ``winecfg`` runs execute winecfg in your ``prefix`` argument. Parameters are
    ``prefix`` (optional wineprefix path), ``arch`` (optional WINEARCH, required when you created win64 prefix),
    ``config`` (dunno what is is).

    example:

    ::

        - task:
            name: winecfg
            prefix: $GAMEDIR
            config: config-file
            arch: win64

*   wine / winesteam: ``joycpl`` runs joycpl in your ``prefix`` argument. Parameters are
    ``prefix`` (optional wineprefix path), ``arch`` (optional WINEARCH, required when you created win64 prefix).

    example:

    ::

        - task:
            name: joypl
            prefix: $GAMEDIR
            arch: win64

*   wine / winesteam: ``eject_disk`` runs eject_disk in your ``prefix`` argument. parameters are
    ``prefix`` (optional wineprefix path).

    example:

    ::

        - task:
            name: eject_disc
            prefix: $GAMEDIR

*   wine / winesteam: ``disable_desktop_integration`` remove links to user directories in a ``prefix`` argument. parameters are
    ``prefix`` (wineprefix path).

    example:

    ::

        - task:
            name: eject_disc
            prefix: $GAMEDIR


*   wine / winesteam: ``set_regedit`` Modifies the Windows registry. Parameters
    are ``path`` (the registry path, use backslashes), ``key``, ``value``,
    ``type`` (optional value type, default is REG_SZ (string)), ``prefix``
    (optional WINEPREFIX), ``arch``
    (optional architecture of the prefix, required when you created win64 prefix).

    Example:

    ::

        - task:
            name: set_regedit
            prefix: $GAMEDIR
            path: HKEY_CURRENT_USER\Software\Valve\Steam
            key: SuppressAutoRun
            value: '00000000'
            type: REG_DWORD
            arch: win64

*   wine / winesteam: ``delete_registry_key`` Deletes registry key in the Windows registry. Parameters
    are ``key``, ``prefix``
    (optional WINEPREFIX), ``arch`` (optional architecture of the prefix, required when you created win64 prefix).

    Example:

    ::

        - task:
            name: set_regedit
            prefix: $GAMEDIR
            path: HKEY_CURRENT_USER\Software\Valve\Steam
            key: SuppressAutoRun
            value: '00000000'
            type: REG_DWORD
            arch: win64

* wine / winesteam: ``set_regedit_file`` Apply a regedit file to the
  registry, Parameters are ``filename`` (regfile name),
  ``arch`` (optional architecture of the prefix, required when you created win64 prefix).


  Example::

    - task:
        name: set_regedit_file
        prefix: $GAMEDIR
        filename: myregfile
        arch: win64

* wine / winesteam: ``winekill`` Stops processes running in Wine prefix. Parameters
  are ``prefix`` (optional WINEPREFIX),
  ``arch`` (optional architecture of the prefix, required when you created win64 prefix).

  Example

  ::

    - task:
        name: winekill
        prefix: $GAMEDIR
        arch: win64

*   dosbox: ``dosexec`` Runs dosbox. Parameters are ``executable`` (optional
    ``file ID`` or path to executable), ``config_file``
    (optional ``file ID`` or path to .conf file), ``args`` (optional command
    arguments), ``working_dir`` (optional working directory, defaults to the
    ``executable``'s dir or the ``config_file``'s dir), ``exit`` (set to
    ``false`` to prevent DOSBox to exit when the ``executable`` is terminated).

    Example:

    ::

        - task:
            name: dosexec
            executable: file_id
            config: $GAMEDIR/game_install.conf
            args: -scaler normal3x -conf more_conf.conf

Displaying a drop-down menu with options
----------------------------------------

Request input from the user by displaying a menu filled with options to choose
from with the ``input_menu`` directive.
The ``description`` parameter holds the message to the user, ``options`` is an
indented list of ``value: label`` lines where "value" is the text that will be
stored and "label" is the text displayed, and the optional ``preselect``
parameter is the value to preselect for the user.

The result of the last input directive is available with the ``$INPUT`` alias.
If need be, you can add an ``id`` parameter to the directive which will make the
selected value available with ``$INPUT_<id>`` with "<id>" obviously being the
id you specified. The id must contain only numbers, letters and underscores.

Example:

::

    - input_menu:
        description: "Choose the game's language:"
        id: LANG
        options:
        - en: English
        - fr: French
        - "value and": "label can be anything, surround them with quotes to avoid issues"
        preselect: fr

In this example, English would be preselected. If the option eventually
selected is French, the "$INPUT_LANG" alias would be available in
following directives and would correspond to "fr". "$INPUT" would work as well,
up until the next input directive.


Trying the installer locally
============================

If needed (i.e. you didn't download the installer first from the website), add
the ``name`` (if name contains : character surrond name with quotes), ``game_slug``, ``slug``, ``version`` and ``runner`` directives.
The value for ``runner`` must be the slug name for the runner.
(E.g. winesteam for Steam Windows.)
Under ``script``, add ``files``, ``installer``, ``game`` and other installer
directives. See below for an example.
Save your script in a .yaml file and use the following command in a terminal:
``lutris -i /path/to/file.yaml``

Example Linux game:

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: linux

    script:
      game:
        exe: $GAMEDIR/mygame
        args: --some-arg
        working_dir: $GAMEDIR

      files:
      - myfile: https://example.com/mygame.zip

      installer:
      - chmodx: $GAMEDIR/mygame
      system:
        terminal: true
        env:
          SOMEENV: true

Example wine game:

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: wine

    script:
      game:
        exe: $GAMEDIR/mygame
        args: --some-args
        prefix: $GAMEDIR/prefix
        arch: win64
        working_dir: $GAMEDIR/prefix
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - task:
          executable: installer
          name: wineexec
          prefix: $GAMEDIR/prefix
          arch: win64
      wine:
        Desktop: true
        WineDesktop: 1024x768
        overrides:
          ddraw.dll: n
      system:
        terminal: true
        env:
          WINEDLLOVERRIDES: d3d11=
          SOMEENV: true

Example gog wine game, some installer crash with with /SILENT or /VERYSILENT
option (Cuphead and Star Wars: Battlefront II for example), (most options can
be found here http://www.jrsoftware.org/ishelp/index.php?topic=setupcmdline,
there is undocumented gog option ``/NOGUI``, you need to use it when you use
``/SILENT`` and ``/SUPPRESSMSGBOXES`` parameters):

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: wine

    script:
      game:
        exe: $GAMEDIR/prefix/game/Game.exe
        args: --some-arg
        prefix: $GAMEDIR/prefix
        arch: win64
        working_dir: $GAMEDIR/prefix
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - task:
          args: /SILENT /LANG=en /SP- /NOCANCEL /SUPPRESSMSGBOXES /NOGUI /DIR="C:/game"
          executable: installer
          name: wineexec
          prefix: $GAMEDIR/prefix
          arch: win64
      wine:
        Desktop: true
        WineDesktop: 1024x768
        overrides:
          ddraw.dll: n
      system:
        terminal: true
        env:
          WINEDLLOVERRIDES: d3d11=
          SOMEENV: true


Example gog wine game, alternative (requires innoextract):

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: wine

    script:
      game:
        exe: $GAMEDIR/prefix/drive_c/Games/YourGame/game.exe
        args: --some-arg
        prefix: $GAMEDIR/prefix
        arch: win64
        working_dir: $GAMEDIR/prefix
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - execute:
          args: --gog -d "$CACHE" setup
          description: Extracting game data
          file: innoextract
      - move:
          description: Extracting game data
          dst: $GAMEDIR/drive_c/Games/YourGame
          src: $CACHE/app
      wine:
        Desktop: true
        WineDesktop: 1024x768
        overrides:
          ddraw.dll: n
      system:
        terminal: true
        env:
          WINEDLLOVERRIDES: d3d11=
          SOMEENV: true


Example gog linux game (mojosetup options found here https://www.reddit.com/r/linux_gaming/comments/42l258/fully_automated_gog_games_install_howto/):

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: linux

    script:
      game:
        exe: $GAMEDIR/game.sh
        args: --some-arg
        working_dir: $GAMEDIR
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - chmodx: installer
      - execute:
          file: installer
          description: Installing game, it will take a while...
          args: -- --i-agree-to-all-licenses --noreadme --nooptions --noprompt --destination=$GAMEDIR
      system:
        terminal: true

Example gog linux game, alternative (requires unzip):

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: linux

    script:
      game:
        exe: Game/start.sh
        args: --some-arg
        working_dir: $GAMEDIR
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - execute:
          args: installer -d "$GAMEDIR" "data/noarch/*"
          description: Extracting game data, it will take a while...
          file: unzip
      - rename:
          dst: $GAMEDIR/Game
          src: $GAMEDIR/data/noarch
      system:
        terminal: true


Example winesteam game:

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: winesteam

    script:
      game:
        appid: 227300
        args: --some-args
        prefix: $GAMEDIR/prefix
        arch: win64
      installer:
      - task:
          description: Setting up wine prefix
          name: create_prefix
          prefix: $GAMEDIR/prefix
          arch: win64
      winesteam:
        Desktop: true
        WineDesktop: 1024x768
        overrides:
          ddraw.dll: n
      system:
        terminal: true
        env:
          WINEDLLOVERRIDES: d3d11=
          SOMEENV: true

Example steam linux game:

::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: steam

    script:
      game:
        appid: 227300
        args: --some-args
      steam:
        quit_steam_on_exit: true
      system:
        terminal: true
        env:
          SOMEENV: true

When submitting the installer script to lutris.net, only copy the script part. Remove the two space indentation:

::

    game:
      exe: $GAMEDIR/mygame
      args: --some-arg

    files:
    - myfile: https://example.com

    installer:
    - chmodx: $GAMEDIR/mygame



Calling the online installer
============================

The installer can be called with the ``lutris:<game-slug>`` url scheme.

Library override info
======================

Overrides option accepts this values:

``n,b`` = Try native and fallback to builtin if native doesn't work

``b,n`` = Try builtin and fallback to native if builtin doesn't work

``b``   = Use buildin

``n``   = Use native

``disabled`` = Disable library

Overrides format for ``create_prefix``, ``wineexec`` commands and for ``wine`` options section:

::

      overrides:
        ddraw.dll: n
        d3d9: disable
        winegstreamer: builtin


Override or set env
===================

Example:

::

     env:
      WINEDLLOVERRIDES: d3d11=
      SOMEENV: true


Sysoptions
==========

**wine section:**

``version`` (example: ``staging-2.21-x86_64``)

``Desktop`` (example: ``true``)

``WineDesktop`` (example: ``1024x768``)

``MouseWarpOverride`` (example: ``enable``, ``disable`` or ``force``)

``Audio`` (example: ``auto``, ``alsa``, ``oss`` or ``jack``)

``ShowCrashDialog`` (example: ``true``)

``overrides`` (example: described above)

**winesteam (wine section options available to winesteam runner) section:**

``steam_path`` (example: ``Z:\home\user\Steam\Steam.exe``)

``quit_steam_on_exit`` (example: ``true``)

``steamless_binary`` (example: fallout-nosteam)

``run_without_steam`` (example: ``true``)

**steam section:**

``steamless_binary`` (example: fallout-nosteam)

``run_without_steam`` (example: ``true``)

``steam_native_runtime`` (example: ``false``)

``args`` (example: ``-tcp -language "english"``)

**system section:**

``reset_desktop`` (example: ``true``)

``restore_gamma`` (example: ``true``)

``resolution`` (example: ``2560x1080``)

``terminal`` (example: ``true``)

``env`` (described above)

``prefix_command`` (example: ``firejail --profile=/etc/firejail/steam.profile --``)

``include_processes`` (example: ``Setup.exe``)

``exclude_processes`` (example: ``unpack.exe``)

``single_cpu`` (example: ``true``)

``disable_runtime`` (example: ``true``)

``disable_compositor`` (example: ``true``)

``reset_pulse`` (example: ``true``)

``pulse_latency`` (example: ``true``)

``use_us_layout`` (example: ``true``)

``killswitch`` (example: ``/dev/input/js0``)

``xboxdrv`` (example: ``--silent --type xbox360``)

``sdl_gamecontrollerconfig`` (example: ``$HOME/gamecontrollerdb.txt``)

``xephyr`` (example: offm ``8bpp`` or ``16bpp``)

``xephyr_resolution`` (example: ``1024x768``)
