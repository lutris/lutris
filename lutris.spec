%{!?__python3: %global __python3 /usr/bin/python3}
%{!?python3_sitelib: %global python3_sitelib %(%{__python3} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?py3_build: %global py3_build CFLAGS="%{optflags}" %{__python3} setup.py build}
%{!?py3_install: %global py3_install %{__python3} setup.py install --skip-build --root %{buildroot}}

%global appid net.lutris.Lutris

Name:           lutris
Version:        0.5.5
Release:        7%{?dist}
Summary:        Install and play any video game easily

License:        GPL-3.0+
Group:          Amusements/Games/Other
URL:            http://lutris.net
Source0:        http://lutris.net/releases/lutris_%{version}.tar.xz

BuildArch:      noarch

# Common build dependencies
BuildRequires:  desktop-file-utils
BuildRequires:  python3-devel

%if 0%{?fedora}
BuildRequires:  python3-gobject, python3-wheel, python3-setuptools
Requires:       python3-gobject, python3-PyYAML, cabextract
Requires:       gtk3, psmisc, xorg-x11-server-Xephyr, xorg-x11-server-utils
Requires:       python3-requests
Requires:       gnome-desktop3
Recommends:     wine-core
%endif

%if 0%{?rhel} || 0%{?centos}
BuildRequires:  python3-gobject
Requires:       python3-gobject, python3-PyYAML, cabextract
%endif

%if 0%{?suse_version}
BuildRequires:  python3-gobject, python3-setuptools, typelib-1_0-Gtk-3_0
BuildRequires:  update-desktop-files
# Needed to workaround "directories not owned by a package" issue
BuildRequires:  hicolor-icon-theme
BuildRequires:  python3-setuptools
Requires:       (python3-gobject-Gdk or python3-gobject)
Requires:       python3-PyYAML, cabextract, typelib-1_0-Gtk-3_0
Requires:       typelib-1_0-GnomeDesktop-3_0, typelib-1_0-WebKit2-4_0, typelib-1_0-Notify-0_7
Requires:       fluid-soundfont-gm, python3-Pillow, python3-requests
%endif

%if 0%{?fedora} || 0%{?suse_version}
BuildRequires:  fdupes

%ifarch x86_64
Requires:       mesa-vulkan-drivers(x86-32)
Requires:       vulkan-loader(x86-32)
%endif

Requires:       mesa-vulkan-drivers
Requires:       vulkan-loader
Recommends:     wine-core
BuildRequires:  fdupes
%endif

%if 0%{?fedora}
%ifarch x86_64
Requires:       mesa-libGL(x86-32)
Requires:       mesa-libGL
%endif
%endif


%description
Lutris is a gaming platform for GNU/Linux. Its goal is to make
gaming on Linux as easy as possible by taking care of installing
and setting up the game for the user. The only thing you have to
do is play the game. It aims to support every game that is playable
on Linux.

%prep
%setup -q -n %{name}


%build
%py3_build


%install
%py3_install
%if 0%{?fedora} || 0%{?suse_version}
%fdupes %{buildroot}%{python3_sitelib}
%endif

#desktop icon
%if 0%{?suse_version}
%suse_update_desktop_file -r -i %{appid} Network FileTransfer
%endif

%if 0%{?fedora} || 0%{?rhel} || 0%{?centos}
desktop-file-install --dir=%{buildroot}%{_datadir}/applications share/applications/%{appid}.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/%{appid}.desktop
%endif

%if 0%{?suse_version} >= 1140
%post
%icon_theme_cache_post
%desktop_database_post
%endif


%if 0%{?suse_version} >= 1140
%postun
%icon_theme_cache_postun
%desktop_database_postun
%endif

%files
%{_bindir}/%{name}
%{_bindir}/lutris-wrapper
%{_datadir}/%{name}/
%{_datadir}/metainfo/%{appid}.metainfo.xml
%{_datadir}/applications/%{appid}.desktop
%{_datadir}/icons/hicolor/16x16/apps/lutris.png
%{_datadir}/icons/hicolor/22x22/apps/lutris.png
%{_datadir}/icons/hicolor/24x24/apps/lutris.png
%{_datadir}/icons/hicolor/32x32/apps/lutris.png
%{_datadir}/icons/hicolor/48x48/apps/lutris.png
%{_datadir}/icons/hicolor/scalable/apps/lutris.svg
%{python3_sitelib}/%{name}-*.egg-info
%{python3_sitelib}/%{name}/

%changelog
* Wed Feb 06 2019 Andrew Schott <andrew@schotty.com 0.5.0.1-6
- Readability cleanup.

* Wed Feb 06 2019 Andrew Schott <andrew@schotty.com 0.5.0.1-6
- Original problem with gnome-desktop3 was a typo from previously.  Correct spelling fixes the problem.

* Wed Feb 06 2019 Andrew Schott <andrew@schotty.com 0.5.0.1-5
- Made changes specific to removing packages that are only for fedora and not suse to a fedora specific section (mesa-libGL)

* Wed Feb 06 2019 Andrew Schott <andrew@schotty.com. 0.5.0.1-4
- Fixed typo in package name for fedora - gnome-desktop3
- Changed Source0 file extension from tar.gz to tar.xz

* Mon Feb 04 2019 Andrew Schott <andrew@schotty.com> - 0.5.0.1-3
- Moved fedora dependency of "gnome-desktop3" to recommends to resolve a snafu with the way it was packaged.
- Fixed the .desktop file registration (was using %{name}, needed %{appid})

* Tue Nov 29 2016 Mathieu Comandon <strycore@gmail.com> - 0.4.3
- Ensure correct Python3 dependencies
- Set up Python macros for building (Thanks to Pharaoh_Atem on #opensuse-buildservice)

* Sat Oct 15 2016 Mathieu Comandon <strycore@gmail.com> - 0.4.0
- Update to Python 3
- Bump version to 0.4.0

* Sat Dec 12 2015 Rémi Verschelde <akien@mageia.org> - 0.3.7-2
- Remove ownership of system directories
- Spec file cleanup

* Fri Nov 27 2015 Mathieu Comandon <strycore@gmail.com> - 0.3.7-1
- Bump to version 0.3.7

* Thu Oct 30 2014 Mathieu Comandon <strycore@gmail.com> - 0.3.6-1
- Bump to version 0.3.6
- Add OpenSuse compatibility (contribution by @malkavi)

* Fri Sep 12 2014 Mathieu Comandon <strycore@gmail.com> - 0.3.5-1
- Bump version to 0.3.5

* Thu Aug 14 2014 Travis Nickles <nickles.travis@gmail.com> - 0.3.4-3
- Edited Requires to include pygobject3.

* Wed Jun 04 2014 Travis Nickles <nickles.travis@gmail.com> - 0.3.4-2
- Changed build and install step based on template generated by
  rpmdev-newspec.
- Added Requires.
- Ensure package can be built using mock.

* Tue Jun 03 2014 Travis Nickles <nickles.travis@gmail.com> - 0.3.4-1
- Initial version of the package
