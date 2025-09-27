"""Game Info Panel implementation"""

import os
import requests
import shutil
import uuid

# Standard Library
# pylint: disable=no-member,too-many-public-methods
from gettext import gettext as _
from pathlib import Path
from typing import Any, Optional

# Third Party Libraries
from gi.repository import GdkPixbuf, Gtk, Pango

# Lutris Modules
from lutris import settings
from lutris.game import Game
from lutris.gui.config.boxes import AdvancedSettingsBox
from lutris.gui.widgets.common import Label, NumberEntry, SlugEntry
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.gui.widgets.utils import MEDIA_CACHE_INVALIDATED, get_image_file_extension, open_uri
from lutris.runners import get_installed
from lutris.services.lutris import LutrisBanner, LutrisCoverart, LutrisIcon, download_lutris_media
from lutris.services.service_media import resolve_media_path
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger

COVERART_KEY = "coverart_big"
BANNER_KEY = "banner"
ICON_KEY = "icon"


class GameInfoBox(AdvancedSettingsBox):
    """Generate a vbox for the Game Info tab."""

    def __init__(self, parent_widget: Any, game: Game | None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.parent_widget = parent_widget

        self.game = game

        self.slug = game.slug if game else None
        self.initial_slug = game.slug if game else None

        self.name_entry = None
        self.sortname_entry = None
        self.runner_dropdown = None
        self.runner_index = None
        self.slug_entry = None
        self.slug_change_button = None
        self.directory_entry = None
        self.year_entry = None
        self.playtime_entry = None
        self.service_medias = {ICON_KEY: LutrisIcon(), BANNER_KEY: LutrisBanner(), COVERART_KEY: LutrisCoverart()}

        self.image_buttons = {}
        self.image_path_entries = {}
        self.image_path_open_button = {}

        if self.game:
            centering_container = Gtk.HBox()
            banner_box = self._get_banner_box()
            centering_container.pack_start(banner_box, True, False, 0)
            self.pack_start(centering_container, False, False, 0)  # Banner
            self._get_banner_entries()  # Cover Browse, Banner Browse, Icon Browse

        self.pack_start(self._get_name_box(), False, False, 6)  # Game name
        self.pack_start(self._get_sortname_box(), False, False, 6)  # Game sort name

        self.pack_start(self._get_runner_box(), False, False, 6)  # Runner

        self.pack_start(self._get_year_box(), False, False, 6)  # Year

        self.pack_start(self._get_playtime_box(), False, False, 6)  # Playtime

        if self.game:
            self.pack_start(self._get_slug_box(), False, False, 6)
            self.pack_start(self._get_directory_box(), False, False, 6)
            self.pack_start(self._get_launch_config_box(), False, False, 6)

        # Read the show advanced options from the settings before updating the widget to have
        # it show correctly
        self.advanced_visibility = settings.read_setting("show_advanced_options") == "True"

        self.update_widgets()

    def update_widgets(self):
        if self.game:
            self._cover_entry.set_visible(self._advanced_visibility)
            self._cover_entry.set_no_show_all(not self._advanced_visibility)
            self._banner_entry.set_visible(self._advanced_visibility)
            self._banner_entry.set_no_show_all(not self._advanced_visibility)
            self._icon_entry.set_visible(self._advanced_visibility)
            self._icon_entry.set_no_show_all(not self._advanced_visibility)

    def _get_name_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Name"))
        box.pack_start(label, False, False, 0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_max_length(150)
        if self.game:
            self.name_entry.set_text(self.game.name)
        box.pack_start(self.name_entry, True, True, 0)
        return box

    def _get_sortname_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Sort name"))
        box.pack_start(label, False, False, 0)
        self.sortname_entry = Gtk.Entry()
        self.sortname_entry.set_max_length(150)
        if self.game:
            self.sortname_entry.set_placeholder_text(self.game.name)
            if self.game.sortname:
                self.sortname_entry.set_text(self.game.sortname)
        box.pack_start(self.sortname_entry, True, True, 0)
        return box

    def _get_year_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        label = Label(_("Release year"))
        box.pack_start(label, False, False, 0)
        self.year_entry = NumberEntry()
        self.year_entry.set_max_length(10)
        if self.game:
            self.year_entry.set_text(str(self.game.year or ""))
        box.pack_start(self.year_entry, True, True, 0)

        return box

    def _get_playtime_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        label = Label(_("Playtime"))
        box.pack_start(label, False, False, 0)
        self.playtime_entry = Gtk.Entry()

        if self.game:
            self.playtime_entry.set_text(self.game.formatted_playtime)
        box.pack_start(self.playtime_entry, True, True, 0)

        return box

    def _get_slug_box(self):
        slug_box = Gtk.VBox(spacing=12, margin_right=12, margin_left=12)

        slug_entry_box = Gtk.Box(spacing=12, margin_right=0, margin_left=0)
        slug_label = Label()
        slug_label.set_markup(
            _(f"Identifier\n<span size='x-small'>(Internal ID: {self.game.id if self.game else '""'})</span>")
        )
        slug_entry_box.pack_start(slug_label, False, False, 0)

        self.slug_entry = SlugEntry()
        if self.game:
            self.slug_entry.set_text(self.game.slug)
        self.slug_entry.set_sensitive(False)
        self.slug_entry.connect("activate", self.on_slug_entry_activate)
        slug_entry_box.pack_start(self.slug_entry, True, True, 0)

        self.slug_change_button = Gtk.Button(_("Change"))
        self.slug_change_button.connect("clicked", self.on_slug_change_clicked)
        slug_entry_box.pack_start(self.slug_change_button, False, False, 0)

        slug_box.pack_start(slug_entry_box, True, True, 0)

        return slug_box

    def _get_directory_box(self):
        """Return widget displaying the location of the game and allowing to move it"""
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, visible=True)
        label = Label(_("Directory"))
        box.pack_start(label, False, False, 0)
        self.directory_entry = Gtk.Entry(visible=True)
        if self.game:
            self.directory_entry.set_text(self.game.directory)
        self.directory_entry.set_sensitive(False)
        box.pack_start(self.directory_entry, True, True, 0)
        move_button = Gtk.Button(_("Move"), visible=True)
        move_button.connect("clicked", self.parent_widget.on_move_clicked)
        box.pack_start(move_button, False, False, 0)
        return box

    def _get_launch_config_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, visible=True)

        if self.game and self.game.config:
            game_config = self.game.config.game_level.get("game", {})
        else:
            game_config = {}
        preferred_name = game_config.get("preferred_launch_config_name")

        if preferred_name:
            spacer = Gtk.Box()
            spacer.set_size_request(230, -1)
            box.pack_start(spacer, False, False, 0)

            if preferred_name == Game.PRIMARY_LAUNCH_CONFIG_NAME:
                text = _("The default launch option will be used for this game")
            else:
                text = _("The '%s' launch option will be used for this game") % preferred_name
            label = Gtk.Label(text)
            label.set_line_wrap(True)
            label.set_halign(Gtk.Align.START)
            label.set_xalign(0.0)
            label.set_valign(Gtk.Align.CENTER)
            box.pack_start(label, True, True, 0)
            button = Gtk.Button(_("Reset"))
            button.connect("clicked", self.on_reset_preferred_launch_config_clicked, box)
            button.set_valign(Gtk.Align.CENTER)
            box.pack_start(button, False, False, 0)
        else:
            box.hide()
        return box

    def on_reset_preferred_launch_config_clicked(self, _button, launch_config_box):
        game_config = self.game.config.game_level.get("game", {}) if self.game and self.game.config else {}
        game_config.pop("preferred_launch_config_name", None)
        game_config.pop("preferred_launch_config_index", None)
        launch_config_box.hide()

    def _get_runner_box(self):
        runner_box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        runner_label = Label(_("Runner"))
        runner_box.pack_start(runner_label, False, False, 0)

        self.runner_dropdown = self._get_runner_dropdown()
        runner_box.pack_start(self.runner_dropdown, True, True, 0)

        return runner_box

    def _get_banner_box(self):
        banner_box = Gtk.Grid()
        banner_box.set_margin_top(12)
        banner_box.set_column_spacing(12)
        banner_box.set_row_spacing(4)

        self._create_image_button(
            banner_box,
            COVERART_KEY,
            _("Set custom cover art"),
            _("Remove custom cover art"),
            _("Download custom cover art"),
        )
        self._create_image_button(
            banner_box, BANNER_KEY, _("Set custom banner"), _("Remove custom banner"), _("Download custom banner")
        )
        self._create_image_button(
            banner_box, ICON_KEY, _("Set custom icon"), _("Remove custom icon"), _("Download custom icon")
        )

        return banner_box

    def _get_banner_entries(self):
        self._cover_entry = self._create_image_entry(COVERART_KEY, _("Cover"), _("Location of custom cover art"))
        self.pack_start(self._cover_entry, False, False, 6)  # Cover

        self._banner_entry = self._create_image_entry(BANNER_KEY, _("Banner"), _("Location of custom banner"))
        self.pack_start(self._banner_entry, False, False, 6)  # Banner

        self._icon_entry = self._create_image_entry(ICON_KEY, _("Icon"), _("Location of custom icon"))
        self.pack_start(self._icon_entry, False, False, 6)  # Icon

    def _create_image_entry(self, image_type, image_label, image_entry_tooltip):
        """Return widget displaying the location of the coverart, banner or icon image"""
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, visible=True)
        label = Label(image_label)
        box.pack_start(label, False, False, 0)

        # Get the current entry path for the image type and set it as the text
        path_entry = Gtk.Entry(visible=True)
        path_entry.set_tooltip_text(image_entry_tooltip)
        path_entry.set_sensitive(False)

        box.pack_start(path_entry, True, True, 0)

        open_button = Gtk.Button.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON)
        open_button.show()
        open_button.set_tooltip_text(_("Open in file browser"))
        open_button.get_style_context().add_class("circular")
        open_button.connect("clicked", self.on_open_image_location_in_file_browser_clicked, image_type)
        self.image_path_open_button[image_type] = open_button

        path_entry.connect("changed", lambda _: self.refresh_image_path_entry(image_type))

        box.pack_start(open_button, False, False, 0)

        self.image_path_entries[image_type] = path_entry
        # Refresh the path entry in the image text entry after it has been added to the image_path_entries dict
        self.refresh_image_path_entry(image_type)
        return box

    def _create_image_button(self, banner_box, image_type, image_tooltip, reset_tooltip, download_tooltip):
        """This adds an image button and its reset button to the box given,
        and adds the image button to self.image_buttons for future reference."""

        image_button_container = Gtk.VBox()
        button_container = Gtk.HBox()

        image_button = Gtk.Button()
        self._set_image(image_type, image_button)
        image_button.set_valign(Gtk.Align.CENTER)
        image_button.set_tooltip_text(image_tooltip)
        image_button.connect("clicked", self.on_custom_image_select, image_type)
        image_button_container.pack_start(image_button, True, True, 0)

        reset_button = Gtk.Button.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.MENU)
        reset_button.set_relief(Gtk.ReliefStyle.NONE)
        reset_button.set_tooltip_text(reset_tooltip)
        reset_button.connect("clicked", self.on_custom_image_reset_clicked, image_type)
        reset_button.set_valign(Gtk.Align.CENTER)
        button_container.pack_start(reset_button, True, False, 0)

        download_button = Gtk.Button.new_from_icon_name("web-browser-symbolic", Gtk.IconSize.MENU)
        download_button.set_relief(Gtk.ReliefStyle.NONE)
        download_button.set_tooltip_text(download_tooltip)
        download_button.connect("clicked", self.on_custom_image_download_clicked, image_type)
        download_button.set_valign(Gtk.Align.CENTER)
        button_container.pack_end(download_button, True, False, 0)

        banner_box.add(image_button_container)
        banner_box.attach_next_to(button_container, image_button_container, Gtk.PositionType.BOTTOM, 1, 1)

        self.image_buttons[image_type] = image_button

    def _set_image(self, image_format, image_button):
        scale_factor = self.get_scale_factor()
        service_media = self.service_medias[image_format]
        game_slug = self.slug or (self.game.slug if self.game else "")
        media_path = resolve_media_path(service_media.get_possible_media_paths(game_slug)).path
        try:
            image = ScaledImage.new_from_media_path(media_path, service_media.config_ui_size, scale_factor)
            image_button.set_image(image)
        except Exception as ex:
            # We need to survive nasty data in the media files, so the user can replace
            # them.
            logger.exception("Unable to load media '%s': %s", image_format, ex)

    def _get_runner_dropdown(self):
        runner_liststore = self._get_runner_liststore()
        runner_dropdown = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_dropdown.set_id_column(1)
        runner_index = 0
        if self.parent_widget.runner_name:
            for runner in runner_liststore:
                if self.parent_widget.runner_name == str(runner[1]):
                    break
                runner_index += 1
        self.runner_index = runner_index
        runner_dropdown.set_active(self.runner_index)
        runner_dropdown.connect("changed", self.parent_widget.on_runner_changed)
        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.END
        runner_dropdown.pack_start(cell, True)
        runner_dropdown.add_attribute(cell, "text", 0)
        return runner_dropdown

    @staticmethod
    def _get_runner_liststore():
        """Build a ListStore with available runners."""
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append((_("Select a runner from the list"), ""))
        for runner in get_installed():
            description = runner.description
            runner_liststore.append(("%s (%s)" % (runner.human_name, description), runner.name))
        return runner_liststore

    def on_slug_change_clicked(self, widget):
        if not self.slug_entry:
            return
        if self.slug_entry.get_sensitive() is False:
            widget.set_label(_("Apply"))
            self.slug_entry.set_sensitive(True)
        else:
            self.change_game_slug()

    def on_slug_entry_activate(self, _widget):
        self.change_game_slug()

    def change_game_slug(self):
        if not self.slug_entry:
            return
        slug = self.slug_entry.get_text()
        self.slug = slug
        self.slug_entry.set_sensitive(False)
        if self.slug_change_button:
            self.slug_change_button.set_label(_("Change"))
        AsyncCall(download_lutris_media, self.refresh_all_images_cb, self.slug)

    def refresh_all_images_cb(self, _result, _error):
        for image_type, image_button in self.image_buttons.items():
            self._set_image(image_type, image_button)

    def get_image_path(self, image_type) -> Optional[Path]:
        """Get the path of the image file"""
        if image_type not in self.service_medias:
            return None

        service_media = self.service_medias[image_type]
        game_slug = self.slug or (self.game.slug if self.game else "")
        media_path = resolve_media_path(service_media.get_possible_media_paths(game_slug))

        image_path = None
        if media_path.exists:
            image_path = Path(media_path.path)
        return image_path

    def on_open_image_location_in_file_browser_clicked(self, _widget, image_type):
        if path := self.get_image_path(image_type):
            open_uri(str(path.parent))

    def refresh_image_path_entry(self, image_type):
        image_path = str(self.get_image_path(image_type) or "")
        if image_path_entry := self.image_path_entries.get(image_type):
            image_path_entry.set_text(image_path)
            self.image_path_open_button[image_type].set_sensitive(bool(image_path))

    def on_custom_image_select(self, _widget, image_type):
        dialog = Gtk.FileChooserNative.new(
            _("Please choose a custom image"),
            self.parent_widget,
            Gtk.FileChooserAction.OPEN,
            None,
            None,
        )

        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("Images"))
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            image_path = dialog.get_filename()
            self.save_custom_media(image_type, image_path)
        dialog.destroy()

    def on_custom_image_reset_clicked(self, _widget, image_type):
        self.refresh_image(image_type)

    def on_custom_image_download_clicked(self, _widget, image_type):
        dialog = UrlDialog(self.parent_widget)
        response = dialog.run()

        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return

        url = dialog.get_url()
        dialog.destroy()

        file_id = uuid.uuid4()
        tmp_file = os.path.join(settings.TMP_DIR, f"download-{file_id}.tmp")
        logger.info(f"Downloading custom image from `{url}` to `{tmp_file}`")

        def download():
            with requests.get(url, stream=True) as r:
                if not r.ok:
                    logger.error(
                        f"Request returned a status code that didn't indicate success: `{url}` (`{r.status_code}`)"
                    )
                    return
                with open(tmp_file, "wb") as fp:
                    for chunk in r.iter_content(chunk_size=8196):
                        if chunk:
                            fp.write(chunk)

            self.save_custom_media(image_type, tmp_file)

        def download_cb(_result, error):
            if error:
                raise error

        AsyncCall(download, download_cb)

    def save_custom_media(self, image_type: str, image_path: str) -> None:
        slug = self.slug or (self.game.slug if self.game else "")
        service_media = self.service_medias[image_type]
        if self.game:
            self.game.custom_images.add(image_type)
        dest_paths = [mp.path for mp in service_media.get_possible_media_paths(slug)]

        if image_path not in dest_paths:
            ext = get_image_file_extension(image_path)

            if ext:
                for candidate in dest_paths:
                    if candidate.casefold().endswith(ext):
                        self._save_copied_media_to(candidate, image_type, image_path)
                        return

            self._save_transcoded_media_to(dest_paths[0], image_type, image_path)

    def _save_copied_media_to(self, dest_path: str, image_type: str, image_path: str) -> None:
        """Copies a media file to the dest_path, but trashes the existing media
        for the game first. When complete, this updates the button indicated by
        image_type as well."""
        slug = self.slug or (self.game.slug if self.game else "")
        service_media = self.service_medias[image_type]

        def on_trashed():
            AsyncCall(copy_image, self.image_refreshed_cb)

        def copy_image():
            shutil.copy(image_path, dest_path, follow_symlinks=True)
            MEDIA_CACHE_INVALIDATED.fire()
            return image_type

        service_media.trash_media(slug, completion_function=on_trashed)

    def _save_transcoded_media_to(self, dest_path: str, image_type: str, image_path: str) -> None:
        """Transcode an image, copying it to a new path and selecting the file type
        based on the file extension of dest_path. Trashes all media for the current
        game too. Runs in the background, and when complete updates the button indicated
        by image_type."""
        slug = self.slug or (self.game.slug if self.game else "")
        service_media = self.service_medias[image_type]
        ext = get_image_file_extension(dest_path) or ".png"
        file_format = {".jpg": "jpeg", ".png": "png"}[ext]

        # If we must transcode the image, we'll scale the image up based on
        # the UI scale factor, to try to avoid blurriness. Of course this won't
        # work if the user changes the scaling later, but what can you do.
        scale_factor = self.get_scale_factor()
        width, height = service_media.custom_media_storage_size
        width = width * scale_factor
        height = height * scale_factor
        temp_file = dest_path + ".tmp"

        def transcode():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image_path, width, height)
            # JPEG encoding looks rather better at high quality;
            # PNG encoding just ignores this option.
            pixbuf.savev(temp_file, file_format, ["quality"], ["100"])
            service_media.trash_media(slug, completion_function=on_trashed)

        def transcode_cb(_result, error):
            if error:
                raise error

        def on_trashed():
            os.rename(temp_file, dest_path)
            MEDIA_CACHE_INVALIDATED.fire()
            self.image_refreshed_cb(image_type)

        AsyncCall(transcode, transcode_cb)

    def refresh_image(self, image_type):
        slug = self.slug or (self.game.slug if self.game else "")
        service_media = self.service_medias[image_type]
        if self.game:
            self.game.custom_images.discard(image_type)

        def on_trashed():
            AsyncCall(download, self.image_refreshed_cb)

        def download():
            download_lutris_media(slug)
            return image_type

        service_media.trash_media(slug, completion_function=on_trashed)

    def image_refreshed_cb(self, image_type, _error=None):
        if image_type:
            self._set_image(image_type, self.image_buttons[image_type])
            service_media = self.service_medias[image_type]
            service_media.run_system_update_desktop_icons()

            # Refresh the text entry and browse button with the new image path
            self.refresh_image_path_entry(image_type)


class UrlDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title=_("Enter URL"), transient_for=parent, flags=0)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)

        self.set_default_size(300, 100)

        box = self.get_content_area()
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("https://example.com/image.png")
        box.add(self.entry)

        self.show_all()

    def get_url(self):
        return self.entry.get_text()
