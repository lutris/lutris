#!/usr/bin/env python

from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='vdf2json',
    version='1.1',
    description='command line tool for converting VDF to JSON',
    long_description=long_description,
    url='https://github.com/rossengeorgiev/vdf-python',
    author='Rossen Georgiev',
    author_email='hello@rgp.io',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Topic :: Text Processing ',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='valve keyvalue vdf tf2 dota2 csgo cli commandline json',
    install_requires=['vdf>=1.4'],
    packages=['vdf2json'],
    entry_points={
        'console_scripts': [
            'vdf2json = vdf2json.cli:main'
        ]
    },
    zip_safe=True,
)
