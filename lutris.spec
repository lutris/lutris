%global appid net.lutris.Lutris

Name:           lutris
Version:        0.5.20
Release:        7%{?dist}
Summary:        Video game preservation platform

License:        GPL-3.0+
Group:          Amusements/Games/Other
URL:            http://lutris.net
Source0:        http://lutris.net/releases/lutris_%{version}.tar.xz
BuildArch:      noarch

BuildRequires:  desktop-file-utils
BuildRequires:  python3-devel
BuildRequires:  python3-gobject
BuildRequires:  python-wheel
BuildRequires:  python-setuptools
BuildRequires:  fdupes
BuildRequires:  libappstream-glib
BuildRequires:  meson
BuildRequires:  gettext
Requires:       python3-gobject
Requires:       python3-PyYAML
Requires:       python3-requests
Requires:       python3-dbus
Requires:       python3-evdev
Requires:       python3-distro
Requires:       python3-pillow
Requires:       cabextract
Requires:       mesa-vulkan-drivers
Requires:       vulkan-loader
Recommends:     wine-core

%ifarch x86_64
Requires:       mesa-vulkan-drivers(x86-32)
Requires:       vulkan-loader(x86-32)
%endif

%if 0%{?fedora}
Requires:       gtk3, psmisc, xrandr
Requires:       gnome-desktop3
Requires:       mesa-libGL
%ifarch x86_64
Requires:       mesa-libGL(x86-32)
%endif
%endif

%if 0%{?suse_version}
BuildRequires:  typelib-1_0-Gtk-3_0
BuildRequires:  update-desktop-files
BuildRequires:  hicolor-icon-theme
Requires:       typelib-1_0-Gtk-3_0
Requires:       typelib-1_0-GnomeDesktop-3_0
Requires:       typelib-1_0-WebKit2-4_0
Requires:       typelib-1_0-Notify-0_7
%endif


%description
Lutris helps you install and play video games from all eras and
from most gaming systems. By leveraging and combining existing
emulators, engine re-implementations and compatibility layers,
it gives you a central interface to launch all your games.

%prep
%autosetup -n %{name}-%{version} -p1

%build
%py3_build
%meson
%meson_build

%install
%py3_install
%meson_install
%if 0%{?fedora} || 0%{?suse_version}
%fdupes %{buildroot}%{python3_sitelib}
%endif

#desktop icon
%if 0%{?suse_version}
%suse_update_desktop_file -r -i %{appid} Game Network
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
%{_datadir}/%{name}/
%{_datadir}/metainfo/%{appid}.metainfo.xml
%{_datadir}/applications/%{appid}.desktop
%{_datadir}/icons/hicolor/16x16/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/22x22/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/24x24/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/32x32/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/48x48/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/64x64/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/128x128/apps/net.lutris.Lutris.png
%{_datadir}/icons/hicolor/scalable/apps/net.lutris.Lutris.svg
%{_datadir}/man/man1/%{name}.1.gz
%{python3_sitelib}/%{name}-*.egg-info
%{python3_sitelib}/%{name}/
%{_datadir}/metainfo/
%{_datadir}/locale/

%changelog
* Mon Sep 11 2023 Mathieu Comandon <mathieucomandon@gmail.com> 0.5.13
- Update to Meson build system

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
