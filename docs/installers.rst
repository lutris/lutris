==================
Writing installers
==================


Displaying an 'Insert disc' dialog
----------------------------------

The ``insert-disc`` command will display a message box to the user requesting 
him to insert the game's disc into the optical drive. A link to CDEmu homepage's
and PPA will also be displayed if the program isn't detected on the machine, 
otherwise it will be replaced with a button to open gCDEmu.

An optional parameter ``message`` will override the default text if given.


Moving files
------------

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
