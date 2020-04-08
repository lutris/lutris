|pypi| |license| |coverage| |scru| |master_build|

Pure python module for (de)serialization to and from VDF that works just like ``json``.

Tested and works on ``python2.7``, ``python3.3+``, ``pypy`` and ``pypy3``.

VDF is Valve's KeyValue text file format

https://developer.valvesoftware.com/wiki/KeyValues

| Supported versions: ``kv1``
| Unsupported: ``kv2`` and ``kv3``

Install
-------

You can grab the latest release from https://pypi.org/project/vdf/ or via ``pip``

.. code:: bash

    pip install vdf

Install the current dev version from ``github``

.. code:: bash

    pip install git+https://github.com/ValvePython/vdf


Problems & solutions
--------------------

- There are known files that contain duplicate keys. This is supported the format and
  makes mapping to ``dict`` impossible. For this case the module provides ``vdf.VDFDict``
  that can be used as mapper instead of ``dict``. See the example section for details.

- By default de-serialization will return a ``dict``, which doesn't preserve nor guarantee
  key order due to `hash randomization`_. If key order is important then
  I suggest using ``collections.OrderedDict``, or ``vdf.VDFDict``.

Example usage
-------------

For text representation

.. code:: python

    import vdf

    # parsing vdf from file or string
    d = vdf.load(open('file.txt'))
    d = vdf.loads(vdf_text)
    d = vdf.parse(open('file.txt'))
    d = vdf.parse(vdf_text)

    # dumping dict as vdf to string
    vdf_text = vdf.dumps(d)
    indented_vdf = vdf.dumps(d, pretty=True)

    # dumping dict as vdf to file
    vdf.dump(d, open('file2.txt','w'), pretty=True)


For binary representation

.. code:: python

    d = vdf.binary_loads(vdf_bytes)
    b = vdf.binary_dumps(d)

    # alternative format - VBKV

    d = vdf.binary_loads(vdf_bytes, alt_format=True)
    b = vdf.binary_dumps(d, alt_format=True)

    # VBKV with header and CRC checking

    d = vdf.vbkv_loads(vbkv_bytes)
    b = vdf.vbkv_dumps(d)

Using an alternative mapper

.. code:: python

  d = vdf.loads(vdf_string, mapper=collections.OrderedDict)
  d = vdf.loads(vdf_string, mapper=vdf.VDFDict)

``VDFDict`` works much like the regular ``dict``, except it handles duplicates and remembers
insert order. Additionally, keys can only be of type ``str``. The most important difference
is that when trying to assigning a key that already exist it will create a duplicate instead
of reassign the value to the existing key.

.. code:: python

  >>> d = vdf.VDFDict()
  >>> d['key'] = 111
  >>> d['key'] = 222
  >>> d
  VDFDict([('key', 111), ('key', 222)])
  >>> d.items()
  [('key', 111), ('key', 222)]
  >>> d['key']
  111
  >>> d[(0, 'key')]  # get the first duplicate
  111
  >>> d[(1, 'key')]  # get the second duplicate
  222
  >>> d.get_all_for('key')
  [111, 222]

  >>> d[(1, 'key')] = 123  # reassign specific duplicate
  >>> d.get_all_for('key')
  [111, 123]

  >>> d['key'] = 333
  >>> d.get_all_for('key')
  [111, 123, 333]
  >>> del d[(1, 'key')]
  >>> d.get_all_for('key')
  [111, 333]
  >>> d[(1, 'key')]
  333

  >>> print vdf.dumps(d)
  "key" "111"
  "key" "333"

  >>> d.has_duplicates()
  True
  >>> d.remove_all_for('key')
  >>> len(d)
  0
  >>> d.has_duplicates()
  False


.. |pypi| image:: https://img.shields.io/pypi/v/vdf.svg?style=flat&label=latest%20version
    :target: https://pypi.org/project/vdf/
    :alt: Latest version released on PyPi

.. |license| image:: https://img.shields.io/pypi/l/vdf.svg?style=flat&label=license
    :target: https://pypi.org/project/vdf/
    :alt: MIT License

.. |coverage| image:: https://img.shields.io/coveralls/ValvePython/vdf/master.svg?style=flat
    :target: https://coveralls.io/r/ValvePython/vdf?branch=master
    :alt: Test coverage

.. |scru| image:: https://scrutinizer-ci.com/g/ValvePython/vdf/badges/quality-score.png?b=master
    :target: https://scrutinizer-ci.com/g/ValvePython/vdf/?branch=master
    :alt: Scrutinizer score

.. |master_build| image:: https://img.shields.io/travis/ValvePython/vdf/master.svg?style=flat&label=master%20build
    :target: http://travis-ci.org/ValvePython/vdf
    :alt: Build status of master branch

.. _DuplicateOrderedDict: https://github.com/rossengeorgiev/dota2_notebooks/blob/master/DuplicateOrderedDict_for_VDF.ipynb

.. _hash randomization: https://docs.python.org/2/using/cmdline.html#envvar-PYTHONHASHSEED
