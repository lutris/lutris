==================
Writing installers
==================


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
