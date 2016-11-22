#!/bin/bash

result_file="/tmp/lutris-desktop-info.txt"

echo -e "Desktop Info for Lutris\n\n" > $result_file

echo "Environment variables:" >> $result_file
echo "DESKTOP_SESSION=$DESKTOP_SESSION" >> $result_file
echo "GDMSESSION=$GDMSESSION" >> $result_file
echo "SHELL=$SHELL" >> $result_file

echo -e "\n\nDistribution:" >> $result_file
lsb_release -a 2>/dev/null >> $result_file
uname -a >> $result_file

echo -e "\n\nRunning desktop processes:" >> $result_file
pgrep -l "gnome|kde|mate|cinnamon|lxde|xfce|jwm" >> $result_file

echo -e "\n\nOpenGL info:" >> $result_file
glxinfo | grep OpenGL >> $result_file

echo -e "\n\nRAM info:" >> $result_file
free -h >> $result_file

echo -e "\n\nCPU info:" >> $result_file
cat /proc/cpuinfo | grep "model name" | uniq >> $result_file

echo -e "\n\nWine info:" >> $result_file
wine_path="$(which wine)"
if [ "$wine_path" ]; then
    echo "Wine installed system wide: $wine_path" >> $result_file
    echo "Version: $($wine_path --version)" >> $result_file
else
    echo "Wine not installed" >> $result_file
fi

echo "Results saved in $result_file please send this file to the Lutris developers"
