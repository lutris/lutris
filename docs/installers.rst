==================
Writing installers
==================

Fetching required files
=======================

The ``files`` section of the installer references every file needed for
installing the game. The section's keys are an unique identifier used later by
the installer. The value can be either a string containing an URI pointing at
the required file or a dictionnary containing the ``filename`` and ``uri`` keys.
The ``uri`` key is equivalent to passing only a string to the installer and the
``filename`` key will be used to give the local copy another name.

If the game contains copyrighted files that cannot be redistributed, the value
should begin with ``N/A``. When the installer encounter this value, it will
prompt the user for the location of the file. To indicate to the user what file
to select, append a message to ``N/A`` like this: 
``N/A:Please select the installer for this game``


If the game makes use of (Windows) Steam data, the value should be
``$WINESTEAM:appid:path/to/data``. This will check that the data is available
or install it otherwise.

Installer meta data
===================

Installing mods and add-ons
---------------------------

Mods and add-ons require that a base game is already available on the system.
You can let now the installer that you want to install an add-on by specifying
the ``requires`` directive. The value of ``requires`` must be the canonical
slug name of a game, not one of its aliases. For example, to install the add-on
"The reckoning" for Quake 2, you should add:

``requires: quake-2``

Writing the installation script
===============================

After every file needed by the game have been aquired, the actual installation
can take place. A series of directives will tell the installer how to set up
the game correctly.

Displaying an 'Insert disc' dialog
----------------------------------

The ``insert-disc`` command will display a message box to the user requesting
him to insert the game's disc into the optical drive. A link to CDEmu homepage's
and PPA will also be displayed if the program isn't detected on the machine,
otherwise it will be replaced with a button to open gCDEmu.

An optional parameter ``message`` will override the default text if given.


Moving files and directories
----------------------------

Move files by using the ``move`` command. ``move``  requires two parameters:
``src`` and ``dst``.

The ``src`` parameter can either be a ``file id`` or a relative location. If the
parameter value is not found in the list of ``file ids``, then it must be
prefixed by either ``$CACHE`` or ``$GAMEDIR`` to move a file or directory from
the download cache or the game installation dir, respectively.

The ``dst`` parameter should be prefixed by either ``$GAMEDIR`` or ``$HOME``
to move files to path relative to the game dir or the current user's home
directory.

The ``move`` command cannot overwrite files.

Example:

::

    move:
      src: game-file-id
      dst: $GAMEDIR/location

Copying and merging directories
-------------------------------

Both merging and copying actions are done with the ``merge`` directive.
Whether the actions acts as merge or copy depends of the existence of the
destination directory. When merging into an existing directory, original files
with the same as ones present in the merged directory will be overwritten, take
this into account when writing your script and order your actions accordingly.

Example:

::

    merge:
      src: game-file-id
      dst: $GAMEDIR/location


Extracting archives
-------------------

Extracting archives is done with the ``extract`` directive, the ``file``
argument is a ``file id``. If the archive should be extracted in some other
location than the ``$GAMEDIR``, you can specify a ``dst`` argument.

Example:

::

    extract:
      file: game-archive
      dst: $GAMEDIR/datadir/

Making a file executable
------------------------

Marking the file as executable is done with the ``chmodx`` command. It is often
needed for games that ships in a zip file which does not retain file permissions.

Example: ``chmodx: $GAMEDIR/game_binary``

Running a task provided by a runner
-----------------------------------

Some actions are specific to some runners, you can call them with th ``task`` 
command. You must at least provide the ``name`` parameter which is the function
that will be called. Other parameters depend on the task being called.

Currently, the following tasks are implemented:

wine: ``wineexec`` Runs a windows executable. Parameters are ``executable``,
``args`` (optional arguments passed to the executable), ``prefix`` (optional
WINEPREFIX).

wine: ``winetricks`` Runs winetricks with the ``app`` argument. ``prefix`` is
an optional WINEPREFIX path.


Calling the installer
=====================

The installer can be called with the ``lutris:<game-slug>`` url scheme or by
specifying the path to an installer script.
