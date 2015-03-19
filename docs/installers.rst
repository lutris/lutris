==================
Writing installers
==================

Fetching required files
=======================

The ``files`` section of the installer references every file needed for
installing the game. This section's keys are unique identifier used later in
the ``installer`` section. The value can either be a string containing a URI
pointing at the required file or a dictionary containing the ``filename`` and
``uri`` keys. The ``uri`` key is equivalent to passing only a string to the
installer and the ``filename`` key will be used to give the local copy another
name. [TODO: example]

If the game contains copyrighted files that cannot be redistributed, the value
should begin with ``N/A``. When the installer encounter this value, it will
prompt the user for the location of the file. To indicate to the user what file
to select, append a message to ``N/A`` like this:
``N/A:Please select the installer for this game``

Examples:

::

    files:
    - file1: http://site.com/gamesetup.exe
    - file2: "N/A:Select the game's setup file"


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

For browser games, specify the game's URL with ``main_file``.
Example: ``main_file: http://www...``

Presetting game parameters
--------------------------

The ``game`` directive lets you preset game parameters and options. Available
parameters depend on the runner:

*   linux: ``args`` (optional command arguments), ``working_dir``
    (optional working directory, defaults to the exe's dir).

*   wine:  ``args``, ``prefix`` (optional Wine prefix), ``working_dir`` (optional
    working directory, defaults to the exe's dir).

*   winesteam: ``args``, ``prefix`` (optional Wine prefix).

[TODO: reference all options] Meanwhile, you can check the configuration window
of any game using the runner you're writing for to get a list of the available
options.

Example:

::

    game:
        exe: drive_c/Game/game.exe
        prefix: $GAMEDIR
        args: -arg

Mods and add-ons
----------------

Mods and add-ons require that a base game is already installed on the system.
You can let the installer know that you want to install an add-on by specifying
the ``requires`` directive. The value of ``requires`` must be the canonical
slug name of the base game, not one of its aliases. For example, to install the
add-on "The reckoning" for Quake 2, you should add:

``requires: quake-2``


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
        src: game-file-id
        dst: $GAMEDIR/location

Copying and merging directories
-------------------------------

Both merging and copying actions are done with the ``merge`` directive.
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
        src: game-file-id
        dst: $GAMEDIR/location

Extracting archives
-------------------

Extracting archives is done with the ``extract`` directive, the ``file``
argument is a ``file id``. If the archive should be extracted in some other
location than the ``$GAMEDIR``, you can specify a ``dst`` argument.

You can optionally specify the archive's type with the ``format`` option.
This is useful if the archive's file extension does not match what it should
be. Accepted values for ``format`` are: zip, tgz, gzip and bz2.

Example:

::

    - extract:
        file: game-archive
        dst: $GAMEDIR/datadir/

Making a file executable
------------------------

Marking the file as executable is done with the ``chmodx`` command. It is often
needed for games that ship in a zip file, which does not retain file
permissions.

Example: ``- chmodx: $GAMEDIR/game_binary``

Executing a file
----------------

Execute files with the ``execute`` directive. Use the ``args`` parameter to add
command arguments, and ``file`` to reference a ``file id`` or a path.

Example:

::

    - execute:
        args: --argh
        file: great-id

Writing into an INI type config file
------------------------------------

Modify or create a config file with the ``write_config`` directive. A config file
is a text file composed of key=value (or key: value) lines grouped under
[sections]. Use the ``file`` (an absolute path or a ``file id``), ``section``,
``key`` and ``value`` parameters. Not that the file is entirely rewritten and
comments are left out; Make sure to compare the initial and resulting file
to spot any potential parsing issues.

Example:

::

    - write_config:
        file: $GAMEDIR/game.ini
        section: Engine
        key: Renderer
        value: OpenGL


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
    create_prefix command. Parameters are ``prefix`` (the path), ``arch``
    (optional architecture of the prefix, default: win32).

    Example:

    ::

        - task:
            name: create_prefix
            prefix: $GAMEDIR
            arch: win64

*   wine / winesteam: ``wineexec`` Runs a windows executable. Parameters are
    ``executable`` (``file ID`` or path), ``args`` (optional arguments passed
    to the executable), ``prefix`` (optional WINEPREFIX),
    ``working_dir`` (optional working directory).

    Example:

    ::

        - task:
            name: wineexec
            prefix: $GAMEDIR
            executable: drive_c/Program Files/Game/Game.exe
            args: --windowed


*   wine / winesteam: ``winetricks`` Runs winetricks with the ``app`` argument.
    ``prefix`` is an optional WINEPREFIX path.

    Example:

    ::

        - task:
            name: winetricks
            prefix: $GAMEDIR
            app: nt40

*   wine / winesteam: ``set_regedit`` Modifies the Windows registry. Parameters
    are ``path`` (the registry path, use backslashes), ``key``, ``value``,
    ``type`` (optional value type, default is REG_SZ (string)), ``prefix``
    (optional WINEPREFIX).

    Example:

    ::

        - task:
            name: set_regedit
            prefix: $GAMEDIR
            path: HKEY_CURRENT_USER\Software\Valve\Steam
            key: SuppressAutoRun
            value: 00000000
            type: REG_DWORD

* wine / winesteam: ``set_regedit_file`` Apply a regedit file to the
  registry

  Example::

    - task:
        name: set_regedit_file
        prefix: $GAMEDIR
        filename: myregfile

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
        description: Choose the game's language:
        id: LANG
        options:
        - en: English
        - bf: Brainfuck
        - "value and": "label can be anything, surround them with quotes to avoid issues"
        preselect: lah

In this example, English would be preselected. If the option eventually
selected is Brainfuck, the "$INPUT_LANG" alias would be available in
following directives and would correspond to "bf". "$INPUT" would work as well,
up until the next input directive.


Trying the installer locally
============================

If needed (i.e. you didn't download the installer first from the website), add
the ``runner`` and ``name`` directives. The value for ``runner`` must be the
slug name for the runner. (E.g. winesteam for Steam Windows.)
Save your script in a file and use the following command in a terminal:
``lutris -i /path/to/file``


Calling the online installer
============================

The installer can be called with the ``lutris:<game-slug>`` url scheme.
