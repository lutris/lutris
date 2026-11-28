//! The application: state, navigation and the screens.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::mpsc::{channel, Receiver};
use std::sync::Arc;

use eframe::egui::{self, pos2, vec2, Align2, Color32, Id, Key, Painter, Rect, Stroke, StrokeKind, Vec2};

use crate::covers::CoverCache;
use crate::draw::{self, ACCENT, BG, DIM, GOOD, PANEL, PANEL_HI, TEXT};
use crate::input::{self, Action, Glyph, PadButton, PadStyle};
use crate::protocol::{self, Game, Incoming, Outgoing, RunState};
use crate::sounds::{Sound, Sounds};
use crate::splash::Splash;

/// Rows of the on-screen keyboard. The control characters stand for
/// backspace, clear and done.
const KEY_ROWS: [&str; 4] = ["1234567890", "qwertyuiop", "asdfghjkl\u{8}", "zxcvbnm \u{1}\u{2}"];
const KEY_BACKSPACE: char = '\u{8}';
const KEY_CLEAR: char = '\u{1}';
const KEY_DONE: char = '\u{2}';

/// Set when the user chose to quit Lutris rather than just leave this mode.
pub static QUIT_LUTRIS: AtomicBool = AtomicBool::new(false);

/// Games shown in the "recent" rows of the home screen.
const ROW_LIMIT: usize = 24;

/// Controller presses are ignored for this long after the window regains
/// focus, so the press that closed a game does not also act here.
const FOCUS_GRACE: f64 = 0.35;

/// How long an error stays on screen, in seconds.
const TOAST_SECONDS: f64 = 9.0;

/// Columns moved by a page up or down in a row of the home screen.
const HOME_PAGE_STEP: usize = 5;

/// Grid columns and visible rows assumed until the library is first drawn.
const INITIAL_LIB_COLS: usize = 7;
const INITIAL_LIB_ROWS_VISIBLE: usize = 2;

/// The row of the on-screen keyboard that has the focus when it opens: the
/// first row of letters.
const KEYBOARD_START_ROW: usize = 1;

/// Multiplier of the row in a key's navigation position; more than any row
/// has keys.
const KEY_NAV_STRIDE: usize = 16;

/// The buttons of the detail page.
const DETAIL_PLAY: usize = 0;
const DETAIL_FAVORITE: usize = 1;

// The layout is measured in units: one unit is one pixel on a 1080p screen.

/// The screen size at which a unit is exactly one pixel.
const REFERENCE_WIDTH: f32 = 1920.0;
const REFERENCE_HEIGHT: f32 = 1080.0;

/// The smallest size of a unit in pixels, however small the window.
const MIN_UNIT: f32 = 0.1;

/// Space kept free at the left and right edges of the screen.
const SCREEN_MARGIN: f32 = 72.0;

/// The centre line of the top bar, below the top of the screen.
const TOP_BAR_Y: f32 = 58.0;

/// Size of the tab names and the clock in the top bar.
const TOP_BAR_TEXT_SIZE: f32 = 28.0;

/// Size of ordinary text: facts, states and messages.
const BODY_TEXT_SIZE: f32 = 24.0;

/// Corner radius of the panels of the menu and the on-screen keyboard.
const PANEL_RADIUS: f32 = 20.0;

// Animations, in seconds.

/// The longest step animations take in one frame, so a stall does not make
/// them jump.
const MAX_FRAME_SECONDS: f32 = 0.05;

/// How long one backdrop takes to fade into the next.
const BACKDROP_FADE_SECONDS: f64 = 0.4;

/// How long a tile, a button and a key take to show they have the focus.
const TILE_FOCUS_SECONDS: f32 = 0.12;
const BUTTON_FOCUS_SECONDS: f32 = 0.1;
const KEY_FOCUS_SECONDS: f32 = 0.08;

/// How fast scrolling closes in on its target: higher is quicker.
const APPROACH_RATE: f32 = 16.0;

/// Scrolling this close to its target, in pixels, has arrived.
const APPROACH_SNAP: f32 = 0.5;

// The backdrop.

/// Brightness of the backdrop (0 to 1); less in the library, where it lies
/// behind a whole grid of covers.
const BACKDROP_BRIGHTNESS: f32 = 0.8;
const LIBRARY_BACKDROP_BRIGHTNESS: f32 = 0.45;

/// How strongly the backdrop is darkened at the top and at the bottom of the
/// screen (0 to 1).
const BACKDROP_SHADE_TOP: f32 = 0.35;
const BACKDROP_SHADE_BOTTOM: f32 = 0.94;

/// The clock is redrawn this long after the minute turns, in seconds, to be
/// sure it has.
const CLOCK_SLACK: f32 = 0.1;
const SECONDS_PER_MINUTE: libc::c_int = 60;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Tab {
    Home,
    Library,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Sort {
    Name,
    Recent,
    Playtime,
}

#[derive(Clone, PartialEq, Eq)]
enum Filter {
    All,
    Favorites,
    Category(String),
    Runner(String),
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum LibFocus {
    Filters,
    Grid,
}

#[derive(Clone)]
enum Overlay {
    Detail { id: String, button: usize },
    Menu { index: usize },
    Keyboard { row: usize, col: usize },
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Device {
    Pad,
    Keyboard,
    Mouse,
}

/// Something the mouse can point at, recorded while drawing.
#[derive(Clone, Copy)]
enum Hit {
    /// Outside an overlay: closes it.
    Dismiss,
    /// Inside an overlay's panel: swallows the click.
    Block,
    Tab(Tab),
    HomeTile(usize, usize),
    LibTile(usize),
    Filter(usize),
    Button(usize),
    MenuItem(usize),
    Key(usize, usize),
}

/// The menu's entries, and which of them picks the navigation sounds.
const MENU_ITEMS: usize = 5;
const MENU_RESUME: usize = 0;
const MENU_SOUNDS: usize = 1;
const MENU_SPLASH: usize = 2;
const MENU_EXIT: usize = 3;

#[derive(PartialEq, Eq)]
struct NavState {
    tab: Tab,
    overlays: usize,
    position: [usize; 8],
}

struct Row {
    title: &'static str,
    items: Vec<usize>,
}

struct Toast {
    text: String,
    until: f64,
}

pub struct App {
    debug_protocol: bool,
    incoming: Receiver<Incoming>,
    pad: Receiver<Action>,
    /// The kind of controller last used, as a `PadStyle`.
    pad_style: Arc<AtomicU8>,
    strings: HashMap<String, String>,
    games: Vec<Game>,
    /// What a launching game is doing, by game ID.
    statuses: HashMap<String, String>,
    got_library: bool,
    covers: CoverCache,
    sounds: Sounds,
    /// A sound an action asked for, in place of the one it would get anyway.
    pending_sound: Option<Sound>,

    tab: Tab,
    overlays: Vec<Overlay>,
    device: Device,
    hits: Vec<(Rect, Hit)>,
    toasts: Vec<Toast>,
    was_focused: bool,
    focused_at: f64,
    now: f64,

    rows: Vec<Row>,
    home_row: usize,
    home_cols: Vec<usize>,
    home_scroll_x: Vec<f32>,
    home_target_x: Vec<f32>,
    home_scroll_y: f32,
    home_reveal: bool,

    filters: Vec<Filter>,
    filter: usize,
    filter_scroll: f32,
    sort: Sort,
    query: String,
    view: Vec<usize>,
    lib_focus: LibFocus,
    lib_index: usize,
    lib_cols: usize,
    lib_rows_visible: usize,
    lib_scroll: f32,
    lib_target: f32,
    lib_reveal: bool,

    /// Cover paths behind the previous and the current backdrop.
    backdrop: [Option<String>; 2],
    backdrop_since: f64,
    backdrop_fade: f32,

    /// The opening animation, while it lasts.
    splash: Option<Splash>,
    /// Whether the animation is to be played the next time.
    splash_enabled: bool,
}

impl App {
    pub fn new(cc: &eframe::CreationContext<'_>, splash: bool, debug_protocol: bool) -> Self {
        let ctx = &cc.egui_ctx;

        draw::setup_fonts(ctx);

        let (incoming_tx, incoming) = channel();

        protocol::spawn_reader(incoming_tx, ctx.clone());

        let (pad_tx, pad) = channel();
        let pad_style = Arc::new(AtomicU8::new(PadStyle::None as u8));

        input::spawn_gamepad_thread(pad_tx, ctx.clone(), pad_style.clone());
        protocol::send(&Outgoing::Ready);

        Self {
            debug_protocol,
            incoming,
            pad,
            pad_style,
            strings: HashMap::new(),
            games: Vec::new(),
            statuses: HashMap::new(),
            got_library: false,
            covers: CoverCache::new(ctx),
            sounds: Sounds::new(),
            pending_sound: None,
            tab: Tab::Home,
            overlays: Vec::new(),
            device: Device::Pad,
            hits: Vec::new(),
            toasts: Vec::new(),
            was_focused: true,
            focused_at: 0.0,
            now: 0.0,
            rows: Vec::new(),
            home_row: 0,
            home_cols: Vec::new(),
            home_scroll_x: Vec::new(),
            home_target_x: Vec::new(),
            home_scroll_y: 0.0,
            home_reveal: true,
            filters: vec![Filter::All],
            filter: 0,
            filter_scroll: 0.0,
            sort: Sort::Name,
            query: String::new(),
            view: Vec::new(),
            lib_focus: LibFocus::Grid,
            lib_index: 0,
            lib_cols: INITIAL_LIB_COLS,
            lib_rows_visible: INITIAL_LIB_ROWS_VISIBLE,
            lib_scroll: 0.0,
            lib_target: 0.0,
            lib_reveal: true,
            backdrop: [None, None],
            backdrop_since: 0.0,
            backdrop_fade: 1.0,
            splash: if splash { Splash::new(ctx) } else { None },
            splash_enabled: splash,
        }
    }

    /// The translation of an interface string.
    fn t<'a>(&'a self, text: &'a str) -> &'a str {
        self.strings.get(text).map_or(text, String::as_str)
    }

    /// Whether the hints on screen should name controller buttons rather
    /// than keys.
    fn shows_pad_hints(&self) -> bool {
        self.device == Device::Pad && self.pad_style() != PadStyle::None
    }

    fn pad_style(&self) -> PadStyle {
        PadStyle::from_u8(self.pad_style.load(Ordering::Relaxed))
    }

    fn game_index(&self, id: &str) -> Option<usize> {
        self.games.iter().position(|game| game.id == id)
    }

    // ---------------------------------------------------------------- data

    fn handle_message(&mut self, ctx: &egui::Context, message: Incoming) {
        match message {
            Incoming::Init { strings, sounds } => {
                self.strings = strings;

                let dirs: Vec<std::path::PathBuf> = sounds.dirs.iter().map(Into::into).collect();

                self.sounds.configure(&dirs, &sounds.pack);
            }
            Incoming::Library { games } => self.set_library(games),
            Incoming::GameState { id, state, status } => {
                if let Some(index) = self.game_index(&id) {
                    self.games[index].state = state;
                }

                if state == RunState::Stopped || status.is_empty() {
                    self.statuses.remove(&id);
                } else {
                    self.statuses.insert(id, status);
                }
            }
            Incoming::Error { message } => {
                self.sounds.play(Sound::Error);
                self.toasts.push(Toast {
                    text: message,
                    until: self.now + TOAST_SECONDS,
                });
            }
            Incoming::Quit => ctx.send_viewport_cmd(egui::ViewportCommand::Close),
            Incoming::DebugAction { action } => {
                if self.debug_protocol {
                    if let Some(action) = Action::from_name(&action) {
                        // A test has no patience for the opening animation.
                        self.splash = None;
                        self.device = Device::Pad;
                        self.handle_action(ctx, action);
                    }
                }
            }
            Incoming::DebugScreenshot { path } => {
                if self.debug_protocol {
                    request_screenshot(ctx, path);
                }
            }
        }
    }

    fn set_library(&mut self, games: Vec<Game>) {
        let focused_home = self.home_game().map(|index| self.games[index].id.clone());
        let focused_lib = self.view.get(self.lib_index).map(|&index| self.games[index].id.clone());
        let filter = self.filters.get(self.filter).cloned().unwrap_or(Filter::All);

        self.games = games;
        self.got_library = true;

        // The library changing is also when covers may have.
        self.covers.refresh();
        self.statuses
            .retain(|id, _| self.games.iter().any(|game| &game.id == id));
        self.overlays.retain(|overlay| match overlay {
            Overlay::Detail { id, .. } => self.games.iter().any(|game| &game.id == id),
            _ => true,
        });

        self.build_rows();

        if let Some(id) = focused_home {
            if let Some(row) = self.rows.get(self.home_row) {
                if let Some(col) = row.items.iter().position(|&index| self.games[index].id == id) {
                    self.home_cols[self.home_row] = col;
                }
            }
        }

        self.build_filters();
        self.filter = self.filters.iter().position(|f| *f == filter).unwrap_or(0);
        self.build_view(focused_lib.as_deref());
    }

    fn build_rows(&mut self) {
        let games = &self.games;
        let by_name = |a: &usize, b: &usize| sort_key(&games[*a]).cmp(&sort_key(&games[*b]));
        let mut rows = Vec::new();

        let mut recent: Vec<usize> = (0..games.len()).filter(|&i| games[i].lastplayed > 0).collect();

        recent.sort_by_key(|&i| std::cmp::Reverse(games[i].lastplayed));
        recent.truncate(ROW_LIMIT);

        if !recent.is_empty() {
            rows.push(Row {
                title: "Recently played",
                items: recent,
            });
        }

        let mut favorites: Vec<usize> = (0..games.len()).filter(|&i| games[i].favorite).collect();

        favorites.sort_by(by_name);

        if !favorites.is_empty() {
            rows.push(Row {
                title: "Favorites",
                items: favorites,
            });
        }

        let mut added: Vec<usize> = (0..games.len()).filter(|&i| games[i].installed_at > 0).collect();

        added.sort_by_key(|&i| std::cmp::Reverse(games[i].installed_at));
        added.truncate(ROW_LIMIT);

        if !added.is_empty() {
            rows.push(Row {
                title: "Recently added",
                items: added,
            });
        }

        if rows.is_empty() && !games.is_empty() {
            let mut all: Vec<usize> = (0..games.len()).collect();

            all.sort_by(by_name);
            all.truncate(ROW_LIMIT);
            rows.push(Row {
                title: "All games",
                items: all,
            });
        }

        self.rows = rows;

        let count = self.rows.len();

        self.home_row = self.home_row.min(count.saturating_sub(1));
        self.home_cols.resize(count, 0);
        self.home_scroll_x.resize(count, 0.0);
        self.home_target_x.resize(count, 0.0);

        for (row, col) in self.rows.iter().zip(self.home_cols.iter_mut()) {
            *col = (*col).min(row.items.len().saturating_sub(1));
        }

        self.home_reveal = true;
    }

    fn build_filters(&mut self) {
        let mut filters = vec![Filter::All];

        if self.games.iter().any(|game| game.favorite) {
            filters.push(Filter::Favorites);
        }

        let mut categories: Vec<&str> = self
            .games
            .iter()
            .flat_map(|game| game.categories.iter().map(String::as_str))
            .collect();
        categories.sort_unstable_by_key(|name| name.to_lowercase());
        categories.dedup();
        filters.extend(categories.into_iter().map(|name| Filter::Category(name.to_owned())));

        let mut runners: Vec<&str> = self
            .games
            .iter()
            .map(|game| game.runner.as_str())
            .filter(|runner| !runner.is_empty())
            .collect();
        runners.sort_unstable_by_key(|name| name.to_lowercase());
        runners.dedup();

        if runners.len() > 1 {
            filters.extend(runners.into_iter().map(|name| Filter::Runner(name.to_owned())));
        }

        self.filters = filters;
    }

    /// Recomputes the games shown in the library, keeping the focus on the
    /// game with the ID given if it is still shown.
    fn build_view(&mut self, keep: Option<&str>) {
        let games = &self.games;
        let filter = self.filters.get(self.filter).unwrap_or(&Filter::All);
        let query = self.query.trim().to_lowercase();
        let mut view: Vec<usize> = (0..games.len())
            .filter(|&i| {
                let game = &games[i];
                let passes = match filter {
                    Filter::All => true,
                    Filter::Favorites => game.favorite,
                    Filter::Category(name) => game.categories.contains(name),
                    Filter::Runner(name) => &game.runner == name,
                };

                passes && (query.is_empty() || game.name.to_lowercase().contains(&query))
            })
            .collect();
        match self.sort {
            Sort::Name => view.sort_by_cached_key(|&i| sort_key(&games[i])),
            Sort::Recent => view.sort_by_cached_key(|&i| (std::cmp::Reverse(games[i].lastplayed), sort_key(&games[i]))),
            Sort::Playtime => view.sort_by(|&a, &b| {
                games[b]
                    .playtime
                    .total_cmp(&games[a].playtime)
                    .then_with(|| sort_key(&games[a]).cmp(&sort_key(&games[b])))
            }),
        }

        self.lib_index = keep
            .and_then(|id| view.iter().position(|&i| games[i].id == id))
            .unwrap_or(0);
        self.view = view;
        if self.view.is_empty() && self.lib_focus == LibFocus::Grid && self.query.is_empty() {
            self.lib_focus = LibFocus::Filters;
        }

        self.lib_reveal = true;
    }

    fn refresh_view(&mut self) {
        let keep = self.view.get(self.lib_index).map(|&i| self.games[i].id.clone());

        self.build_view(keep.as_deref());
    }

    fn home_game(&self) -> Option<usize> {
        let row = self.rows.get(self.home_row)?;

        row.items.get(*self.home_cols.get(self.home_row)?).copied()
    }

    /// The game the screen is about right now, which sets the backdrop.
    fn current_game(&self) -> Option<usize> {
        for overlay in self.overlays.iter().rev() {
            if let Overlay::Detail { id, .. } = overlay {
                return self.game_index(id);
            }
        }

        match self.tab {
            Tab::Home => self.home_game(),
            Tab::Library => self.view.get(self.lib_index).copied(),
        }
    }

    // --------------------------------------------------------------- input

    /// Where the user is, as far as navigation goes; when an action leaves
    /// this unchanged, nothing happened and nothing is heard.
    fn nav_state(&self) -> NavState {
        let overlay = match self.overlays.last() {
            Some(Overlay::Detail { button, .. }) => *button,
            Some(Overlay::Menu { index }) => *index,
            Some(Overlay::Keyboard { row, col }) => row * KEY_NAV_STRIDE + col,
            None => 0,
        };

        NavState {
            tab: self.tab,
            overlays: self.overlays.len(),
            position: [
                self.home_row,
                self.home_cols.get(self.home_row).copied().unwrap_or(0),
                self.lib_focus as usize,
                self.lib_index,
                self.filter,
                self.sort as usize,
                overlay,
                self.query.len(),
            ],
        }
    }

    /// True if the opening animation is still playing: then whatever the
    /// user just did is not passed on, and cuts the animation short instead.
    fn skips_splash(&mut self) -> bool {
        match &mut self.splash {
            Some(splash) if splash.blocks_input(self.now) => {
                splash.skip(self.now);
                true
            }
            _ => false,
        }
    }

    fn handle_action(&mut self, ctx: &egui::Context, action: Action) {
        if self.skips_splash() {
            return;
        }

        let before = self.nav_state();

        self.pending_sound = None;
        self.dispatch_action(ctx, action);

        let after = self.nav_state();

        // What the pointer could hit was noted when the last frame was drawn.
        // Once the screen has changed, none of it is there any more.
        if after.tab != before.tab || after.overlays != before.overlays {
            self.hits.clear();
        }

        let sound = self.pending_sound.take().or_else(|| {
            if after == before {
                return None;
            }

            Some(match action {
                Action::Accept => Sound::Select,
                Action::Back => Sound::Back,
                Action::TabPrev | Action::TabNext => Sound::Tab,
                Action::Menu | Action::Search if after.overlays > before.overlays => Sound::Open,
                Action::Menu | Action::Search => Sound::Back,
                Action::Alt => Sound::Toggle,
                _ => Sound::Move,
            })
        });

        if let Some(sound) = sound {
            self.sounds.play(sound);
        }
    }

    fn dispatch_action(&mut self, ctx: &egui::Context, action: Action) {
        match self.overlays.last().cloned() {
            Some(Overlay::Detail { id, button }) => self.detail_action(action, &id, button),
            Some(Overlay::Menu { index }) => self.menu_action(ctx, action, index),
            Some(Overlay::Keyboard { row, col }) => self.keyboard_action(action, row, col),
            None => self.screen_action(action),
        }
    }

    fn screen_action(&mut self, action: Action) {
        match action {
            Action::TabPrev | Action::TabNext => {
                self.tab = match self.tab {
                    Tab::Home => Tab::Library,
                    Tab::Library => Tab::Home,
                };
            }
            Action::Menu => self.overlays.push(Overlay::Menu { index: MENU_RESUME }),
            Action::Search => {
                self.tab = Tab::Library;
                self.lib_focus = LibFocus::Grid;
                self.overlays.push(Overlay::Keyboard {
                    row: KEYBOARD_START_ROW,
                    col: 0,
                });
            }
            Action::Back => {
                if self.tab == Tab::Library && !self.query.is_empty() {
                    self.query.clear();
                    self.refresh_view();
                } else if self.tab == Tab::Library {
                    self.tab = Tab::Home;
                } else {
                    self.overlays.push(Overlay::Menu { index: MENU_RESUME });
                }
            }
            _ => match self.tab {
                Tab::Home => self.home_action(action),
                Tab::Library => self.library_action(action),
            },
        }
    }

    fn home_action(&mut self, action: Action) {
        let Some(row) = self.rows.get(self.home_row) else {
            return;
        };

        let last = row.items.len().saturating_sub(1);
        let col = &mut self.home_cols[self.home_row];

        match action {
            Action::Left => *col = col.saturating_sub(1),
            Action::Right => *col = (*col + 1).min(last),
            Action::PageUp => *col = col.saturating_sub(HOME_PAGE_STEP),
            Action::PageDown => *col = (*col + HOME_PAGE_STEP).min(last),
            Action::Up => self.home_row = self.home_row.saturating_sub(1),
            Action::Down => self.home_row = (self.home_row + 1).min(self.rows.len() - 1),
            Action::Accept => {
                if let Some(index) = self.home_game() {
                    self.open_detail(index);
                }
            }
            _ => {}
        }

        self.home_reveal = true;
    }

    fn library_action(&mut self, action: Action) {
        if action == Action::Alt {
            self.sort = match self.sort {
                Sort::Name => Sort::Recent,
                Sort::Recent => Sort::Playtime,
                Sort::Playtime => Sort::Name,
            };

            self.refresh_view();

            return;
        }

        if self.lib_focus == LibFocus::Filters {
            match action {
                Action::Left if self.filter > 0 => {
                    self.filter -= 1;
                    self.build_view(None);
                }
                Action::Right if self.filter + 1 < self.filters.len() => {
                    self.filter += 1;
                    self.build_view(None);
                }
                Action::Down | Action::Accept if !self.view.is_empty() => {
                    self.lib_focus = LibFocus::Grid;
                    self.lib_reveal = true;
                }
                _ => {}
            }

            return;
        }

        let count = self.view.len();
        if count == 0 {
            if action == Action::Up {
                self.lib_focus = LibFocus::Filters;
            }

            return;
        }

        let cols = self.lib_cols.max(1);
        let page = self.lib_rows_visible.max(1) * cols;
        let index = self.lib_index;

        match action {
            Action::Left if !index.is_multiple_of(cols) => self.lib_index -= 1,
            Action::Right if index % cols < cols - 1 && index + 1 < count => self.lib_index += 1,
            Action::Up if index >= cols => self.lib_index -= cols,
            Action::Up => self.lib_focus = LibFocus::Filters,
            Action::Down if index + cols < count => self.lib_index += cols,
            // From the row above a short last row, land on its last game.
            Action::Down if index / cols < (count - 1) / cols => self.lib_index = count - 1,
            Action::PageUp => self.lib_index = index.saturating_sub(page),
            Action::PageDown => self.lib_index = (index + page).min(count - 1),
            Action::Accept => self.open_detail(self.view[index]),
            _ => {}
        }

        self.lib_reveal = true;
    }

    fn open_detail(&mut self, index: usize) {
        self.overlays.push(Overlay::Detail {
            id: self.games[index].id.clone(),
            button: DETAIL_PLAY,
        });
    }

    fn detail_action(&mut self, action: Action, id: &str, button: usize) {
        let Some(index) = self.game_index(id) else {
            self.overlays.pop();

            return;
        };

        match action {
            Action::Left | Action::Right => {
                let button = if action == Action::Left {
                    DETAIL_PLAY
                } else {
                    DETAIL_FAVORITE
                };
                if let Some(Overlay::Detail { button: current, .. }) = self.overlays.last_mut() {
                    *current = button;
                }
            }
            Action::Accept if button == DETAIL_PLAY => {
                let game = &mut self.games[index];
                if game.state == RunState::Stopped {
                    // Show the launch at once; Lutris corrects us if it fails.
                    game.state = RunState::Launching;
                    protocol::send(&Outgoing::Launch { id: id.to_owned() });
                    self.pending_sound = Some(Sound::Launch);
                } else {
                    protocol::send(&Outgoing::Stop { id: id.to_owned() });
                    self.pending_sound = Some(Sound::Select);
                }
            }
            Action::Accept => {
                let game = &mut self.games[index];

                game.favorite = !game.favorite;
                protocol::send(&Outgoing::SetFavorite {
                    id: id.to_owned(),
                    favorite: game.favorite,
                });

                self.pending_sound = Some(Sound::Toggle);
            }
            Action::Back => {
                self.overlays.pop();
            }
            Action::Menu => self.overlays.push(Overlay::Menu { index: MENU_RESUME }),
            _ => {}
        }
    }

    fn menu_action(&mut self, ctx: &egui::Context, action: Action, index: usize) {
        let set = |app: &mut Self, value: usize| {
            if let Some(Overlay::Menu { index }) = app.overlays.last_mut() {
                *index = value;
            }
        };

        match action {
            Action::Up => set(self, index.saturating_sub(1)),
            Action::Down => set(self, (index + 1).min(MENU_ITEMS - 1)),
            Action::Back | Action::Menu => {
                self.overlays.pop();
            }
            Action::Left | Action::Right if index == MENU_SOUNDS => self.cycle_sounds(action == Action::Right),
            Action::Left | Action::Right if index == MENU_SPLASH => self.toggle_splash(),
            Action::Accept => match index {
                MENU_RESUME => {
                    self.overlays.pop();
                }
                MENU_SOUNDS => self.cycle_sounds(true),
                MENU_SPLASH => self.toggle_splash(),
                MENU_EXIT => ctx.send_viewport_cmd(egui::ViewportCommand::Close),
                _ => {
                    QUIT_LUTRIS.store(true, Ordering::Relaxed);
                    ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                }
            },
            _ => {}
        }
    }

    /// Switches the opening animation on or off, for the next time Big
    /// Picture mode is started.
    fn toggle_splash(&mut self) {
        self.splash_enabled = !self.splash_enabled;
        protocol::send(&Outgoing::SetSplash {
            enabled: self.splash_enabled,
        });

        self.pending_sound = Some(Sound::Toggle);
    }

    /// Switches to the next set of navigation sounds, and lets it be heard.
    fn cycle_sounds(&mut self, forward: bool) {
        let pack = self.sounds.cycle(forward);

        protocol::send(&Outgoing::SetSoundPack { pack });
        self.pending_sound = Some(Sound::Select);
    }

    fn keyboard_action(&mut self, action: Action, row: usize, col: usize) {
        let width = |row: usize| KEY_ROWS[row].chars().count();
        let (mut new_row, mut new_col) = (row, col);

        match action {
            Action::Left => new_col = if col == 0 { width(row) - 1 } else { col - 1 },
            Action::Right => new_col = if col + 1 >= width(row) { 0 } else { col + 1 },
            Action::Up => new_row = row.saturating_sub(1),
            Action::Down => new_row = (row + 1).min(KEY_ROWS.len() - 1),
            Action::Accept => {
                if let Some(key) = KEY_ROWS[row].chars().nth(col) {
                    self.press_key(key);
                }

                return;
            }
            Action::Alt => {
                self.press_key(KEY_BACKSPACE);

                return;
            }
            Action::Search => {
                self.press_key(' ');

                return;
            }
            Action::Back | Action::Menu => {
                self.overlays.pop();

                return;
            }
            _ => {}
        }

        new_col = new_col.min(width(new_row) - 1);

        if let Some(Overlay::Keyboard { row, col }) = self.overlays.last_mut() {
            (*row, *col) = (new_row, new_col);
        }
    }

    fn press_key(&mut self, key: char) {
        match key {
            KEY_BACKSPACE => {
                self.query.pop();
            }
            KEY_CLEAR => self.query.clear(),
            KEY_DONE => {
                self.overlays.pop();
                self.pending_sound = Some(Sound::Back);

                return;
            }
            // No leading or doubled spaces: they would match nothing useful.
            ' ' if self.query.is_empty() || self.query.ends_with(' ') => return,
            other => self.query.push(other),
        }

        self.pending_sound = Some(Sound::Key);
        self.build_view(None);
    }

    /// Whether typing on a real keyboard goes into the search.
    fn typing_searches(&self) -> bool {
        match self.overlays.last() {
            Some(Overlay::Keyboard { .. }) => true,
            Some(_) => false,
            None => self.tab == Tab::Library,
        }
    }

    fn handle_keyboard(&mut self, ctx: &egui::Context) {
        let events = ctx.input(|input| input.events.clone());
        for event in events {
            match event {
                egui::Event::Key {
                    key,
                    pressed: true,
                    repeat,
                    modifiers,
                    ..
                } => {
                    // Holding a key down moves on and on, but accepts once.
                    if repeat && !key_repeats(key) {
                        continue;
                    }

                    self.device = Device::Keyboard;

                    let typing = self.typing_searches();
                    let on_keyboard = matches!(self.overlays.last(), Some(Overlay::Keyboard { .. }));
                    let action = match key {
                        Key::ArrowUp => Some(Action::Up),
                        Key::ArrowDown => Some(Action::Down),
                        Key::ArrowLeft => Some(Action::Left),
                        Key::ArrowRight => Some(Action::Right),
                        // With a real keyboard, Enter finishes the search
                        // rather than pressing an on-screen key.
                        Key::Enter if on_keyboard => Some(Action::Back),
                        Key::Enter => Some(Action::Accept),
                        Key::Space if !typing || self.query.is_empty() => Some(Action::Accept),
                        Key::Escape => Some(Action::Back),
                        Key::Tab if modifiers.shift => Some(Action::TabPrev),
                        Key::Tab => Some(Action::TabNext),
                        Key::PageUp => Some(Action::PageUp),
                        Key::PageDown => Some(Action::PageDown),
                        Key::F10 => Some(Action::Menu),
                        Key::S if modifiers.command => Some(Action::Alt),
                        Key::F if modifiers.command => Some(Action::Search),
                        Key::Q if modifiers.command => {
                            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                            None
                        }
                        Key::F11 => {
                            let fullscreen = ctx.input(|i| i.viewport().fullscreen.unwrap_or(false));

                            ctx.send_viewport_cmd(egui::ViewportCommand::Fullscreen(!fullscreen));
                            None
                        }
                        Key::Backspace if typing && !self.query.is_empty() => {
                            self.sounds.play(Sound::Key);
                            self.query.pop();
                            self.build_view(None);
                            None
                        }
                        _ => None,
                    };

                    if let Some(action) = action {
                        self.handle_action(ctx, action);
                    }
                }
                egui::Event::Text(text) if self.typing_searches() => {
                    let before = self.query.len();

                    for ch in text.chars() {
                        let skip =
                            ch.is_control() || (ch == ' ' && (self.query.is_empty() || self.query.ends_with(' ')));
                        if !skip {
                            self.query.extend(ch.to_lowercase());
                        }
                    }

                    if self.query.len() != before {
                        self.sounds.play(Sound::Key);
                        self.device = Device::Keyboard;
                        self.lib_focus = LibFocus::Grid;
                        self.build_view(None);
                    }
                }
                _ => {}
            }
        }
    }

    fn handle_pointer(&mut self, ctx: &egui::Context) {
        let (pos, moved, clicked, scroll) = ctx.input(|input| {
            (
                input.pointer.hover_pos(),
                input.pointer.delta() != Vec2::ZERO,
                input.pointer.primary_clicked(),
                input.smooth_scroll_delta,
            )
        });

        if moved || clicked {
            self.device = Device::Mouse;
        }

        // During the opening animation a click only ends it, and the
        // pointer has nothing to point at yet.
        if self.splash.as_ref().is_some_and(|splash| splash.blocks_input(self.now)) {
            if clicked {
                self.skips_splash();
            }

            return;
        }

        if scroll != Vec2::ZERO && self.overlays.is_empty() {
            match self.tab {
                Tab::Library => self.lib_target -= scroll.y,
                Tab::Home => {
                    if let Some(target) = self.home_target_x.get_mut(self.home_row) {
                        *target -= scroll.y + scroll.x;
                    }
                }
            }
        }

        let Some(pos) = pos else { return };

        if !moved && !clicked {
            return;
        }

        let hit = self
            .hits
            .iter()
            .rev()
            .find(|(rect, _)| rect.contains(pos))
            .map(|(_, hit)| *hit);
        let Some(hit) = hit else { return };

        // Pointing at something focuses it; clicking then activates it.
        let mut activate = clicked;

        match hit {
            Hit::Block => return,
            Hit::Dismiss => {
                if clicked {
                    self.handle_action(ctx, Action::Back);
                }

                return;
            }
            Hit::Tab(tab) => {
                if clicked && self.tab != tab {
                    self.tab = tab;
                    self.sounds.play(Sound::Tab);
                }

                return;
            }
            Hit::HomeTile(row, col) => {
                if row == self.home_row {
                    self.home_cols[row] = col;
                } else if clicked {
                    // Clicking another row scrolls to it; a second click opens.
                    self.home_row = row;
                    self.home_cols[row] = col;
                    self.home_reveal = true;
                    activate = false;
                } else {
                    return;
                }
            }
            Hit::LibTile(index) => {
                self.lib_focus = LibFocus::Grid;
                self.lib_index = index;
            }
            Hit::Filter(index) => {
                if clicked && index != self.filter {
                    self.sounds.play(Sound::Move);
                    self.filter = index;
                    self.build_view(None);
                }

                return;
            }
            Hit::Button(index) => {
                if let Some(Overlay::Detail { button, .. }) = self.overlays.last_mut() {
                    *button = index;
                }
            }
            Hit::MenuItem(item) => {
                if let Some(Overlay::Menu { index }) = self.overlays.last_mut() {
                    *index = item;
                }
            }
            Hit::Key(key_row, key_col) => {
                if let Some(Overlay::Keyboard { row, col }) = self.overlays.last_mut() {
                    (*row, *col) = (key_row, key_col);
                }
            }
        }

        if activate {
            self.handle_action(ctx, Action::Accept);
        }
    }

    // ------------------------------------------------------------- drawing

    fn draw(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect) {
        let u = (screen.width() / REFERENCE_WIDTH)
            .min(screen.height() / REFERENCE_HEIGHT)
            .max(MIN_UNIT);
        let dt = ctx.input(|input| input.stable_dt).min(MAX_FRAME_SECONDS);

        self.hits.clear();

        self.draw_backdrop(ctx, painter, screen);
        match self.tab {
            Tab::Home => self.draw_home(ctx, painter, screen, u, dt),
            Tab::Library => self.draw_library(ctx, painter, screen, u, dt),
        }

        self.draw_top_bar(painter, screen, u);
        self.draw_footer_fade(painter, screen, u);

        for depth in 0..self.overlays.len() {
            // Everything beneath an overlay is out of the mouse's reach.
            self.hits.clear();
            self.hits.push((screen, Hit::Dismiss));
            match self.overlays[depth].clone() {
                Overlay::Detail { id, button } => self.draw_detail(ctx, painter, screen, u, &id, button),
                Overlay::Menu { index } => self.draw_menu(ctx, painter, screen, u, index),
                Overlay::Keyboard { row, col } => self.draw_keyboard(ctx, painter, screen, u, row, col),
            }
        }

        self.draw_footer(painter, screen, u);
        self.draw_toasts(ctx, painter, screen, u);

        if let Some(splash) = &mut self.splash {
            if !splash.draw(ctx, painter, screen, u, self.now) {
                self.splash = None;
            }
        }
    }

    fn draw_backdrop(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect) {
        let wanted = self.current_game().and_then(|index| self.games[index].cover.clone());
        if wanted != self.backdrop[1] {
            self.backdrop.swap(0, 1);
            self.backdrop[1] = wanted;
            self.backdrop_since = self.now;
        }

        // The fade only starts once the new image is there to fade to.
        let ready = match &self.backdrop[1] {
            Some(path) => self.covers.get(path).is_some(),
            None => true,
        };

        if !ready {
            self.backdrop_since = self.now;
        }

        let fade = (((self.now - self.backdrop_since) / BACKDROP_FADE_SECONDS) as f32).clamp(0.0, 1.0);
        if fade < 1.0 {
            ctx.request_repaint();
        }

        self.backdrop_fade = fade;

        let brightness = if self.tab == Tab::Library {
            LIBRARY_BACKDROP_BRIGHTNESS
        } else {
            BACKDROP_BRIGHTNESS
        };

        self.paint_backdrop(painter, screen, brightness);
    }

    /// Paints the blurred cover of the current game over the whole screen.
    fn paint_backdrop(&mut self, painter: &Painter, screen: Rect, brightness: f32) {
        painter.rect_filled(screen, 0.0, BG);

        let fade = self.backdrop_fade;
        for (slot, alpha) in [(0, 1.0 - fade), (1, fade)] {
            let Some(path) = &self.backdrop[slot] else {
                continue;
            };

            if alpha <= 0.0 {
                continue;
            }

            if let Some(cover) = self.covers.get(path) {
                let tint = draw::with_alpha(Color32::from_gray((f32::from(u8::MAX) * brightness) as u8), alpha);
                let uv = draw::cover_uv(cover.aspect, screen);

                draw::textured_rect(painter, screen, 0.0, cover.blurred.id(), uv, tint);
            }
        }

        // Darken towards the bottom, where the covers are.
        let mut mesh = egui::Mesh::default();
        let top = draw::with_alpha(BG, BACKDROP_SHADE_TOP);
        let bottom = draw::with_alpha(BG, BACKDROP_SHADE_BOTTOM);

        mesh.colored_vertex(screen.left_top(), top);
        mesh.colored_vertex(screen.right_top(), top);
        mesh.colored_vertex(screen.right_bottom(), bottom);
        mesh.colored_vertex(screen.left_bottom(), bottom);
        mesh.add_triangle(0, 1, 2);
        mesh.add_triangle(0, 2, 3);
        painter.add(egui::Shape::mesh(mesh));
    }

    fn draw_top_bar(&mut self, painter: &Painter, screen: Rect, u: f32) {
        // Sizes in units.
        const LOGO_SIZE: f32 = 30.0;

        /// Space between the logo and the tabs, and between two tabs.
        const LOGO_GAP: f32 = 56.0;
        const TAB_GAP: f32 = 44.0;

        /// Space between a bumper's name and the tab next to it.
        const BUMPER_GAP: f32 = 22.0;

        /// The line under the selected tab.
        const UNDERLINE_OFFSET: f32 = 8.0;
        const UNDERLINE_HEIGHT: f32 = 4.0;
        const UNDERLINE_RADIUS: f32 = 2.0;

        /// How far around its name a tab can be clicked.
        const TAB_HIT_MARGIN: f32 = 16.0;

        let y = screen.top() + TOP_BAR_Y * u;
        let mut x = screen.left() + SCREEN_MARGIN * u;
        let logo = draw::text(
            painter,
            pos2(x, y),
            Align2::LEFT_CENTER,
            "LUTRIS",
            draw::bold(LOGO_SIZE * u),
            ACCENT,
        );

        x = logo.right() + LOGO_GAP * u;

        let show_bumpers = self.shows_pad_hints() && self.overlays.is_empty();
        if show_bumpers {
            x = bumper(
                painter,
                pos2(x, y),
                bumper_name(self.pad_style(), PadButton::TabPrev),
                u,
            ) + BUMPER_GAP * u;
        }

        for (tab, label) in [(Tab::Home, "Home"), (Tab::Library, "Library")] {
            let selected = self.tab == tab;
            let color = if selected { TEXT } else { DIM };
            let label = self.t(label).to_owned();
            let rect = draw::text(
                painter,
                pos2(x, y),
                Align2::LEFT_CENTER,
                &label,
                draw::bold(TOP_BAR_TEXT_SIZE * u),
                color,
            );

            if selected {
                let underline = Rect::from_min_size(
                    pos2(rect.left(), rect.bottom() + UNDERLINE_OFFSET * u),
                    vec2(rect.width(), UNDERLINE_HEIGHT * u),
                );

                painter.rect_filled(underline, UNDERLINE_RADIUS * u, ACCENT);
            }

            self.hits.push((rect.expand(TAB_HIT_MARGIN * u), Hit::Tab(tab)));
            x = rect.right() + TAB_GAP * u;
        }

        if show_bumpers {
            // `x` is a tab gap past the last tab; the bumper is closer.
            bumper(
                painter,
                pos2(x - (TAB_GAP - BUMPER_GAP) * u, y),
                bumper_name(self.pad_style(), PadButton::TabNext),
                u,
            );
        }

        self.draw_status(painter, screen, u);
    }

    /// The clock, and what is running, in the top right corner.
    fn draw_status(&self, painter: &Painter, screen: Rect, u: f32) {
        // Sizes in units.

        /// The most room the name of the running game gets.
        const GAME_MAX_WIDTH: f32 = 520.0;

        /// Space between the name of the running game and the clock.
        const GAME_GAP: f32 = 40.0;

        /// The dot before the name: its radius, and its centre's distance
        /// from the name.
        const DOT_RADIUS: f32 = 7.0;
        const DOT_GAP: f32 = 18.0;

        let y = screen.top() + TOP_BAR_Y * u;
        let right = screen.right() - SCREEN_MARGIN * u;
        let clock = draw::text(
            painter,
            pos2(right, y),
            Align2::RIGHT_CENTER,
            &clock_text(),
            draw::regular(TOP_BAR_TEXT_SIZE * u),
            TEXT,
        );

        if let Some(game) = self.games.iter().find(|game| game.state != RunState::Stopped) {
            let width = GAME_MAX_WIDTH * u;
            let galley = draw::fit_text(painter, &game.name, draw::regular(BODY_TEXT_SIZE * u), GOOD, width, 1);
            let pos = pos2(clock.left() - GAME_GAP * u - galley.size().x, y - galley.size().y / 2.0);

            painter.circle_filled(pos2(pos.x - DOT_GAP * u, y), DOT_RADIUS * u, GOOD);
            painter.galley(pos, galley, GOOD);
        }
    }

    /// Fades whatever scrolls beneath the button hints into the background.
    fn draw_footer_fade(&self, painter: &Painter, screen: Rect, u: f32) {
        /// Where the fade begins and where it is complete, in units above
        /// the bottom of the screen.
        const FADE_START: f32 = 190.0;
        const FADE_END: f32 = 90.0;

        let top = screen.bottom() - FADE_START * u;
        let middle = screen.bottom() - FADE_END * u;
        let mut mesh = egui::Mesh::default();

        for (y, color) in [(top, Color32::TRANSPARENT), (middle, BG), (screen.bottom(), BG)] {
            mesh.colored_vertex(pos2(screen.left(), y), color);
            mesh.colored_vertex(pos2(screen.right(), y), color);
        }

        mesh.add_triangle(0, 1, 3);
        mesh.add_triangle(0, 3, 2);
        mesh.add_triangle(2, 3, 5);
        mesh.add_triangle(2, 5, 4);
        painter.add(egui::Shape::mesh(mesh));
    }

    fn draw_footer(&mut self, painter: &Painter, screen: Rect, u: f32) {
        /// The centre line of the hints, in units above the bottom of the
        /// screen, and the space between two hints.
        const HINTS_Y: f32 = 48.0;
        const HINT_GAP: f32 = 36.0;

        let pad = self.shows_pad_hints();
        let style = self.pad_style();
        let glyph = |button: PadButton, key: &'static str| if pad { style.glyph(button) } else { Glyph::Text(key) };
        let mut hints: Vec<(Glyph, &str)> = Vec::new();

        match self.overlays.last() {
            Some(Overlay::Keyboard { .. }) => {
                hints.push((glyph(PadButton::Accept, "Enter"), if pad { "Select" } else { "Done" }));

                if pad {
                    hints.push((style.glyph(PadButton::Alt), "Delete"));
                    hints.push((style.glyph(PadButton::Search), "Space"));
                    hints.push((style.glyph(PadButton::Back), "Done"));
                }
            }
            Some(_) => {
                hints.push((glyph(PadButton::Accept, "Enter"), "Select"));
                hints.push((glyph(PadButton::Back, "Esc"), "Back"));
            }
            None => {
                hints.push((glyph(PadButton::Accept, "Enter"), "Select"));

                if self.tab == Tab::Library {
                    hints.push((glyph(PadButton::Back, "Esc"), "Back"));
                    hints.push((glyph(PadButton::Alt, "Ctrl+S"), "Sort"));
                }

                if pad {
                    hints.push((style.glyph(PadButton::Search), "Search"));
                } else if self.tab == Tab::Library {
                    hints.push((Glyph::Text("A-Z"), "Search"));
                } else {
                    hints.push((Glyph::Text("Tab"), "Library"));
                }

                hints.push((glyph(PadButton::Menu, "F10"), "Menu"));
            }
        }

        let y = screen.bottom() - HINTS_Y * u;
        let mut x = screen.right() - SCREEN_MARGIN * u;

        for (glyph, label) in hints.into_iter().rev() {
            // Keys have names in other languages too; buttons are left as they are.
            let glyph = match glyph {
                Glyph::Text(name) => Glyph::Text(self.t(name)),
                symbol => symbol,
            };

            x = draw::hint(painter, pos2(x, y), glyph, self.t(label), u) - HINT_GAP * u;
        }
    }

    fn draw_home(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, dt: f32) {
        // Sizes in units; positions ending in _Y are below the top of the screen.

        /// The name of the focused game.
        const TITLE_SIZE: f32 = 64.0;
        const TITLE_Y: f32 = 128.0;

        /// The line of facts under it: runner, platform and year.
        const FACTS_SIZE: f32 = 26.0;
        const FACTS_Y: f32 = 236.0;

        /// The line under that: whether it runs, and how much it was played.
        const STATS_Y: f32 = 284.0;

        /// Space after the state, between a label and its value, and after
        /// a value.
        const STATE_GAP: f32 = 36.0;
        const STAT_LABEL_GAP: f32 = 12.0;
        const STAT_GAP: f32 = 44.0;

        /// A cover in a row, and the space between two of them.
        const TILE: Vec2 = vec2(228.0, 304.0);
        const TILE_GAP: f32 = 26.0;

        /// Where the first row begins.
        const ROWS_Y: f32 = 372.0;

        /// Room above the rows that scrolling rows may still be seen in.
        const ROWS_HEADROOM: f32 = 14.0;

        /// Height of a row beyond its tiles: its title, and space below.
        const ROW_EXTRA_HEIGHT: f32 = 96.0;

        /// The centre line of a row's title and the top of its tiles, below
        /// the top of the row.
        const ROW_TITLE_Y: f32 = 14.0;
        const ROW_TILES_Y: f32 = 48.0;

        let margin = SCREEN_MARGIN * u;
        let left = screen.left() + margin;

        if self.rows.is_empty() {
            self.draw_empty(painter, screen, u);

            return;
        }

        // The focused game, large, above the rows.
        if let Some(index) = self.home_game() {
            let game = &self.games[index];
            let title = draw::fit_text(
                painter,
                &game.name,
                draw::bold(TITLE_SIZE * u),
                TEXT,
                screen.width() - 2.0 * margin,
                1,
            );

            painter.galley(pos2(left, screen.top() + TITLE_Y * u), title, TEXT);

            let facts: Vec<&str> = [game.runner.as_str(), game.platform.as_str()]
                .into_iter()
                .filter(|fact| !fact.is_empty())
                .collect();
            let mut line = facts.join("  ·  ");

            if let Some(year) = game.year {
                line = format!("{line}  ·  {year}");
            }

            draw::text(
                painter,
                pos2(left, screen.top() + FACTS_Y * u),
                Align2::LEFT_CENTER,
                &line,
                draw::regular(FACTS_SIZE * u),
                DIM,
            );

            let mut x = left;
            let y = screen.top() + STATS_Y * u;

            if game.state != RunState::Stopped {
                let label = if game.state == RunState::Running {
                    "Running"
                } else {
                    "Launching…"
                };

                let rect = draw::text(
                    painter,
                    pos2(x, y),
                    Align2::LEFT_CENTER,
                    self.t(label),
                    draw::bold(BODY_TEXT_SIZE * u),
                    GOOD,
                );

                x = rect.right() + STATE_GAP * u;
            }

            for (label, value) in [
                ("Play time", &game.playtime_text),
                ("Last played", &game.lastplayed_text),
            ] {
                if value.is_empty() {
                    continue;
                }

                let rect = draw::text(
                    painter,
                    pos2(x, y),
                    Align2::LEFT_CENTER,
                    self.t(label),
                    draw::regular(BODY_TEXT_SIZE * u),
                    DIM,
                );
                let rect = draw::text(
                    painter,
                    pos2(rect.right() + STAT_LABEL_GAP * u, y),
                    Align2::LEFT_CENTER,
                    value,
                    draw::regular(BODY_TEXT_SIZE * u),
                    TEXT,
                );

                x = rect.right() + STAT_GAP * u;
            }
        }

        // The rows scroll beneath the header, the focused one at the top.
        let tile = TILE * u;
        let gap = TILE_GAP * u;
        let pitch = tile.y + ROW_EXTRA_HEIGHT * u;
        let rows_top = screen.top() + ROWS_Y * u;
        let target_y = self.home_row as f32 * pitch;

        self.home_scroll_y = approach(ctx, self.home_scroll_y, target_y, dt);

        let clip = Rect::from_min_max(pos2(screen.left(), rows_top - ROWS_HEADROOM * u), screen.right_bottom());
        let clipped = painter.with_clip_rect(clip);
        let visible_width = screen.width() - 2.0 * margin;

        for row_index in 0..self.rows.len() {
            let y = rows_top + row_index as f32 * pitch - self.home_scroll_y;
            if y > screen.bottom() || y + pitch < clip.top() {
                continue;
            }

            let focused_row = row_index == self.home_row;
            let title_color = if focused_row { TEXT } else { DIM };

            draw::text(
                &clipped,
                pos2(left, y + ROW_TITLE_Y * u),
                Align2::LEFT_CENTER,
                self.t(self.rows[row_index].title),
                draw::bold(BODY_TEXT_SIZE * u),
                title_color,
            );

            let count = self.rows[row_index].items.len();
            let col = self.home_cols[row_index];
            let step = tile.x + gap;
            let max_scroll = (count as f32 * step - gap - visible_width).max(0.0);
            let mut target = self.home_target_x[row_index];

            if focused_row && self.home_reveal {
                let tile_left = col as f32 * step;

                target = target.min(tile_left).max(tile_left + tile.x - visible_width);
            }

            target = target.clamp(0.0, max_scroll);
            self.home_target_x[row_index] = target;

            let scroll = approach(ctx, self.home_scroll_x[row_index], target, dt);

            self.home_scroll_x[row_index] = scroll;

            let tiles_top = y + ROW_TILES_Y * u;
            let first = ((scroll - margin) / step).floor().max(0.0) as usize;
            for item in first..count {
                let x = left + item as f32 * step - scroll;
                if x > screen.right() {
                    break;
                }

                let rect = Rect::from_min_size(pos2(x, tiles_top), tile);
                let focused = focused_row && item == col && self.overlays.is_empty();
                let focus =
                    ctx.animate_bool_with_time(Id::unique(("home", row_index, item)), focused, TILE_FOCUS_SECONDS);
                let game = &self.games[self.rows[row_index].items[item]];

                // The focused tile is drawn last so it overlaps its neighbours.
                if !focused {
                    draw::game_tile(&clipped, &mut self.covers, game, rect, focus, u);
                }

                if rect.intersects(clip) {
                    self.hits.push((rect.intersect(clip), Hit::HomeTile(row_index, item)));
                }
            }

            if focused_row && self.overlays.is_empty() {
                let x = left + col as f32 * step - scroll;
                let rect = Rect::from_min_size(pos2(x, tiles_top), tile);
                let focus = ctx.animate_bool_with_time(Id::unique(("home", row_index, col)), true, TILE_FOCUS_SECONDS);
                let game = &self.games[self.rows[row_index].items[col]];

                draw::game_tile(&clipped, &mut self.covers, game, rect, focus, u);
            }
        }

        self.home_reveal = false;
    }

    fn draw_empty(&self, painter: &Painter, screen: Rect, u: f32) {
        // Sizes in units.
        const TITLE_SIZE: f32 = 40.0;
        const DETAIL_SIZE: f32 = 26.0;

        /// How far the detail is below the title.
        const DETAIL_OFFSET: f32 = 60.0;

        /// Where the message goes while the on-screen keyboard is open,
        /// below the top of the screen.
        const SEARCHING_Y: f32 = 380.0;

        let (title, detail) = if !self.got_library {
            ("Loading library…", "")
        } else if self.games.is_empty() {
            ("Your library is empty", "Install games in Lutris to see them here.")
        } else {
            ("No games found", "")
        };

        // Stay clear of the on-screen keyboard.
        let searching = matches!(self.overlays.last(), Some(Overlay::Keyboard { .. }));
        let center = if searching {
            pos2(screen.center().x, screen.top() + SEARCHING_Y * u)
        } else {
            screen.center()
        };

        draw::text(
            painter,
            center,
            Align2::CENTER_CENTER,
            self.t(title),
            draw::bold(TITLE_SIZE * u),
            TEXT,
        );

        if !detail.is_empty() {
            draw::text(
                painter,
                center + vec2(0.0, DETAIL_OFFSET * u),
                Align2::CENTER_CENTER,
                self.t(detail),
                draw::regular(DETAIL_SIZE * u),
                DIM,
            );
        }
    }

    fn draw_library(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, dt: f32) {
        // Sizes in units.

        /// The centre line of the row of filters, below the top of the
        /// screen, and the size of its text.
        const CHIPS_Y: f32 = 142.0;
        const CHIPS_TEXT_SIZE: f32 = 22.0;

        /// A filter chip: its height, the space on either side of its
        /// text, and the space between two chips.
        const CHIP_HEIGHT: f32 = 50.0;
        const CHIP_PADDING: f32 = 22.0;
        const CHIP_GAP: f32 = 14.0;

        /// How solid a chip is that is not selected (0 to 1).
        const CHIP_ALPHA: f32 = 0.85;

        /// Space kept free between the filters and the summary.
        const SUMMARY_GAP: f32 = 32.0;

        /// Room kept right of the selected filter when scrolling to it.
        const CHIPS_SCROLL_MARGIN: f32 = 24.0;

        /// A cover in the grid, and the least space between two of them.
        const TILE: Vec2 = vec2(216.0, 288.0);
        const TILE_MIN_GAP: f32 = 26.0;

        /// Height of a row of the grid beyond its tiles: the name, and
        /// space below.
        const ROW_EXTRA_HEIGHT: f32 = 72.0;

        /// Where the grid begins, below the top of the screen, and where it
        /// ends, above the bottom.
        const GRID_TOP: f32 = 214.0;
        const GRID_BOTTOM: f32 = 92.0;

        /// Room above the grid that a focused, grown tile may still use.
        const GRID_HEADROOM: f32 = 18.0;

        /// The name under a cover, and how far under.
        const NAME_SIZE: f32 = 20.0;
        const NAME_OFFSET: f32 = 16.0;

        /// The scroll marker: its edges, left of the screen's right edge,
        /// its corner radius, and the least height of its thumb.
        const SCROLLBAR_LEFT: f32 = 30.0;
        const SCROLLBAR_RIGHT: f32 = 24.0;
        const SCROLLBAR_RADIUS: f32 = 3.0;
        const THUMB_MIN_HEIGHT: f32 = 40.0;

        /// How solid the track of the scroll marker is (0 to 1).
        const TRACK_ALPHA: f32 = 0.5;

        let margin = SCREEN_MARGIN * u;
        let left = screen.left() + margin;
        let right = screen.right() - margin;
        let chips_y = screen.top() + CHIPS_Y * u;
        let interactive = self.overlays.is_empty();

        // Right of the filters: how many games, and their order.
        let sort = match self.sort {
            Sort::Name => "Sorted by name",
            Sort::Recent => "Sorted by last played",
            Sort::Playtime => "Sorted by play time",
        };

        let summary = format!(
            "{}  ·  {}",
            self.t("Games: %d").replace("%d", &self.view.len().to_string()),
            self.t(sort)
        );
        let summary = draw::text(
            painter,
            pos2(right, chips_y),
            Align2::RIGHT_CENTER,
            &summary,
            draw::regular(CHIPS_TEXT_SIZE * u),
            DIM,
        );

        // The search, then the filters.
        let chip_height = CHIP_HEIGHT * u;
        let chips_clip = Rect::from_min_max(
            pos2(screen.left(), chips_y - chip_height),
            pos2(summary.left() - SUMMARY_GAP * u, chips_y + chip_height),
        );
        let chips = painter.with_clip_rect(chips_clip);
        let mut x = left - self.filter_scroll;
        let searching = matches!(self.overlays.last(), Some(Overlay::Keyboard { .. }));
        if searching || !self.query.is_empty() {
            let label = format!("{}: {}", self.t("Search"), self.query);
            let galley = chips.layout_no_wrap(label, draw::bold(CHIPS_TEXT_SIZE * u), BG);
            let rect = Rect::from_min_size(
                pos2(x, chips_y - chip_height / 2.0),
                vec2(galley.size().x + 2.0 * CHIP_PADDING * u, chip_height),
            );

            chips.rect_filled(rect, chip_height / 2.0, ACCENT);
            chips.galley(
                pos2(rect.left() + CHIP_PADDING * u, chips_y - galley.size().y / 2.0),
                galley,
                BG,
            );
            x = rect.right() + CHIP_GAP * u;
        }

        let mut selected_span = (0.0, 0.0);

        for index in 0..self.filters.len() {
            let label = match &self.filters[index] {
                Filter::All => self.t("All games").to_owned(),
                Filter::Favorites => self.t("Favorites").to_owned(),
                Filter::Category(name) | Filter::Runner(name) => name.clone(),
            };

            let selected = index == self.filter;
            let focused = selected && self.lib_focus == LibFocus::Filters && interactive;
            let (fill, color) = if selected {
                (TEXT, BG)
            } else {
                (draw::with_alpha(PANEL_HI, CHIP_ALPHA), TEXT)
            };

            let galley = chips.layout_no_wrap(label, draw::regular(CHIPS_TEXT_SIZE * u), color);
            let rect = Rect::from_min_size(
                pos2(x, chips_y - chip_height / 2.0),
                vec2(galley.size().x + 2.0 * CHIP_PADDING * u, chip_height),
            );

            chips.rect_filled(rect, chip_height / 2.0, fill);
            chips.galley(
                pos2(rect.left() + CHIP_PADDING * u, chips_y - galley.size().y / 2.0),
                galley,
                color,
            );

            if focused {
                chips.rect_stroke(
                    rect.expand(draw::FOCUS_RING_GAP * u),
                    chip_height / 2.0 + draw::FOCUS_RING_GAP * u,
                    Stroke::new(draw::FOCUS_RING_WIDTH * u, ACCENT),
                    StrokeKind::Outside,
                );
            }

            if selected {
                selected_span = (rect.left() + self.filter_scroll, rect.right() + self.filter_scroll);
            }

            if rect.intersects(chips_clip) {
                self.hits.push((rect.intersect(chips_clip), Hit::Filter(index)));
            }

            x = rect.right() + CHIP_GAP * u;
        }

        // Keep the selected filter in view.
        let room = chips_clip.right() - CHIPS_SCROLL_MARGIN * u;
        let mut filter_target = self.filter_scroll;

        filter_target = filter_target.max(selected_span.1 - room).min(selected_span.0 - left);
        self.filter_scroll = approach(ctx, self.filter_scroll, filter_target.max(0.0), dt);

        if self.view.is_empty() {
            self.draw_empty(painter, screen, u);

            return;
        }

        // The grid: as many columns as fit, spread over the full width.
        let tile = TILE * u;
        let min_gap = TILE_MIN_GAP * u;
        let width = right - left;
        let cols = (((width + min_gap) / (tile.x + min_gap)).floor() as usize).max(1);
        let gap = if cols > 1 {
            (width - cols as f32 * tile.x) / (cols - 1) as f32
        } else {
            0.0
        };

        let pitch = tile.y + ROW_EXTRA_HEIGHT * u;
        let top = screen.top() + GRID_TOP * u;
        let bottom = screen.bottom() - GRID_BOTTOM * u;
        let height = bottom - top;
        let rows = self.view.len().div_ceil(cols);

        if cols != self.lib_cols {
            self.lib_cols = cols;
            self.lib_reveal = true;
        }

        self.lib_rows_visible = ((height / pitch).floor() as usize).max(1);

        if self.lib_reveal {
            // Scroll by whole rows, so no row is left cut in half.
            let row = self.lib_index / cols;
            let first = (self.lib_target / pitch).round() as usize;
            let first = first.min(row).max((row + 1).saturating_sub(self.lib_rows_visible));

            self.lib_target = first as f32 * pitch;
            self.lib_reveal = false;
        }

        let max_scroll = (rows as f32 * pitch - height).max(0.0);

        self.lib_target = self.lib_target.clamp(0.0, max_scroll);
        self.lib_scroll = approach(ctx, self.lib_scroll, self.lib_target, dt);

        let clip = Rect::from_min_max(
            pos2(screen.left(), top - GRID_HEADROOM * u),
            pos2(screen.right(), bottom),
        );
        let clipped = painter.with_clip_rect(clip);
        let first_row = (self.lib_scroll / pitch).floor().max(0.0) as usize;
        let last_row = (((self.lib_scroll + height) / pitch).ceil() as usize).min(rows);
        let grid_focused = self.lib_focus == LibFocus::Grid && interactive;
        let mut focused_tile = None;

        for row in first_row..last_row {
            for col in 0..cols {
                let index = row * cols + col;
                let Some(&game_index) = self.view.get(index) else {
                    break;
                };

                let rect = Rect::from_min_size(
                    pos2(
                        left + col as f32 * (tile.x + gap),
                        top + row as f32 * pitch - self.lib_scroll,
                    ),
                    tile,
                );
                let game = &self.games[game_index];
                let focused = grid_focused && index == self.lib_index;
                let focus = ctx.animate_bool_with_time(Id::unique(("lib", game_index)), focused, TILE_FOCUS_SECONDS);

                if focused {
                    focused_tile = Some((rect, game_index, focus));
                } else {
                    draw::game_tile(&clipped, &mut self.covers, game, rect, focus, u);
                }

                let name = draw::fit_text(&clipped, &game.name, draw::regular(NAME_SIZE * u), DIM, tile.x, 1);
                let name_pos = pos2(rect.center().x - name.size().x / 2.0, rect.bottom() + NAME_OFFSET * u);
                let color = if focused { TEXT } else { DIM };

                clipped.galley_with_override_text_color(name_pos, name, color);

                if rect.intersects(clip) {
                    self.hits.push((rect.intersect(clip), Hit::LibTile(index)));
                }
            }
        }

        if let Some((rect, game_index, focus)) = focused_tile {
            draw::game_tile(&clipped, &mut self.covers, &self.games[game_index], rect, focus, u);
        }

        // A scroll position marker, when there is something to scroll.
        if max_scroll > 0.0 {
            let track = Rect::from_min_max(
                pos2(screen.right() - SCROLLBAR_LEFT * u, top),
                pos2(screen.right() - SCROLLBAR_RIGHT * u, bottom),
            );
            let thumb_height = (height / (rows as f32 * pitch) * height).max(THUMB_MIN_HEIGHT * u);
            let thumb_top = top + (height - thumb_height) * (self.lib_scroll / max_scroll).clamp(0.0, 1.0);

            painter.rect_filled(track, SCROLLBAR_RADIUS * u, draw::with_alpha(PANEL_HI, TRACK_ALPHA));
            painter.rect_filled(
                Rect::from_min_size(pos2(track.left(), thumb_top), vec2(track.width(), thumb_height)),
                SCROLLBAR_RADIUS * u,
                DIM,
            );
        }
    }

    fn draw_detail(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, id: &str, button: usize) {
        // Sizes in units.

        /// Space kept free at the left and right edges of the page.
        const PAGE_MARGIN: f32 = 170.0;

        /// The cover: how far below the top of the screen, and its size.
        const COVER_Y: f32 = 190.0;
        const COVER: Vec2 = vec2(465.0, 620.0);

        /// Space between the cover and the text beside it.
        const COLUMN_GAP: f32 = 80.0;

        /// The game's name: its size, how many rows it may take, and the
        /// space below it.
        const TITLE_SIZE: f32 = 56.0;
        const TITLE_ROWS: usize = 2;
        const TITLE_GAP: f32 = 34.0;

        /// The facts: where their values begin, right of their labels'
        /// left edge, and the height of a line.
        const FACT_VALUE_X: f32 = 230.0;
        const FACT_LINE_HEIGHT: f32 = 46.0;

        /// How far the state of a running game is above the buttons.
        const STATUS_OFFSET: f32 = 58.0;

        /// The buttons, which end level with the cover.
        const BUTTON_HEIGHT: f32 = 84.0;
        const BUTTON_GAP: f32 = 28.0;
        const PLAY_WIDTH: f32 = 300.0;
        const FAVORITE_MAX_WIDTH: f32 = 440.0;

        let Some(index) = self.game_index(id) else {
            return;
        };

        // A page of its own, over everything else.
        self.paint_backdrop(painter, screen, BACKDROP_BRIGHTNESS);
        self.hits.push((screen, Hit::Block));
        self.draw_status(painter, screen, u);

        let top_overlay = matches!(self.overlays.last(), Some(Overlay::Detail { .. }));
        let game = &self.games[index];

        let cover_rect = Rect::from_min_size(
            pos2(screen.left() + PAGE_MARGIN * u, screen.top() + COVER_Y * u),
            COVER * u,
        );

        draw::game_tile(painter, &mut self.covers, game, cover_rect, 0.0, u);

        let x = cover_rect.right() + COLUMN_GAP * u;
        let width = screen.right() - PAGE_MARGIN * u - x;
        let title = draw::fit_text(painter, &game.name, draw::bold(TITLE_SIZE * u), TEXT, width, TITLE_ROWS);
        let mut y = cover_rect.top();
        let title_height = title.size().y;

        painter.galley(pos2(x, y), title, TEXT);
        y += title_height + TITLE_GAP * u;

        let year = game.year.map(|year| year.to_string()).unwrap_or_default();
        let facts = [
            ("Runner", game.runner.as_str()),
            ("Platform", game.platform.as_str()),
            ("Year", year.as_str()),
            ("Play time", game.playtime_text.as_str()),
            ("Last played", game.lastplayed_text.as_str()),
        ];
        for (label, value) in facts {
            if value.is_empty() {
                continue;
            }

            draw::text(
                painter,
                pos2(x, y),
                Align2::LEFT_TOP,
                self.t(label),
                draw::regular(BODY_TEXT_SIZE * u),
                DIM,
            );

            let value_width = width - FACT_VALUE_X * u;
            let value = draw::fit_text(painter, value, draw::regular(BODY_TEXT_SIZE * u), TEXT, value_width, 1);

            painter.galley(pos2(x + FACT_VALUE_X * u, y), value, TEXT);
            y += FACT_LINE_HEIGHT * u;
        }

        let buttons_top = cover_rect.bottom() - BUTTON_HEIGHT * u;

        if game.state != RunState::Stopped {
            let mut status = self
                .t(if game.state == RunState::Running {
                    "Running"
                } else {
                    "Launching…"
                })
                .to_owned();
            if let Some(detail) = self.statuses.get(id) {
                status = format!("{status}  {detail}");
            }

            let status = draw::fit_text(painter, &status, draw::regular(BODY_TEXT_SIZE * u), GOOD, width, 1);

            painter.galley(pos2(x, buttons_top - STATUS_OFFSET * u), status, GOOD);
        }

        let stopped = game.state == RunState::Stopped;
        let favorite = game.favorite;
        let play_label = self.t(if stopped { "Play" } else { "Stop" }).to_owned();
        let favorite_label = self
            .t(if favorite {
                "Remove from favorites"
            } else {
                "Add to favorites"
            })
            .to_owned();
        let play_rect = Rect::from_min_size(pos2(x, buttons_top), vec2(PLAY_WIDTH * u, BUTTON_HEIGHT * u));
        // The second button gets what room the first one leaves, if that is less.
        let favorite_width = (FAVORITE_MAX_WIDTH * u).min(width - (PLAY_WIDTH + BUTTON_GAP) * u);
        let favorite_rect = Rect::from_min_size(
            pos2(play_rect.right() + BUTTON_GAP * u, buttons_top),
            vec2(favorite_width, BUTTON_HEIGHT * u),
        );
        let buttons = [
            (
                play_rect,
                play_label,
                if stopped { ACCENT } else { PANEL_HI },
                if stopped { BG } else { TEXT },
            ),
            (favorite_rect, favorite_label, PANEL_HI, TEXT),
        ];
        for (i, (rect, label, fill, color)) in buttons.into_iter().enumerate() {
            let focused = top_overlay && button == i;
            let focus = ctx.animate_bool_with_time(Id::unique(("detail", i)), focused, BUTTON_FOCUS_SECONDS);

            draw::button(painter, rect, &label, fill, color, focus, u);
            self.hits.push((rect, Hit::Button(i)));
        }
    }

    fn draw_menu(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, index: usize) {
        // Sizes in units.

        /// How much the screen behind the menu is darkened (0 to 1).
        const SCRIM_ALPHA: f32 = 0.6;
        const WIDTH: f32 = 600.0;

        /// Space between the panel's edge and the entries.
        const PADDING: f32 = 28.0;

        /// The height an entry takes up, of which this much is the space
        /// to the next one.
        const ITEM_HEIGHT: f32 = 84.0;
        const ITEM_GAP: f32 = 10.0;

        painter.rect_filled(screen, 0.0, draw::with_alpha(Color32::BLACK, SCRIM_ALPHA));

        let sounds = format!("{}: {}", self.t("Sounds"), self.t(&self.sounds.current().name));
        let items = [
            self.t("Resume").to_owned(),
            sounds,
            format!(
                "{}: {}",
                self.t("Start animation"),
                self.t(if self.splash_enabled { "On" } else { "Off" })
            ),
            self.t("Exit Big Picture").to_owned(),
            self.t("Quit Lutris").to_owned(),
        ];
        let item_height = ITEM_HEIGHT * u;
        let padding = PADDING * u;
        let size = vec2(WIDTH * u, items.len() as f32 * item_height + 2.0 * padding);
        let panel = Rect::from_center_size(screen.center(), size);

        painter.rect_filled(panel, PANEL_RADIUS * u, PANEL);
        self.hits.push((panel, Hit::Block));

        for (i, label) in items.into_iter().enumerate() {
            let rect = Rect::from_min_size(
                pos2(panel.left() + padding, panel.top() + padding + i as f32 * item_height),
                vec2(size.x - 2.0 * padding, item_height - ITEM_GAP * u),
            );
            let focus = ctx.animate_bool_with_time(Id::unique(("menu", i)), i == index, BUTTON_FOCUS_SECONDS);
            let fill = if i == index { PANEL_HI } else { PANEL };

            draw::button(painter, rect, &label, fill, TEXT, focus, u);
            self.hits.push((rect, Hit::MenuItem(i)));
        }
    }

    fn draw_keyboard(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, row: usize, col: usize) {
        // Sizes in units.

        /// A key, and the space between two of them.
        const KEY: Vec2 = vec2(104.0, 76.0);
        const KEY_GAP: f32 = 10.0;
        const KEY_RADIUS: f32 = 10.0;

        /// Keys in the longest row, which the panel is as wide as.
        const KEYS_PER_ROW: f32 = 10.0;

        /// Space between the panel's edge and the keys.
        const PADDING: f32 = 30.0;

        /// Space between the panel and the bottom of the screen.
        const BOTTOM_MARGIN: f32 = 96.0;

        /// How solid the panel is (0 to 1).
        const PANEL_ALPHA: f32 = 0.97;

        /// How much of its size a key gains when focused.
        const FOCUS_GROWTH: f32 = 0.05;

        /// Size of a key's text: a single character, or a word.
        const CHAR_SIZE: f32 = 28.0;
        const WORD_SIZE: f32 = 18.0;

        /// How much narrower than the key its text has to be.
        const LABEL_MARGIN: f32 = 8.0;

        let key = KEY * u;
        let gap = KEY_GAP * u;
        let padding = PADDING * u;
        let size = vec2(
            KEYS_PER_ROW * key.x + (KEYS_PER_ROW - 1.0) * gap + 2.0 * padding,
            KEY_ROWS.len() as f32 * (key.y + gap) - gap + 2.0 * padding,
        );
        let panel = Rect::from_min_size(
            pos2(
                screen.center().x - size.x / 2.0,
                screen.bottom() - BOTTOM_MARGIN * u - size.y,
            ),
            size,
        );

        painter.rect_filled(panel, PANEL_RADIUS * u, draw::with_alpha(PANEL, PANEL_ALPHA));
        self.hits.push((panel, Hit::Block));

        for (r, keys) in KEY_ROWS.iter().enumerate() {
            for (c, ch) in keys.chars().enumerate() {
                let rect = Rect::from_min_size(
                    pos2(
                        panel.left() + padding + c as f32 * (key.x + gap),
                        panel.top() + padding + r as f32 * (key.y + gap),
                    ),
                    key,
                );
                let focused = r == row && c == col;
                let focus = ctx.animate_bool_with_time(Id::unique(("key", r, c)), focused, KEY_FOCUS_SECONDS);
                let label = match ch {
                    ' ' => self.t("Space").to_owned(),
                    KEY_BACKSPACE => self.t("Delete").to_owned(),
                    KEY_CLEAR => self.t("Clear").to_owned(),
                    KEY_DONE => self.t("Done").to_owned(),
                    other => other.to_uppercase().collect(),
                };

                let (fill, color) = match ch {
                    KEY_DONE => (ACCENT, BG),
                    _ if focused => (TEXT, BG),
                    _ => (PANEL_HI, TEXT),
                };

                let rect_drawn = Rect::from_center_size(rect.center(), rect.size() * (1.0 + FOCUS_GROWTH * focus));

                painter.rect_filled(rect_drawn, KEY_RADIUS * u, fill);

                let size = if label.chars().count() > 1 {
                    WORD_SIZE
                } else {
                    CHAR_SIZE
                };

                let width = key.x - LABEL_MARGIN * u;
                let galley = draw::fit_text(painter, &label, draw::bold(size * u), color, width, 1);

                painter.galley(rect_drawn.center() - galley.size() / 2.0, galley, color);
                draw::focus_ring(painter, rect_drawn, KEY_RADIUS * u, u, focus);
                self.hits.push((rect, Hit::Key(r, c)));
            }
        }
    }

    fn draw_toasts(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32) {
        // Sizes in units.

        /// How many messages are shown at once, the newest lowest.
        const MAX_SHOWN: usize = 3;

        /// Space between the lowest message and the bottom of the screen.
        const BOTTOM_MARGIN: f32 = 110.0;

        /// The most room a message's text gets: its width and its rows.
        const MAX_WIDTH: f32 = 1100.0;
        const MAX_ROWS: usize = 3;

        /// Space around the text, sideways and above and below.
        const PADDING_X: f32 = 28.0;
        const PADDING_Y: f32 = 18.0;
        const RADIUS: f32 = 16.0;

        /// Space between two messages.
        const GAP: f32 = 14.0;

        /// A message is cleared this long after its time is up, in
        /// seconds, to be sure it is.
        const EXPIRY_SLACK: f32 = 0.05;

        self.toasts.retain(|toast| toast.until > self.now);

        let mut bottom = screen.bottom() - BOTTOM_MARGIN * u;

        for toast in self.toasts.iter().rev().take(MAX_SHOWN) {
            let font = draw::regular(BODY_TEXT_SIZE * u);
            let galley = draw::fit_text(painter, &toast.text, font, TEXT, MAX_WIDTH * u, MAX_ROWS);
            let size = galley.size() + vec2(2.0 * PADDING_X * u, 2.0 * PADDING_Y * u);
            let rect = Rect::from_min_size(pos2(screen.center().x - size.x / 2.0, bottom - size.y), size);

            painter.rect_filled(rect, RADIUS * u, draw::BAD);
            painter.galley(rect.min + vec2(PADDING_X * u, PADDING_Y * u), galley, TEXT);
            bottom = rect.top() - GAP * u;
        }

        if let Some(next) = self.toasts.iter().map(|toast| toast.until).reduce(f64::min) {
            ctx.request_repaint_after_secs((next - self.now).max(0.0) as f32 + EXPIRY_SLACK);
        }
    }
}

impl eframe::App for App {
    /// Runs before every frame, and also while the window is hidden behind a
    /// game - which is when most of the news from Lutris arrives.
    fn logic(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.now = ctx.input(|input| input.time);

        while let Ok(message) = self.incoming.try_recv() {
            self.handle_message(ctx, message);
        }

        // A controller is read whether or not we have the focus, so anything
        // pressed while a game is in front must not reach this interface.
        let focused = ctx.input(|input| input.focused);
        if focused && !self.was_focused {
            self.focused_at = self.now;
        }

        self.was_focused = focused;

        let accept = focused && self.now - self.focused_at >= FOCUS_GRACE;

        while let Ok(action) = self.pad.try_recv() {
            if accept {
                self.device = Device::Pad;
                self.handle_action(ctx, action);
            }
        }
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        self.covers.begin_frame();
        self.handle_keyboard(&ctx);
        self.handle_pointer(&ctx);

        let screen = ctx.content_rect();
        let painter = ui.painter().clone();

        self.draw(&ctx, &painter, screen);

        if self.device != Device::Mouse {
            ctx.set_cursor_icon(egui::CursorIcon::None);
        }

        // Keep the clock right without animating anything.
        ctx.request_repaint_after_secs(seconds_to_next_minute());
    }
}

/// Whether holding a key down repeats what it does: moving about does, and
/// so does deleting; accepting, going back and the rest do not.
fn key_repeats(key: Key) -> bool {
    matches!(
        key,
        Key::ArrowUp | Key::ArrowDown | Key::ArrowLeft | Key::ArrowRight | Key::PageUp | Key::PageDown | Key::Backspace
    )
}

/// Moves `current` towards `target` with an ease-out, asking for another
/// frame until it gets there.
fn approach(ctx: &egui::Context, current: f32, target: f32, dt: f32) -> f32 {
    let distance = target - current;
    if distance.abs() < APPROACH_SNAP {
        return target;
    }

    ctx.request_repaint();

    current + distance * (1.0 - (-dt * APPROACH_RATE).exp())
}

/// The key games are sorted by: Lutris's sort name where there is one,
/// compared without regard to case.
fn sort_key(game: &Game) -> String {
    let name = if game.sortname.is_empty() {
        &game.name
    } else {
        &game.sortname
    };

    name.to_lowercase()
}

fn bumper_name(style: PadStyle, button: PadButton) -> &'static str {
    match style.glyph(button) {
        Glyph::Text(name) => name,
        _ => "",
    }
}

fn bumper(painter: &Painter, pos: egui::Pos2, label: &str, u: f32) -> f32 {
    // Sizes in units.
    const TEXT_SIZE: f32 = 16.0;
    const HEIGHT: f32 = 30.0;
    const RADIUS: f32 = 8.0;
    const OUTLINE_WIDTH: f32 = 2.0;

    /// Space on either side of the name.
    const PADDING: f32 = 10.0;

    let galley = painter.layout_no_wrap(label.to_owned(), draw::bold(TEXT_SIZE * u), DIM);
    let rect = Rect::from_min_size(
        pos2(pos.x, pos.y - HEIGHT / 2.0 * u),
        vec2(galley.size().x + 2.0 * PADDING * u, HEIGHT * u),
    );

    painter.rect_stroke(
        rect,
        RADIUS * u,
        Stroke::new(OUTLINE_WIDTH * u, DIM),
        StrokeKind::Inside,
    );
    painter.galley(rect.center() - galley.size() / 2.0, galley, DIM);

    rect.right()
}

fn local_time() -> libc::tm {
    // SAFETY: time() accepts a null pointer, and localtime_r() only writes to
    // the tm it is given, which is valid when zeroed.
    unsafe {
        let now = libc::time(std::ptr::null_mut());
        let mut tm: libc::tm = std::mem::zeroed();

        libc::localtime_r(&now, &mut tm);
        tm
    }
}

fn clock_text() -> String {
    let tm = local_time();

    format!("{:02}:{:02}", tm.tm_hour, tm.tm_min)
}

fn seconds_to_next_minute() -> f32 {
    (SECONDS_PER_MINUTE - local_time().tm_sec.clamp(0, SECONDS_PER_MINUTE - 1)) as f32 + CLOCK_SLACK
}

fn request_screenshot(ctx: &egui::Context, path: String) {
    let callback = egui::ScreenshotCallback::new(move |image: Arc<egui::ColorImage>| {
        let [width, height] = image.size;
        let result = image::save_buffer(
            &path,
            image.as_raw(),
            width as u32,
            height as u32,
            image::ExtendedColorType::Rgba8,
        );

        match result {
            Ok(()) => eprintln!("lutris-bigpicture: screenshot saved to {path}"),
            Err(err) => eprintln!("lutris-bigpicture: screenshot failed: {err}"),
        }
    });

    ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(callback));
    ctx.request_repaint();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn held_keys_move_on_but_accept_once() {
        for key in [Key::ArrowLeft, Key::ArrowDown, Key::PageDown, Key::Backspace] {
            assert!(key_repeats(key), "{key:?}");
        }

        for key in [Key::Enter, Key::Space, Key::Escape, Key::Tab, Key::F10] {
            assert!(!key_repeats(key), "{key:?}");
        }
    }
}
