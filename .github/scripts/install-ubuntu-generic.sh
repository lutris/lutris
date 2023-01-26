#!/bin/bash
# Default dependencies needed on a fresh install of ubuntu in order to
# build the lutris package.

sudo apt update
sudo apt install \
    debhelper \
    debmake \
    devscripts \
    dh-python \
    meson \
    equivs \
    git-buildpackage
