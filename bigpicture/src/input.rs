//! Controller input. Keyboard and mouse come through the windowing system;
//! gamepads are read here on their own thread and turned into the same
//! navigation actions.

use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::mpsc::Sender;
use std::sync::Arc;
use std::time::{Duration, Instant};

use eframe::egui;
use gilrs::{Axis, Button, EventType, Gilrs};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Up,
    Down,
    Left,
    Right,
    Accept,
    Back,
    Menu,
    Search,
    /// The secondary action: sort in the library, backspace on the keyboard.
    Alt,
    TabPrev,
    TabNext,
    PageUp,
    PageDown,
}

impl Action {
    pub fn from_name(name: &str) -> Option<Self> {
        Some(match name {
            "up" => Self::Up,
            "down" => Self::Down,
            "left" => Self::Left,
            "right" => Self::Right,
            "accept" => Self::Accept,
            "back" => Self::Back,
            "menu" => Self::Menu,
            "search" => Self::Search,
            "alt" => Self::Alt,
            "tab_prev" => Self::TabPrev,
            "tab_next" => Self::TabNext,
            "page_up" => Self::PageUp,
            "page_down" => Self::PageDown,
            _ => return None,
        })
    }
}

/// What kind of controller is in use, which decides how its buttons are
/// named on screen.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum PadStyle {
    /// No controller is connected.
    None = 0,
    /// Xbox controllers, and everything else that is laid out and labelled
    /// like one - which is nearly everything else.
    Xbox = 1,
    PlayStation = 2,
    Nintendo = 3,
}

/// The buttons that are named on screen, by what they do here.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PadButton {
    Accept,
    Back,
    Alt,
    Search,
    Menu,
    TabPrev,
    TabNext,
}

/// How a button is shown: by its letter or name, or by the symbol on it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Glyph<'a> {
    /// A name: of a controller's button, or of a key, which is translated.
    Text(&'a str),
    Cross,
    Circle,
    Square,
    Triangle,
}

impl PadStyle {
    pub fn from_u8(value: u8) -> Self {
        match value {
            1 => Self::Xbox,
            2 => Self::PlayStation,
            3 => Self::Nintendo,
            _ => Self::None,
        }
    }

    /// Works out the kind of a controller from its USB vendor ID, where it
    /// has one, and from its name, which is what Bluetooth and the drivers
    /// that wrap controllers leave us with.
    pub fn detect(name: &str, vendor_id: Option<u16>) -> Self {
        const SONY: u16 = 0x054c;
        const NINTENDO: u16 = 0x057e;

        let name = name.to_lowercase();
        let named = |words: &[&str]| words.iter().any(|word| name.contains(word));
        if vendor_id == Some(SONY) || named(&["dualsense", "dualshock", "playstation", "ps3", "ps4", "ps5", "sony"]) {
            Self::PlayStation
        } else if vendor_id == Some(NINTENDO) || named(&["nintendo", "switch", "joy-con", "pro controller"]) {
            Self::Nintendo
        } else {
            Self::Xbox
        }
    }

    /// What the button that does something here is called on this kind of
    /// controller. The buttons are told apart by where they are - the
    /// bottom one of the four accepts, on every controller - so it is only
    /// their names that differ.
    pub fn glyph(self, button: PadButton) -> Glyph<'static> {
        use Glyph::{Circle, Cross, Square, Text, Triangle};
        match (self, button) {
            (Self::PlayStation, PadButton::Accept) => Cross,
            (Self::PlayStation, PadButton::Back) => Circle,
            (Self::PlayStation, PadButton::Alt) => Square,
            (Self::PlayStation, PadButton::Search) => Triangle,
            (Self::PlayStation, PadButton::Menu) => Text("OPTIONS"),
            (Self::PlayStation, PadButton::TabPrev) => Text("L1"),
            (Self::PlayStation, PadButton::TabNext) => Text("R1"),
            // Nintendo's letters are the other way round from Xbox's.
            (Self::Nintendo, PadButton::Accept) => Text("B"),
            (Self::Nintendo, PadButton::Back) => Text("A"),
            (Self::Nintendo, PadButton::Alt) => Text("Y"),
            (Self::Nintendo, PadButton::Search) => Text("X"),
            (Self::Nintendo, PadButton::Menu) => Text("+"),
            (Self::Nintendo, PadButton::TabPrev) => Text("L"),
            (Self::Nintendo, PadButton::TabNext) => Text("R"),
            (_, PadButton::Accept) => Text("A"),
            (_, PadButton::Back) => Text("B"),
            (_, PadButton::Alt) => Text("X"),
            (_, PadButton::Search) => Text("Y"),
            (_, PadButton::Menu) => Text("MENU"),
            (_, PadButton::TabPrev) => Text("LB"),
            (_, PadButton::TabNext) => Text("RB"),
        }
    }
}

const REPEAT_DELAY: Duration = Duration::from_millis(380);
const REPEAT_INTERVAL: Duration = Duration::from_millis(95);
const STICK_PRESS: f32 = 0.6;
const STICK_RELEASE: f32 = 0.4;

/// How many times further the stick has to be pushed along the other axis
/// before the direction it is held in changes.
const STICK_DOMINANCE: f32 = 1.3;

/// How long the thread waits for a controller to do something before it
/// looks again for which controllers there are.
const IDLE_TIMEOUT: Duration = Duration::from_secs(2);

/// Starts the gamepad thread. It sleeps in the kernel until a controller does
/// something, so an idle controller costs nothing. `style` is kept at the
/// kind (as a `PadStyle`) of the controller that was used last.
pub fn spawn_gamepad_thread(tx: Sender<Action>, ctx: egui::Context, style: Arc<AtomicU8>) {
    let spawned = std::thread::Builder::new().name("gamepad".into()).spawn(move || {
        let mut gilrs = match Gilrs::new() {
            Ok(gilrs) => gilrs,
            Err(err) => {
                eprintln!("lutris-bigpicture: controllers unavailable: {err}");

                return;
            }
        };

        let mut dpad: Option<Action> = None;
        let mut stick = (0.0f32, 0.0f32);
        let mut stick_dir: Option<Action> = None;
        let mut held: Option<(Action, Instant)> = None;
        let mut active: Option<gilrs::GamepadId> = None;

        loop {
            // Until a controller is used, go by the first one there is.
            let style_of = |gamepad: gilrs::Gamepad<'_>| PadStyle::detect(gamepad.name(), gamepad.vendor_id());

            if active.and_then(|id| gilrs.connected_gamepad(id)).is_none() {
                active = gilrs.gamepads().next().map(|(id, _)| id);

                let found = active.map_or(PadStyle::None, |id| style_of(gilrs.gamepad(id)));
                if style.swap(found as u8, Ordering::Relaxed) != found as u8 {
                    ctx.request_repaint();
                }
            }

            let timeout = match held {
                Some((_, next)) => next.saturating_duration_since(Instant::now()),
                None => IDLE_TIMEOUT,
            };

            let event = gilrs.next_event_blocking(Some(timeout));
            let mut actions: Vec<Action> = Vec::new();

            if let Some(event) = event {
                // Whichever controller is being used is the one whose
                // buttons get named.
                let used = matches!(event.event, EventType::ButtonPressed(..) | EventType::AxisChanged(..));
                if used && active != Some(event.id) {
                    if let Some(gamepad) = gilrs.connected_gamepad(event.id) {
                        active = Some(event.id);
                        style.store(style_of(gamepad) as u8, Ordering::Relaxed);
                    }
                }

                match event.event {
                    EventType::ButtonPressed(button, _) => match button {
                        Button::DPadUp => dpad = Some(Action::Up),
                        Button::DPadDown => dpad = Some(Action::Down),
                        Button::DPadLeft => dpad = Some(Action::Left),
                        Button::DPadRight => dpad = Some(Action::Right),
                        Button::South => actions.push(Action::Accept),
                        Button::East => actions.push(Action::Back),
                        Button::West => actions.push(Action::Alt),
                        Button::North => actions.push(Action::Search),
                        Button::Start | Button::Mode => actions.push(Action::Menu),
                        Button::LeftTrigger => actions.push(Action::TabPrev),
                        Button::RightTrigger => actions.push(Action::TabNext),
                        Button::LeftTrigger2 => actions.push(Action::PageUp),
                        Button::RightTrigger2 => actions.push(Action::PageDown),
                        _ => {}
                    },
                    EventType::ButtonReleased(button, _) => {
                        let released = match button {
                            Button::DPadUp => Some(Action::Up),
                            Button::DPadDown => Some(Action::Down),
                            Button::DPadLeft => Some(Action::Left),
                            Button::DPadRight => Some(Action::Right),
                            _ => None,
                        };

                        if released.is_some() && released == dpad {
                            dpad = None;
                        }
                    }
                    EventType::AxisChanged(axis, value, _) => {
                        match axis {
                            Axis::LeftStickX => stick.0 = value,
                            Axis::LeftStickY => stick.1 = value,
                            _ => {}
                        }

                        stick_dir = stick_direction(stick, stick_dir);
                    }
                    EventType::Disconnected => {
                        dpad = None;
                        stick = (0.0, 0.0);
                        stick_dir = None;
                    }
                    _ => {}
                }
            }

            // Turn the held direction into an initial press plus repeats.
            let direction = dpad.or(stick_dir);
            let now = Instant::now();

            match (direction, held) {
                (None, _) => held = None,
                (Some(dir), Some((held_dir, next))) if dir == held_dir => {
                    if now >= next {
                        actions.push(dir);
                        held = Some((dir, now + REPEAT_INTERVAL));
                    }
                }
                (Some(dir), _) => {
                    actions.push(dir);
                    held = Some((dir, now + REPEAT_DELAY));
                }
            }

            if !actions.is_empty() {
                for action in actions {
                    if tx.send(action).is_err() {
                        return;
                    }
                }

                ctx.request_repaint();
            }
        }
    });

    if let Err(err) = spawned {
        eprintln!("lutris-bigpicture: could not start the gamepad thread: {err}");
    }
}

/// The direction the stick points in, with hysteresis so it does not chatter
/// around the threshold.
fn stick_direction((x, y): (f32, f32), current: Option<Action>) -> Option<Action> {
    let threshold = if current.is_some() { STICK_RELEASE } else { STICK_PRESS };
    if x.abs() < threshold && y.abs() < threshold {
        return None;
    }

    // Keep the current direction unless the other axis clearly dominates.
    let horizontal = match current {
        Some(Action::Left | Action::Right) => x.abs() * STICK_DOMINANCE > y.abs(),
        Some(_) => x.abs() > y.abs() * STICK_DOMINANCE,
        None => x.abs() > y.abs(),
    };

    Some(if horizontal {
        if x > 0.0 {
            Action::Right
        } else {
            Action::Left
        }
    } else if y > 0.0 {
        Action::Up
    } else {
        Action::Down
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn controllers_are_told_apart() {
        // Over Bluetooth a DualSense has a name but may have no vendor ID.
        assert_eq!(
            PadStyle::detect("DualSense Wireless Controller", None),
            PadStyle::PlayStation
        );
        assert_eq!(
            PadStyle::detect("Wireless Controller", Some(0x054c)),
            PadStyle::PlayStation
        );
        assert_eq!(PadStyle::detect("PS4 Controller", None), PadStyle::PlayStation);
        assert_eq!(
            PadStyle::detect("Nintendo Switch Pro Controller", None),
            PadStyle::Nintendo
        );
        assert_eq!(PadStyle::detect("Some Pad", Some(0x057e)), PadStyle::Nintendo);
        assert_eq!(
            PadStyle::detect("Xbox Wireless Controller", Some(0x045e)),
            PadStyle::Xbox
        );
        assert_eq!(PadStyle::detect("Steam Deck", Some(0x28de)), PadStyle::Xbox);
        assert_eq!(PadStyle::detect("8BitDo Something", None), PadStyle::Xbox);

        for style in [
            PadStyle::None,
            PadStyle::Xbox,
            PadStyle::PlayStation,
            PadStyle::Nintendo,
        ] {
            assert_eq!(PadStyle::from_u8(style as u8), style);
        }
    }

    #[test]
    fn buttons_are_named_as_on_the_controller() {
        assert_eq!(PadStyle::PlayStation.glyph(PadButton::Accept), Glyph::Cross);
        assert_eq!(PadStyle::PlayStation.glyph(PadButton::Back), Glyph::Circle);
        assert_eq!(PadStyle::PlayStation.glyph(PadButton::TabPrev), Glyph::Text("L1"));
        assert_eq!(PadStyle::Xbox.glyph(PadButton::Accept), Glyph::Text("A"));
        assert_eq!(PadStyle::Nintendo.glyph(PadButton::Accept), Glyph::Text("B"));
    }

    #[test]
    fn stick_at_rest_has_no_direction() {
        assert_eq!(stick_direction((0.1, -0.2), None), None);
    }

    #[test]
    fn stick_follows_its_dominant_axis() {
        assert_eq!(stick_direction((0.9, 0.2), None), Some(Action::Right));
        assert_eq!(stick_direction((-0.9, 0.2), None), Some(Action::Left));
        assert_eq!(stick_direction((0.1, 0.8), None), Some(Action::Up));
        assert_eq!(stick_direction((0.1, -0.8), None), Some(Action::Down));
    }

    #[test]
    fn stick_holds_its_direction_until_clearly_released() {
        // Below the press threshold, but not yet back past the release one.
        assert_eq!(stick_direction((0.5, 0.0), Some(Action::Right)), Some(Action::Right));
        assert_eq!(stick_direction((0.5, 0.0), None), None);
        assert_eq!(stick_direction((0.3, 0.0), Some(Action::Right)), None);
    }

    #[test]
    fn stick_does_not_flip_axis_on_a_near_diagonal() {
        assert_eq!(stick_direction((0.7, 0.75), Some(Action::Right)), Some(Action::Right));
        assert_eq!(stick_direction((0.7, 0.75), Some(Action::Up)), Some(Action::Up));
    }

    #[test]
    fn actions_have_names_for_the_test_protocol() {
        assert_eq!(Action::from_name("accept"), Some(Action::Accept));
        assert_eq!(Action::from_name("nonsense"), None);
    }
}
