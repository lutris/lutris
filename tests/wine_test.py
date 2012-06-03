import bootstrap
import os

from lutris.runners import wine

kwargs = {'prefix':  os.path.join(os.path.expanduser('~'), 'wineprefixtest')}

wine.create_prefix(**kwargs)

