//! Cover art loading. Images are decoded on worker threads and uploaded as
//! textures only while they are on screen (or were recently), so a library of
//! thousands of games costs no more than the covers actually being looked at.

use std::collections::HashMap;
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::{Arc, Condvar, Mutex};

use eframe::egui::{self, ColorImage, TextureHandle, TextureOptions};

/// Covers are shown at most this tall, so there is no point keeping more.
const MAX_COVER_HEIGHT: u32 = 720;

/// How many covers to keep before evicting the least recently shown.
const MAX_CACHED: usize = 320;

/// Requests waiting beyond this are dropped; they are for covers that have
/// been scrolled past and will be asked for again if they come back.
const MAX_QUEUED: usize = 96;

/// Evicting brings the cache down to this size, so it is not done again at
/// once: three quarters of the limit.
const EVICT_TO: usize = MAX_CACHED * 3 / 4;

/// A cover is only evicted once it has not been shown for more frames than
/// this.
const EVICT_IDLE_FRAMES: u64 = 2;

/// The most threads decoding covers, and how many to start when the number
/// of processors is unknown.
const MAX_WORKERS: usize = 4;
const DEFAULT_WORKERS: usize = 2;

/// Width of the blurred copy in pixels, and the limits of its height.
const BLUR_WIDTH: u32 = 40;
const BLUR_MIN_HEIGHT: u32 = 8;
const BLUR_MAX_HEIGHT: u32 = 160;

/// How strongly the copy is blurred: the sigma of the Gaussian, in pixels.
const BLUR_SIGMA: f32 = 2.5;

pub struct Cover {
    pub texture: TextureHandle,
    /// A tiny blurred copy, stretched over the screen as a backdrop.
    pub blurred: TextureHandle,
    /// Width divided by height.
    pub aspect: f32,
}

enum Entry {
    Loading,
    Ready(Cover),
    Failed,
}

struct Slot {
    entry: Entry,
    last_used: u64,
}

type Queue = Arc<(Mutex<Vec<String>>, Condvar)>;

pub struct CoverCache {
    slots: HashMap<String, Slot>,
    queue: Queue,
    results: Receiver<(String, Option<Cover>)>,
    frame: u64,
}

impl CoverCache {
    pub fn new(ctx: &egui::Context) -> Self {
        let queue: Queue = Arc::new((Mutex::new(Vec::new()), Condvar::new()));
        let (tx, results) = channel();
        let workers = std::thread::available_parallelism()
            .map(|n| n.get().saturating_sub(1))
            .unwrap_or(DEFAULT_WORKERS)
            .clamp(1, MAX_WORKERS);
        for i in 0..workers {
            let queue = queue.clone();
            let tx: Sender<(String, Option<Cover>)> = tx.clone();
            let ctx = ctx.clone();
            let _ = std::thread::Builder::new()
                .name(format!("cover-{i}"))
                .spawn(move || worker(&queue, &tx, &ctx));
        }

        Self {
            slots: HashMap::new(),
            queue,
            results,
            frame: 0,
        }
    }

    /// Call once per frame, before drawing.
    pub fn begin_frame(&mut self) {
        self.frame += 1;

        while let Ok((path, cover)) = self.results.try_recv() {
            // A result for a request we have since dropped is simply discarded.
            if let Some(slot) = self.slots.get_mut(&path) {
                slot.entry = match cover {
                    Some(cover) => Entry::Ready(cover),
                    None => Entry::Failed,
                };
            }
        }

        if self.slots.len() > MAX_CACHED {
            self.evict();
        }
    }

    /// The cover at `path` if it is loaded; otherwise it is requested and
    /// `None` is returned until it arrives.
    pub fn get(&mut self, path: &str) -> Option<&Cover> {
        let frame = self.frame;

        if !self.slots.contains_key(path) {
            self.request(path);
        }

        let slot = self.slots.get_mut(path)?;

        slot.last_used = frame;
        match &slot.entry {
            Entry::Ready(cover) => Some(cover),
            _ => None,
        }
    }

    fn request(&mut self, path: &str) {
        self.slots.insert(
            path.to_owned(),
            Slot {
                entry: Entry::Loading,
                last_used: self.frame,
            },
        );

        let (lock, condvar) = &*self.queue;
        let mut pending = lock.lock().unwrap();

        pending.push(path.to_owned());

        if pending.len() > MAX_QUEUED {
            let stale = pending.remove(0);

            self.slots.remove(&stale);
        }

        condvar.notify_one();
    }

    fn evict(&mut self) {
        let frame = self.frame;
        let mut idle: Vec<(u64, String)> = self
            .slots
            .iter()
            .filter(|(_, slot)| slot.last_used + EVICT_IDLE_FRAMES < frame && !matches!(slot.entry, Entry::Loading))
            .map(|(path, slot)| (slot.last_used, path.clone()))
            .collect();
        idle.sort_unstable();

        let excess = self.slots.len().saturating_sub(EVICT_TO);
        for (_, path) in idle.into_iter().take(excess) {
            self.slots.remove(&path);
        }
    }
}

fn worker(queue: &Queue, tx: &Sender<(String, Option<Cover>)>, ctx: &egui::Context) {
    let (lock, condvar) = &**queue;

    loop {
        let path = {
            let mut pending = lock.lock().unwrap();

            loop {
                // Newest first: what was asked for last is what is on screen now.
                if let Some(path) = pending.pop() {
                    break path;
                }

                pending = condvar.wait(pending).unwrap();
            }
        };

        let cover = load(&path, ctx);
        if tx.send((path, cover)).is_err() {
            return;
        }

        ctx.request_repaint();
    }
}

fn load(path: &str, ctx: &egui::Context) -> Option<Cover> {
    // The extension is not trusted: Lutris stores PNGs under .jpg names and
    // vice versa.
    let image = image::ImageReader::open(path)
        .ok()?
        .with_guessed_format()
        .ok()?
        .decode()
        .ok()?;
    let image = if image.height() > MAX_COVER_HEIGHT {
        image.resize(u32::MAX, MAX_COVER_HEIGHT, image::imageops::FilterType::Triangle)
    } else {
        image
    };

    let rgba = image.to_rgba8();
    let (width, height) = rgba.dimensions();
    if width == 0 || height == 0 {
        return None;
    }

    let blur_height = (BLUR_WIDTH * height / width).clamp(BLUR_MIN_HEIGHT, BLUR_MAX_HEIGHT);
    let small = image::imageops::thumbnail(&rgba, BLUR_WIDTH, blur_height);
    let small = image::imageops::blur(&small, BLUR_SIGMA);

    let texture = ctx.load_texture(
        path,
        ColorImage::from_rgba_unmultiplied([width as usize, height as usize], rgba.as_raw()),
        TextureOptions::LINEAR,
    );
    let blurred = ctx.load_texture(
        format!("{path}#blur"),
        ColorImage::from_rgba_unmultiplied([small.width() as usize, small.height() as usize], small.as_raw()),
        TextureOptions::LINEAR,
    );

    Some(Cover {
        texture,
        blurred,
        aspect: width as f32 / height as f32,
    })
}
