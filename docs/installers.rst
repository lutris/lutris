==================
Writing installers
==================


Table of contents
=================

* `Basics`_
* `Variable substitution`_
* `Game configuration directives`_
* `Runner configuration directives`_
* `System configuration directives`_
* `Fetching required files`_
* `Installer meta data`_
* `Writing the installation script`_
* `Example scripts`_



Basics
======

Games in Lutris are written in the YAML format in a declarative way.
The same document provides information on how to acquire game files, setup the
game and store a base configuration.

Make sure you have some level of understanding of the YAML format before
getting into Lutris scripting. The Ansible documentation provides a short
guide on the syntax: https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html

At the very least, a Lutris installer should have a ``game`` section. If the
installer needs to download or ask the user for some files, those can be added
in the `files` section.

Installer instructions are stored in the ``installer`` section. This is where
the installer files are processed and will results in a runnable game when the
installer has finished.

The configuration for a game is constructed from its installer. The `files` and
`installer` sections are removed from the script, some variables such as
$GAMEDIR are substituted and the results is saved in:
~/.config/lutris/games/<game>-<timestamp>.yml.

Published installers can be accessed from a command line by using the ``lutris:``
URL prefix followed by the installer slug.
For example, calling ``lutris lutris:quake-darkplaces`` will launch the
Darkplaces installer for Quake.

**Important note:** Installer scripts downloaded to the client are embedded in
another document. What is editable on the Lutris section is the ``script``
section of a bigger document. In addition to the script it self, Lutris needs
to know the following information:

* ``name``: Name of the game, should be surrounded in quotes if containing special characters.
* ``game_slug``: Game identifier on the Lutris website
* ``version``: Name of the installer
* ``slug``: Installer identifier
* ``runner``: Runner used for the game.

If you intend to write installers locally and not use the website, you should
have those keys provided at the root level and everything else indented under a
``script`` section.
Local installers can be launched from the CLI with ``lutris -i /path/to/file.yaml``.

Variable substitution
=====================

You can use variables in your script to customize some aspect of it. Those
variables get substituted for their actual value during the install process.

Available variables are:

* ``$GAMEDIR``: Absolute path where the game is installed.
* ``$CACHE``: Temporary cache used to manipulate game files and deleted at the
  end of the installation.
* ``$RESOLUTION``: Full resolution of the user's main display (eg. ``1920x1080``)
* ``$RESOLUTION_WIDTH``: Resolution width of the user's main display (eg. ``1920``)
* ``$RESOLUTION_HEIGHT``: Resolution height of the user's main display (eg. ``1080``)

You can also reference files from the ``files`` section by their identifier,
they will resolve to the absolute path of the downloaded or user provided file.
Referencing game files usually doesn't require preceding the variable name with
a dollar sign.



Installer meta data
===================

Installer meta-data is any directive that is at the root level of the
installer used for customizing the installer.

Referencing the main file
-------------------------

Referencing the main file of a game is possible to do at the root level of the
installer but this information is later merged in the ``game`` section. It is
recommended to put this information directly in the ``game`` section. If you
see an existing installer with keys like ``exe`` or ``main_file`` sitting at
the root level, please move them to the ``game`` section.

Customizing the game's name
---------------------------

Use the ``custom-name`` directive to override the name of the game. Use this
only if the installer provides a significantly different game from the base
one.

Example: ``custom-name: Quake Champions: Doom Edition``

Requiring additional binaries
-----------------------------

If the game or the installer needs some system binaries to run, you can specify
them in the ``require-binaries`` directive. The value is a comma-separated list
of required binaries (acting as AND), if one of several binaries are able to
run the program, you can add them as a ``|`` separated list (acting as OR).

Example::

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

Extensions / patches
--------------------

You can write installers that will not create a new game entry in Lutris.
Instead they will modify the configuration on an exsiting game.
You can use this feature with the ``extends`` directive. It works the same
way as the ``requires`` directive and will check for a base game to be available.

Example::

    # Used in a installer that fixes issues with Mesa
    extends: unreal-gold

Customizing the end of install text
-----------------------------------

You can display a custom message when the installation is completed. To do so,
use the ``install_complete_text`` key.




Game configuration directives
=============================

A game configuration file can contain up to 3 sections: `game`, `system` and a
section named after the runner used for the game.

The `game` section can also contain references to other stores such as Steam or
GOG. Some IDs are used to launch the game (Steam, ScummVM) while in other
cases, the ID is only used to find games files on a 3rd party platform and
download the installer (Humble Bundle, GOG).

Lutris supports the following game identifiers:

`appid`: For Steam games. Numerical ID found in the URL of the store page.
Example: The `appid` for https://store.steampowered.com/app/238960/Path_of_Exile/ is `238960`.
This ID is used for installing and running the game.

`game_id`: Identifier used for ScummVM / ResidualVM games. Can be looked up
on the game compatibility list: https://www.scummvm.org/compatibility/
and https://www.residualvm.org/compatibility/

`gogid`: GOG identifier. Can be looked up on https://www.gogdb.org/products Be
sure to reference the base game and not one of its package or DLC.
Example: The `gogid` for Darksiders III is 1246703238

`humbleid`: Humble Bundle ID. There currently isn't a way to lookup game IDs
other than using the order details from the HB API. Lutris will soon provide
easier ways to find this ID.

`main_file`: For MAME games, the `main_file` can refer to a MAME ID instead of
a file path.

Common game section entries
---------------------------

``exe``: Main game executable. Used for Linux and Wine games.
Example: ``exe: exult``

``main_file``: Used in most emulator runners to reference the ROM or disk file.
Example: ``main_file: game.rom``.
Can also be used to pass the URL for web based games: ``main_file: http://www...``

``args``: Pass additional arguments to the command.
Can be used with linux, wine, winesteam, dosbox, scummvm, pico8 and zdoom runners.
Example: ``args: -c $GAMEDIR/exult.cfg``

``working_dir``: Set the working directory for the game executable.
This is useful if the game needs to run from a different directory than the one
the executable resides in.
This directive can be used for Linux, Wine and Dosbox installers.
Example: ``$GAMEDIR/path/to/game``

Wine and other wine based runners like WineSteam
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``arch``: Sets the architecture of a Wine prefix. By default it is set to ``win64``,
the value can be set to ``win32`` to setup the game in a 32-bit prefix.

``prefix``: Path to the Wine prefix. For Wine games, it should be set to
``$GAMEDIR``. For WineSteam games, set it to ``$GAMEDIR/prefix`` to isolate the
prefix files from the game files. This is only needed if the Steam game
needs customization. If not provided, Lutris will use WineSteam's default prefix
where Steam for Windows is installed.


DRM free Steam and WineSteam
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Lutris has the ability to run Steam games without launching the Steam client.
This is only possible with certain games lacking the Steam DRM.

``run_without_steam``: Activate the DRM free mode and no not launch Steam when
the game runs.

``steamless_binary``: Used in conjonction with ``run_without_steam``. This
allows to provide the path of the game executable if it's able to run without
the Steam client. The game must not have the Steam DRM to use this feature.

Example: ``steamless_binary: $GAMEDIR/System/GMDX.exe``


ScummVM
^^^^^^^

``path``: Location of the game files. This should be set to ``$GAMEDIR`` in
installer scripts.



Runner configuration directives
===============================

Runners can be customized in a section named after the runner identifier
(``slug`` field in the API).  A complete list of all runners is available at
https://lutris.net/api/runners.  Use the runner's slug as the runner
identifier. Please keep the amount of runner customization to a minimum, only
adding what is needed to make the game run correctly. A lot of runner options
do not have their place in Lutris installers and are reserved for the user's
preferences.

The following sections will describe runner directives commonly used in
installers.

wine
----

``version``: Set the Wine version to a specific build. Only set this if the game
has known regressions with the current default build. Abusing this feature
slows down the development of the Wine project.
Example: ``version: staging-2.21-x86_64``

``Desktop``: Run the game in a Wine virtual desktop. This should be used if the
game has issues with Linux window managers such as crashes on Alt-Tab.
Example: ``Desktop: true``

``WineDesktop``: Set the resolution of the Wine virtual desktop. If not provided,
the virtual desktop will take up the whole screen, which is likely the desired
behavior. It is unlikely that you would add this directive in an installer but
can be useful is a game is picky about the resolution it's running in.
Example: ``WineDesktop: 1024x768``

``dxvk``: Use this to disable DXVK if needed. (``dxvk: false``)

``esync``: Use this to enable esync. (``esync: true``)

``overrides``: Overrides for Wine DLLs. List your DLL overrides in a
mapping with the following values:

``n,b`` = Try native and fallback to builtin if native doesn't work

``b,n`` = Try builtin and fallback to native if builtin doesn't work

``b``   = Use builtin

``n``   = Use native

``disabled`` = Disable library

Example::

      overrides:
        ddraw.dll: n
        d3d9: disabled
        winegstreamer: builtin

System configuration directives
===============================

Those directives are stored in the ``system`` section and allow for
customization of system features. As with runner configuration options, system
directives should be used carefully, only adding them when absolutely necessary
to run a game.

``restore_gamma``: If the game doesn't restore the correct gamma on exit, you
can use this option to call xgamma and reset the default values. This option
won't work on Wayland.
Example: ``restore_gamma: true``

``terminal``: Run the game in a terminal if the game is a text based one. Do
not use this option to get the console output of the game, this will result in
a broken installer. **Only use this option for text based games.**

``env``: Sets environment variables before launching a game and during install.
Do not **ever** use this directive to enable a framerate counter. Do not use
this directive to override Wine DLLs. Variable substitution is available in
values.
Example::

     env:
       __GL_SHADER_DISK_CACHE: 1
       __GL_THREADED_OPTIMIZATIONS: '1'
       __GL_SHADER_DISK_CACHE_PATH: $GAMEDIR
       mesa_glthread: 'true'

``single_cpu``: Run the game on a single CPU core. Useful for some old games
that handle multicore CPUs poorly. (``single_cpu: true``)

``disable_runtime``: **DO NOT DISABLE THE LUTRIS RUNTIME IN LUTRIS INSTALLERS**

``pulse_latency``: Set PulseAudio latency to 60 msecs. Can reduce audio
stuttering. (``pulse_latency: true``)

``use_us_layout``: Change the keyboard layout to a standard US one while the
game is running.  Useful for games that handle other layouts poorly and don't
have key remapping options. (``use_us_layou: true``)

``xephyr``: Run the game in Xephyr. This is useful for games only handling 256
color modes. To enable Xephyr, pass the desired bit per plane value. (``xephyr: 8bpp``)

``xephyr_resolution``: Used with the ``xephyr`` option, this sets the size of
the Xephyr window. (``xephyr_resolution: 1024x768``)


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

Examples::

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


Writing the installation script
===============================

After every file needed by the game has been acquired, the actual installation
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

Example::

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

Example::

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

Example::

    - merge:
        src: game_file_id
        dst: $GAMEDIR/location

Extracting archives
-------------------

Extracting archives is done with the ``extract`` directive, the ``file``
argument is a ``file id`` or a file path with optional wildcards. If the archive(s)
should be extracted in some other location than the ``$GAMEDIR``, you can specify a
``dst`` argument.

You can optionally specify the archive's type with the ``format`` option.
This is useful if the archive's file extension does not match what it should
be. Accepted values for ``format`` are: zip, tgz, gzip, bz2, and gog (innoextract).

Example::

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

Example::

    - execute:
        args: --argh
        file: great_id
        terminal: true
        env:
          key: value

You can use the ``command`` parameter instead of ``file`` and ``args``. This
lets you run bash/shell commands easier. ``bash`` is used and is added to ``include_processes`` internally.

Example::

    - execute:
        command: 'echo Hello World! | cat'

Writing files
-------------


Writing text files
^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

    * ``overrides``: optional DLL overrides, format described later

    * ``install_gecko``: optional variable to stop installing gecko

    * ``install_mono``: optional variable to stop installing mono

    Example:

    ::

        - task:
            name: create_prefix
            arch: win64

*   wine / winesteam: ``wineexec`` Runs a windows executable. Parameters are
    ``executable`` (``file ID`` or path), ``args`` (optional arguments passed
    to the executable), ``prefix`` (optional WINEPREFIX),
    ``arch`` (optional WINEARCH, required when you created win64 prefix), ``blocking`` (if true, do not run the process in a thread), ``working_dir`` (optional working directory), ``include_processes``  (optional space-separated list of processes to include to
    being watched)
    ``exclude_processes`` (optional space-separated list of processes to exclude from
    being watched), ``env`` (optional environment variables), ``overrides`` (optional DLL overrides).

    Example::

        - task:
            name: wineexec
            executable: drive_c/Program Files/Game/Game.exe
            args: --windowed

*   wine / winesteam: ``winetricks`` Runs winetricks with the ``app`` argument.
    ``prefix`` is an optional WINEPREFIX path. You can run many tricks at once by adding more to the ``app`` parameter (space-separated).

    By default Winetricks will run in silent mode but that can cause issues
    with some components such as XNA. In such cases, you can provide the
    option ``silent: false``

    Example::

        - task:
            name: winetricks
            app: nt40

    For a full list of available ``winetricks`` see here: https://github.com/Winetricks/winetricks/tree/master/files/verbs

*   wine / winesteam: ``eject_disk`` runs eject_disk in your ``prefix`` argument. Parameters are
    ``prefix`` (optional wineprefix path).

    Example:

    ::

        - task:
            name: eject_disc

*   wine / winesteam: ``set_regedit`` Modifies the Windows registry. Parameters
    are ``path`` (the registry path, use backslashes), ``key``, ``value``,
    ``type`` (optional value type, default is REG_SZ (string)), ``prefix``
    (optional WINEPREFIX), ``arch``
    (optional architecture of the prefix, required when you created win64 prefix).

    Example:

    ::

        - task:
            name: set_regedit
            path: HKEY_CURRENT_USER\Software\Valve\Steam
            key: SuppressAutoRun
            value: '00000000'
            type: REG_DWORD

*   wine / winesteam: ``delete_registry_key`` Deletes registry key in the Windows registry. Parameters
    are ``key``, ``prefix``
    (optional WINEPREFIX), ``arch`` (optional architecture of the prefix, required when you created win64 prefix).

    Example:

    ::

        - task:
            name: set_regedit
            path: HKEY_CURRENT_USER\Software\Valve\Steam
            key: SuppressAutoRun
            value: '00000000'
            type: REG_DWORD

* wine / winesteam: ``set_regedit_file`` Apply a regedit file to the
  registry, Parameters are ``filename`` (regfile name),
  ``arch`` (optional architecture of the prefix, required when you created win64 prefix).


  Example::

    - task:
        name: set_regedit_file
        filename: myregfile

* wine / winesteam: ``winekill`` Stops processes running in Wine prefix. Parameters
  are ``prefix`` (optional WINEPREFIX),
  ``arch`` (optional architecture of the prefix, required when you created win64 prefix).

  Example

  ::

    - task:
        name: winekill

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
        preselect: en

In this example, English would be preselected. If the option eventually
selected is French, the "$INPUT_LANG" alias would be available in
following directives and would correspond to "fr". "$INPUT" would work as well,
up until the next input directive.

Example scripts
===============

Those example scripts are intended to be used as standalone files. Only the
``script`` section should be added to the script submission form.

Example Linux game::

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

Example wine game::

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
        arch: win32
        working_dir: $GAMEDIR/prefix
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - task:
          executable: installer
          name: wineexec
          prefix: $GAMEDIR/prefix
      wine:
        Desktop: true
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
        exe: $GAMEDIR/drive_c/game/bin/Game.exe
        args: --some-arg
        prefix: $GAMEDIR
        working_dir: $GAMEDIR/drive_c/game
      files:
      - installer: "N/A:Select the game's setup file"
      installer:
      - task:
          args: /SILENT /LANG=en /SP- /NOCANCEL /SUPPRESSMSGBOXES /NOGUI /DIR="C:/game"
          executable: installer
          name: wineexec
      wine:
        Desktop: true
        overrides:
          ddraw.dll: n
      system:
        terminal: true
        env:
          SOMEENV: true


Example gog wine game, alternative (requires innoextract)::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: wine

    script:
      game:
        exe: $GAMEDIR/drive_c/Games/YourGame/game.exe
        args: --some-arg
        prefix: $GAMEDIR/prefix
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
        overrides:
          ddraw.dll: n
      system:
        env:
          SOMEENV: true


Example gog linux game (mojosetup options found here https://www.reddit.com/r/linux_gaming/comments/42l258/fully_automated_gog_games_install_howto/)::

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

Example gog linux game, alternative::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: linux

    script:
      files:
      - goginstaller: N/A:Please select the GOG.com Linux installer
      game:
        args: --some-arg
        exe: start.sh
      installer:
      - extract:
          dst: $CACHE/GOG
          file: goginstaller
          format: zip
      - merge:
          dst: $GAMEDIR
          src: $CACHE/GOG/data/noarch/
      system:
        terminal: true


Example winesteam game::

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

Example steam Linux game::

    name: My Game
    game_slug: my-game
    version: Installer
    slug: my-game-installer
    runner: steam

    script:
      game:
        appid: 227300
        args: --some-args
