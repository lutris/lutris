"""Startup profile selector dialog.

Shows a card-based profile picker at Lutris launch so each user can
choose their own profile before the main window appears.
"""

from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris import settings
from lutris.profile import get_profile_manager

# Settings key: "1" = show, "0" = skip, absent = auto (show if >1 profile)
SETTING_KEY = "show_profile_selector"

_AVATAR_PALETTE = [
    "#e53935",  # red
    "#8e24aa",  # purple
    "#3949ab",  # indigo
    "#00897b",  # teal
    "#43a047",  # green
    "#f4511e",  # deep-orange
    "#6d4c41",  # brown
    "#546e7a",  # blue-grey
]


def _avatar_color(profile_id: str) -> str:
    return _AVATAR_PALETTE[sum(ord(c) for c in profile_id) % len(_AVATAR_PALETTE)]


class ProfileSelectorDialog(Gtk.Dialog):
    """Card-based profile picker shown at startup."""

    def __init__(self):
        super().__init__(flags=Gtk.DialogFlags.MODAL)
        self.set_default_size(520, 360)
        self.set_resizable(False)
        self.pm = get_profile_manager()

        # Custom header bar — no close button, Lutris logo on the left
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title(_("Who's playing?"))
        logo = Gtk.Image.new_from_icon_name("net.lutris.Lutris", Gtk.IconSize.LARGE_TOOLBAR)
        header.pack_start(logo)
        self.set_titlebar(header)

        content = self.get_content_area()
        content.set_spacing(0)
        content.set_margin_top(20)
        content.set_margin_bottom(0)
        content.set_margin_start(20)
        content.set_margin_end(20)

        # Profile cards grid
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_max_children_per_line(5)
        self.flow.set_min_children_per_line(2)
        self.flow.set_column_spacing(8)
        self.flow.set_row_spacing(8)
        self.flow.set_homogeneous(True)
        content.pack_start(self.flow, True, True, 0)

        self._build_cards()

        # Bottom bar: skip checkbox + manage button
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(16)
        bottom.set_margin_bottom(16)

        self.skip_check = Gtk.CheckButton(label=_("Don't show at startup"))
        self.skip_check.set_active(settings.read_setting(SETTING_KEY) == "0")
        bottom.pack_start(self.skip_check, False, False, 0)

        manage_btn = Gtk.Button(label=_("Manage profiles…"))
        manage_btn.connect("clicked", self._on_manage)
        bottom.pack_end(manage_btn, False, False, 0)

        content.pack_start(bottom, False, False, 0)

        self.show_all()

    # ------------------------------------------------------------------
    # Card builders

    def _build_cards(self) -> None:
        for child in self.flow.get_children():
            self.flow.remove(child)

        active = self.pm.current_profile_id
        for profile in self.pm.get_all_profiles():
            card = self._make_profile_card(profile["id"], profile["name"], profile["id"] == active)
            self.flow.add(card)

        self.flow.add(self._make_add_card())
        self.flow.show_all()

    def _make_profile_card(self, pid: str, name: str, is_active: bool) -> Gtk.Button:
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("profile-card")
        if is_active:
            btn.get_style_context().add_class("profile-card-active")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(16)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)

        # Colored letter avatar via per-widget CSS
        avatar = Gtk.Label(label=(name[0].upper() if name else "?"))
        color = _avatar_color(pid)
        css_cls = "avatar_" + pid.replace("-", "_")
        css = (
            f".{css_cls} {{"
            f"  background-color: {color};"
            f"  border-radius: 32px;"
            f"  color: white;"
            f"  font-size: 22px;"
            f"  font-weight: bold;"
            f"  min-width: 64px;"
            f"  min-height: 64px;"
            f"}}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        avatar.get_style_context().add_class(css_cls)
        avatar.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        vbox.pack_start(avatar, False, False, 0)

        name_lbl = Gtk.Label(label=name)
        name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_lbl.set_max_width_chars(10)
        vbox.pack_start(name_lbl, False, False, 0)

        if is_active:
            check_lbl = Gtk.Label(label="✓")
            check_lbl.get_style_context().add_class("dim-label")
            vbox.pack_start(check_lbl, False, False, 0)

        btn.add(vbox)
        btn.connect("clicked", self._on_profile_selected, pid)
        return btn

    def _make_add_card(self) -> Gtk.Button:
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("profile-card")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(16)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)

        # Icon in a fixed-size box to match avatar dimensions
        icon = Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        icon.set_pixel_size(40)
        icon_box = Gtk.Box()
        icon_box.set_size_request(64, 64)
        icon_box.set_halign(Gtk.Align.CENTER)
        icon_box.pack_start(icon, True, True, 0)
        vbox.pack_start(icon_box, False, False, 0)

        lbl = Gtk.Label(label=_("Add profile"))
        vbox.pack_start(lbl, False, False, 0)

        btn.add(vbox)
        btn.connect("clicked", self._on_add)
        return btn

    # ------------------------------------------------------------------
    # Handlers

    def _on_profile_selected(self, _btn, pid: str) -> None:
        self.pm.switch(pid)
        self._persist_skip()
        self.response(Gtk.ResponseType.OK)

    def _on_add(self, _btn) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("New profile"),
        )
        dlg.format_secondary_text(_("Enter a name for the new profile:"))
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        dlg.get_message_area().pack_start(entry, False, False, 0)
        dlg.show_all()
        resp = dlg.run()
        name = entry.get_text().strip()
        dlg.destroy()
        if resp == Gtk.ResponseType.OK and name:
            new_id = self.pm.create_profile(name)
            self.pm.switch(new_id)
            self._persist_skip()
            self.response(Gtk.ResponseType.OK)

    def _on_manage(self, _btn) -> None:
        from lutris.gui.dialogs.profile_dialog import ProfileDialog

        mgr = ProfileDialog(parent=self)
        mgr.run()
        mgr.destroy()
        self._build_cards()

    def _persist_skip(self) -> None:
        settings.write_setting(SETTING_KEY, "0" if self.skip_check.get_active() else "1")
