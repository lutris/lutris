//! The line-delimited JSON protocol spoken with Lutris.
//!
//! Lutris starts this program as a child process and owns the library, the
//! game processes and the translations. It writes one JSON object per line to
//! our stdin and reads our requests from our stdout, so nothing else may be
//! printed there (diagnostics go to stderr).
//!
//! Leaving is not a message: we just exit, and the exit status tells Lutris
//! whether to bring its window back (0) or to quit as well
//! (`EXIT_QUIT_LUTRIS`). Unlike a last message, that cannot be lost.

use std::collections::HashMap;
use std::io::{BufRead, Write};

use serde::{Deserialize, Serialize};

/// Exit status that asks Lutris to quit too.
pub const EXIT_QUIT_LUTRIS: i32 = 3;

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RunState {
    #[default]
    Stopped,
    Launching,
    Running,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Game {
    pub id: String,
    pub name: String,
    /// Name to sort by, if it differs from the display name.
    pub sortname: String,
    pub runner: String,
    pub platform: String,
    pub year: Option<i64>,
    /// Hours played, for sorting; `playtime_text` is what gets shown.
    pub playtime: f64,
    pub playtime_text: String,
    /// Unix timestamps, 0 when unknown.
    pub lastplayed: i64,
    pub lastplayed_text: String,
    pub installed_at: i64,
    /// Path of the cover image, if Lutris has one.
    pub cover: Option<String>,
    pub favorite: bool,
    pub categories: Vec<String>,
    pub state: RunState,
}

/// Which navigation sounds to use, and where sound packs are found.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct SoundConfig {
    /// ID of the selected pack; empty for the default pack.
    pub pack: String,
    /// Directories holding sound packs, the most important first.
    pub dirs: Vec<String>,
}

/// Messages from Lutris.
#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Incoming {
    /// Translated UI strings, keyed by their English text.
    Init {
        #[serde(default)]
        strings: HashMap<String, String>,
        #[serde(default)]
        sounds: SoundConfig,
    },
    /// The full library; sent at startup and whenever it changes.
    Library {
        games: Vec<Game>,
    },
    GameState {
        id: String,
        state: RunState,
        #[serde(default)]
        status: String,
    },
    /// Something went wrong that the user should know about.
    Error {
        message: String,
    },
    /// Leave Big Picture mode.
    Quit,
    /// Test hooks, only honoured with `--debug-protocol`.
    DebugAction {
        action: String,
    },
    DebugScreenshot {
        path: String,
    },
}

/// Requests to Lutris.
#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Outgoing {
    Ready,
    Launch {
        id: String,
    },
    Stop {
        id: String,
    },
    SetFavorite {
        id: String,
        favorite: bool,
    },
    /// The user picked other navigation sounds; Lutris remembers the choice.
    SetSoundPack {
        pack: String,
    },
    /// The user switched the opening animation on or off, for next time.
    SetSplash {
        enabled: bool,
    },
}

pub fn send(message: &Outgoing) {
    let Ok(line) = serde_json::to_string(message) else {
        return;
    };

    let mut stdout = std::io::stdout().lock();
    // A closed pipe means Lutris is gone; the reader thread notices and quits.
    let _ = writeln!(stdout, "{line}");
    let _ = stdout.flush();
}

/// Reads messages from stdin on a background thread, waking the UI for each.
/// When stdin closes, Lutris is gone and we are told to quit.
pub fn spawn_reader(tx: std::sync::mpsc::Sender<Incoming>, ctx: eframe::egui::Context) {
    std::thread::Builder::new()
        .name("lutris-reader".into())
        .spawn(move || {
            for line in std::io::stdin().lock().lines() {
                let Ok(line) = line else { break };
                if line.trim().is_empty() {
                    continue;
                }

                match serde_json::from_str::<Incoming>(&line) {
                    Ok(message) => {
                        if tx.send(message).is_err() {
                            return;
                        }

                        ctx.request_repaint();
                    }
                    Err(err) => eprintln!("lutris-bigpicture: ignoring bad message: {err}"),
                }
            }

            let _ = tx.send(Incoming::Quit);

            ctx.request_repaint();
        })
        .expect("failed to start the reader thread");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn library_message_tolerates_missing_and_null_fields() {
        let line =
            r#"{"type":"library","games":[{"id":"7","name":"A Game","year":null,"cover":null,"state":"running"}]}"#;
        let Incoming::Library { games } = serde_json::from_str(line).unwrap() else {
            panic!("not a library message");
        };

        assert_eq!(games[0].id, "7");
        assert_eq!(games[0].state, RunState::Running);
        assert!(games[0].cover.is_none() && games[0].categories.is_empty());
    }

    #[test]
    fn requests_are_tagged_with_their_type() {
        let line = serde_json::to_string(&Outgoing::SetFavorite {
            id: "7".into(),
            favorite: true,
        })
        .unwrap();

        assert_eq!(line, r#"{"type":"set_favorite","id":"7","favorite":true}"#);
        assert_eq!(serde_json::to_string(&Outgoing::Ready).unwrap(), r#"{"type":"ready"}"#);
    }

    #[test]
    fn unknown_messages_are_errors_not_panics() {
        assert!(serde_json::from_str::<Incoming>(r#"{"type":"mystery"}"#).is_err());
    }
}
