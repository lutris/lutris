//! Navigation sounds.
//!
//! The sounds come in packs. A pack is a directory holding one audio file per
//! sound, named after it (`move.ogg`, `select.ogg`, ...; Ogg Vorbis for
//! preference, WAV and MP3 are understood too), and optionally a `pack.json`:
//!
//! ```json
//! { "name": "My Pack", "volume": 0.8, "silent": ["move", "key"] }
//! ```
//!
//! Lutris ships one pack, called `default`, and tells us where packs are and
//! which is selected. A sound that a pack has no file for is taken from the
//! default pack, unless the pack lists it as silent.
//!
//! Playback happens on a thread of its own, which only holds the audio device
//! open while there is something to hear.

use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, RecvTimeoutError, Sender};
use std::sync::Arc;
use std::time::{Duration, Instant};

use rodio::buffer::SamplesBuffer;
use rodio::{ChannelCount, Decoder, DeviceSinkBuilder, SampleRate, Source};

/// ID of the pack that Lutris ships, which the others fall back on.
pub const PACK_DEFAULT: &str = "default";

/// ID that stands for no sounds at all.
pub const PACK_OFF: &str = "off";

/// The file in a pack's directory that describes it.
const MANIFEST_FILE: &str = "pack.json";

/// The audio device is released after this long without a sound.
const IDLE_CLOSE: Duration = Duration::from_secs(4);

/// After the audio device could not be opened, it is left alone for this
/// long: each attempt can take long enough to be felt.
const RETRY_AFTER: Duration = Duration::from_secs(30);

/// The kinds of audio file looked for, the preferred one first.
const EXTENSIONS: [&str; 3] = ["ogg", "wav", "mp3"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Sound {
    /// The focus moved.
    Move,
    /// Something was chosen.
    Select,
    /// Going back, or closing something.
    Back,
    /// Switching between the home screen and the library.
    Tab,
    /// The menu or the on-screen keyboard opened.
    Open,
    /// A character was typed.
    Key,
    /// A setting was switched, such as a favorite.
    Toggle,
    /// A game is being launched.
    Launch,
    /// Something went wrong.
    Error,
}

impl Sound {
    pub const ALL: [Sound; 9] = [
        Sound::Move,
        Sound::Select,
        Sound::Back,
        Sound::Tab,
        Sound::Open,
        Sound::Key,
        Sound::Toggle,
        Sound::Launch,
        Sound::Error,
    ];

    /// Where the sound is in `ALL`, and so in a bank.
    fn index(self) -> usize {
        Self::ALL.iter().position(|sound| *sound == self).unwrap_or(0)
    }

    /// The name of the sound's file in a pack, without extension.
    pub fn file_stem(self) -> &'static str {
        match self {
            Sound::Move => "move",
            Sound::Select => "select",
            Sound::Back => "back",
            Sound::Tab => "tab",
            Sound::Open => "open",
            Sound::Key => "key",
            Sound::Toggle => "toggle",
            Sound::Launch => "launch",
            Sound::Error => "error",
        }
    }
}

/// Decoded audio, ready to be played any number of times.
#[derive(Clone)]
struct Clip {
    channels: ChannelCount,
    sample_rate: SampleRate,
    samples: Arc<[f32]>,
}

/// One clip per sound, in the order of `Sound::ALL`; `None` is silence.
type Bank = Vec<Option<Clip>>;

/// What a pack has to say about one sound.
enum Entry {
    /// Nothing: it has no file for it.
    Missing,
    /// That it is not to be heard.
    Silent,
    Clip(Clip),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Pack {
    /// What the pack is selected by: its directory name.
    pub id: String,
    /// What it is called on screen.
    pub name: String,
    /// Where its files are; `None` for the pack that makes no sound.
    dir: Option<PathBuf>,
}

impl Pack {
    fn off() -> Self {
        Self {
            id: PACK_OFF.to_owned(),
            name: "Off".to_owned(),
            dir: None,
        }
    }
}

enum Message {
    Bank(Bank),
    Play(Sound),
}

pub struct Sounds {
    tx: Option<Sender<Message>>,
    packs: Vec<Pack>,
    current: String,
}

impl Sounds {
    /// Starts out silent; `configure` is called once Lutris has told us where
    /// the packs are and what the user wants.
    pub fn new() -> Self {
        Self {
            tx: None,
            packs: vec![Pack::off()],
            current: PACK_OFF.to_owned(),
        }
    }

    /// Looks for packs in `dirs` (earlier directories win over later ones)
    /// and selects `pack`, or the default pack if that one is gone.
    pub fn configure(&mut self, dirs: &[PathBuf], pack: &str) {
        let mut found: Vec<Pack> = Vec::new();

        for dir in dirs {
            for pack in scan_packs(dir) {
                if !found.iter().any(|known| known.id == pack.id) {
                    found.push(pack);
                }
            }
        }

        // The default pack first, and no sounds last, after all that make some.
        found.sort_by_key(|pack| (pack.id != PACK_DEFAULT, pack.name.to_lowercase()));
        found.push(Pack::off());

        self.packs = found;
        self.select(pack);
    }

    pub fn current(&self) -> &Pack {
        self.packs
            .iter()
            .find(|pack| pack.id == self.current)
            .unwrap_or(&self.packs[0])
    }

    /// Switches to the next (or previous) pack and returns its ID.
    pub fn cycle(&mut self, forward: bool) -> String {
        let count = self.packs.len();
        let index = self.packs.iter().position(|pack| pack.id == self.current).unwrap_or(0);
        let next = if forward {
            (index + 1) % count
        } else {
            (index + count - 1) % count
        };

        let id = self.packs[next].id.clone();

        self.select(&id);

        id
    }

    fn select(&mut self, id: &str) {
        let pack = self
            .packs
            .iter()
            .find(|pack| pack.id == id)
            .unwrap_or(&self.packs[0])
            .clone();
        self.current = pack.id.clone();

        match self.bank(&pack) {
            Some(bank) => self.send(Message::Bank(bank)),
            // Nothing to play: let the thread, and the device, go.
            None => self.tx = None,
        }
    }

    /// What to play for each sound with a pack selected; `None` if it is the
    /// pack that makes no sound.
    fn bank(&self, pack: &Pack) -> Option<Bank> {
        let chosen = load_pack(pack.dir.as_ref()?);
        let fallback = self
            .packs
            .iter()
            .find(|other| other.id == PACK_DEFAULT && other.id != pack.id)
            .and_then(|default| default.dir.as_deref())
            .map(load_pack);

        let bank = chosen
            .into_iter()
            .enumerate()
            .map(|(index, entry)| match entry {
                Entry::Clip(clip) => Some(clip),
                Entry::Silent => None,
                Entry::Missing => match fallback.as_ref().map(|fallback| &fallback[index]) {
                    Some(Entry::Clip(clip)) => Some(clip.clone()),
                    _ => None,
                },
            })
            .collect();

        Some(bank)
    }

    pub fn play(&mut self, sound: Sound) {
        if self.current != PACK_OFF {
            self.send(Message::Play(sound));
        }
    }

    fn send(&mut self, message: Message) {
        if self.tx.is_none() {
            let (tx, rx) = channel();
            let spawned = std::thread::Builder::new()
                .name("sounds".into())
                .spawn(move || playback_thread(&rx));
            match spawned {
                Ok(_) => self.tx = Some(tx),
                Err(err) => {
                    eprintln!("lutris-bigpicture: could not start the sound thread: {err}");

                    return;
                }
            }
        }

        if let Some(tx) = &self.tx {
            let _ = tx.send(message);
        }
    }
}

fn playback_thread(rx: &std::sync::mpsc::Receiver<Message>) {
    let mut bank: Bank = Vec::new();
    let mut sink = None;
    let mut last_played = Instant::now();
    let mut retry_at = Instant::now();

    loop {
        let message = if sink.is_some() {
            rx.recv_timeout(IDLE_CLOSE)
        } else {
            rx.recv().map_err(|_| RecvTimeoutError::Disconnected)
        };

        match message {
            Ok(Message::Bank(new_bank)) => bank = new_bank,
            Ok(Message::Play(sound)) => {
                let Some(Some(clip)) = bank.get(sound.index()) else {
                    continue;
                };

                if sink.is_none() && Instant::now() >= retry_at {
                    match DeviceSinkBuilder::open_default_sink() {
                        Ok(mut opened) => {
                            opened.log_on_drop(false);
                            sink = Some(opened);
                        }
                        Err(err) => {
                            eprintln!("lutris-bigpicture: no sound: {err}");
                            retry_at = Instant::now() + RETRY_AFTER;
                        }
                    }
                }

                if let Some(sink) = &sink {
                    let samples: Vec<f32> = clip.samples.to_vec();

                    sink.mixer()
                        .add(SamplesBuffer::new(clip.channels, clip.sample_rate, samples));
                    last_played = Instant::now();
                }
            }
            Err(RecvTimeoutError::Timeout) => {}
            Err(RecvTimeoutError::Disconnected) => return,
        }

        if sink.is_some() && last_played.elapsed() >= IDLE_CLOSE {
            sink = None;
        }
    }
}

// ---------------------------------------------------------------- packs

/// The packs in `dir`: its subdirectories holding at least one sound file or
/// a manifest.
fn scan_packs(dir: &Path) -> Vec<Pack> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };

    let mut packs: Vec<Pack> = entries
        .flatten()
        .filter_map(|entry| {
            let path = entry.path();
            let id = path.file_name()?.to_str()?.to_owned();
            if !path.is_dir() || id == PACK_OFF || id.starts_with('.') {
                return None;
            }

            let manifest = read_manifest(&path);
            let has_sounds = Sound::ALL.iter().any(|sound| sound_file(&path, *sound).is_some());
            if !has_sounds && manifest.is_null() {
                return None;
            }

            let name = manifest
                .get("name")
                .and_then(|name| name.as_str())
                .filter(|name| !name.trim().is_empty())
                .unwrap_or(&id)
                .to_owned();

            Some(Pack {
                id,
                name,
                dir: Some(path),
            })
        })
        .collect();
    packs.sort_by_key(|pack| pack.name.to_lowercase());

    packs
}

fn read_manifest(dir: &Path) -> serde_json::Value {
    std::fs::read_to_string(dir.join(MANIFEST_FILE))
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or(serde_json::Value::Null)
}

fn sound_file(dir: &Path, sound: Sound) -> Option<PathBuf> {
    EXTENSIONS
        .iter()
        .map(|extension| dir.join(format!("{}.{extension}", sound.file_stem())))
        .find(|path| path.is_file())
}

/// What the pack in `dir` has for each sound, in the order of `Sound::ALL`.
fn load_pack(dir: &Path) -> Vec<Entry> {
    let manifest = read_manifest(dir);
    let volume = manifest
        .get("volume")
        .and_then(|volume| volume.as_f64())
        .map_or(1.0, |volume| volume.clamp(0.0, 1.0) as f32);
    let silent: Vec<&str> = manifest
        .get("silent")
        .and_then(|silent| silent.as_array())
        .map(|names| names.iter().filter_map(|name| name.as_str()).collect())
        .unwrap_or_default();

    Sound::ALL
        .iter()
        .map(|sound| {
            if silent.contains(&sound.file_stem()) {
                return Entry::Silent;
            }

            let Some(path) = sound_file(dir, *sound) else {
                return Entry::Missing;
            };

            match decode(&path, volume) {
                Some(clip) => Entry::Clip(clip),
                None => {
                    eprintln!("lutris-bigpicture: cannot play {}", path.display());

                    Entry::Missing
                }
            }
        })
        .collect()
}

fn decode(path: &Path, volume: f32) -> Option<Clip> {
    let file = std::fs::File::open(path).ok()?;
    let decoder = Decoder::try_from(file).ok()?;
    let channels = decoder.channels();
    let sample_rate = decoder.sample_rate();
    let samples: Vec<f32> = decoder.map(|sample| sample * volume).collect();
    if samples.is_empty() {
        return None;
    }

    Some(Clip {
        channels,
        sample_rate,
        samples: samples.into(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The sample rate of the WAV files the tests write.
    const TEST_RATE: u32 = 8000;

    /// How many samples they hold.
    const TEST_SAMPLES: u32 = 80;

    /// Half of full scale, as a 16-bit sample.
    const HALF_SCALE: i16 = 16384;

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("lutris-bigpicture-test-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);

        std::fs::create_dir_all(&dir).unwrap();

        dir
    }

    /// The pack that Lutris ships, in the source tree.
    fn shipped_pack() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../share/lutris/bigpicture/sounds")
            .join(PACK_DEFAULT)
    }

    /// A minimal 16-bit mono WAV file of samples of a constant value.
    fn write_wav(path: &Path, value: i16) {
        const HEADER_AFTER_SIZE: u32 = 36;
        const FORMAT_CHUNK_SIZE: u32 = 16;
        const PCM: u16 = 1;
        const MONO: u16 = 1;
        const BYTES_PER_SAMPLE: u16 = 2;

        let data_len = TEST_SAMPLES * u32::from(BYTES_PER_SAMPLE);
        let mut bytes = Vec::new();

        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&(HEADER_AFTER_SIZE + data_len).to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt ");
        bytes.extend_from_slice(&FORMAT_CHUNK_SIZE.to_le_bytes());
        bytes.extend_from_slice(&PCM.to_le_bytes());
        bytes.extend_from_slice(&MONO.to_le_bytes());
        bytes.extend_from_slice(&TEST_RATE.to_le_bytes());
        bytes.extend_from_slice(&(TEST_RATE * u32::from(BYTES_PER_SAMPLE)).to_le_bytes());
        bytes.extend_from_slice(&BYTES_PER_SAMPLE.to_le_bytes());
        bytes.extend_from_slice(&(BYTES_PER_SAMPLE * 8).to_le_bytes());
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&data_len.to_le_bytes());

        for _ in 0..TEST_SAMPLES {
            bytes.extend_from_slice(&value.to_le_bytes());
        }

        std::fs::write(path, bytes).unwrap();
    }

    fn clip_of(entry: &Entry) -> Option<&Clip> {
        match entry {
            Entry::Clip(clip) => Some(clip),
            _ => None,
        }
    }

    #[test]
    fn the_default_pack_has_every_sound_short_and_quiet() {
        const LONGEST_SECONDS: f32 = 1.5;
        const LOUDEST_PEAK: f32 = 0.12;

        let pack = load_pack(&shipped_pack());

        for sound in Sound::ALL {
            let clip = clip_of(&pack[sound.index()]).unwrap_or_else(|| panic!("no {sound:?}"));
            let frames = clip.samples.len() / usize::from(clip.channels.get());
            let seconds = frames as f32 / clip.sample_rate.get() as f32;

            assert!(
                seconds > 0.01 && seconds < LONGEST_SECONDS,
                "{sound:?} lasts {seconds}s"
            );

            let peak = clip.samples.iter().fold(0.0f32, |peak, s| peak.max(s.abs()));

            assert!(peak > 0.0 && peak < LOUDEST_PEAK, "{sound:?} peaks at {peak}");
        }

        assert_eq!(read_manifest(&shipped_pack())["name"], "Default");
    }

    #[test]
    fn packs_are_found_named_and_sorted() {
        let dir = temp_dir("scan");

        std::fs::create_dir_all(dir.join("zeta")).unwrap();
        write_wav(&dir.join("zeta/move.wav"), HALF_SCALE);
        std::fs::create_dir_all(dir.join("retro")).unwrap();
        write_wav(&dir.join("retro/select.wav"), HALF_SCALE);
        std::fs::write(dir.join("retro/pack.json"), r#"{"name": "Arcade"}"#).unwrap();
        std::fs::create_dir_all(dir.join("empty")).unwrap();
        std::fs::write(dir.join("stray.wav"), b"").unwrap();

        let packs = scan_packs(&dir);
        let found: Vec<(&str, &str)> = packs.iter().map(|p| (p.id.as_str(), p.name.as_str())).collect();

        assert_eq!(found, [("retro", "Arcade"), ("zeta", "zeta")]);

        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn a_pack_falls_back_on_the_default_pack_and_can_be_silent() {
        let dir = temp_dir("bank");

        std::fs::create_dir_all(dir.join("default")).unwrap();

        for sound in Sound::ALL {
            let file = format!("{}.ogg", sound.file_stem());

            std::fs::copy(shipped_pack().join(&file), dir.join("default").join(&file)).unwrap();
        }

        std::fs::create_dir_all(dir.join("mine")).unwrap();
        write_wav(&dir.join("mine/move.wav"), HALF_SCALE);
        std::fs::write(dir.join("mine/pack.json"), r#"{"volume": 0.5, "silent": ["key"]}"#).unwrap();

        let mut sounds = Sounds::new();

        sounds.configure(std::slice::from_ref(&dir), "mine");

        let bank = sounds.bank(sounds.current()).unwrap();
        let moved = bank[Sound::Move.index()].as_ref().unwrap();

        assert_eq!(moved.sample_rate.get(), TEST_RATE);
        assert_eq!(moved.samples.len(), TEST_SAMPLES as usize);
        assert!((moved.samples[0] - 0.25).abs() < 0.01, "volume is applied");
        assert!(bank[Sound::Key.index()].is_none(), "listed as silent");

        let default = load_pack(&dir.join("default"));
        let select = bank[Sound::Select.index()].as_ref().unwrap();

        assert_eq!(
            select.samples.len(),
            clip_of(&default[Sound::Select.index()]).unwrap().samples.len()
        );

        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn selection_falls_back_on_the_default_pack_and_cycles() {
        let dir = temp_dir("cycle");

        for pack in ["zeta", "default"] {
            std::fs::create_dir_all(dir.join(pack)).unwrap();
            write_wav(&dir.join(pack).join("move.wav"), HALF_SCALE);
        }

        let mut sounds = Sounds::new();

        assert_eq!(sounds.current().id, PACK_OFF, "silent until told otherwise");

        sounds.configure(std::slice::from_ref(&dir), "gone");

        assert_eq!(sounds.current().id, PACK_DEFAULT);
        assert_eq!(sounds.cycle(true), "zeta");
        assert_eq!(sounds.cycle(true), PACK_OFF);
        assert_eq!(sounds.cycle(true), PACK_DEFAULT);
        assert_eq!(sounds.cycle(false), PACK_OFF);

        std::fs::remove_dir_all(dir).unwrap();
    }
}
