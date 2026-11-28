//! The opening animation: the Lutris otter rolls in around its ball and the
//! name appears under it; then, in one clean cut, the interface is there,
//! having got itself ready underneath in the meantime.

use eframe::egui::{self, emath::Rot2, pos2, vec2, Color32, Painter, Rect, TextureHandle, TextureOptions};

use crate::draw::{self, ACCENT, BG, TEXT};

/// The Lutris icon, rendered from share/icons/hicolor/scalable/apps/
/// net.lutris.Lutris.svg with `rsvg-convert -w 768 -h 768`.
const ICON: &[u8] = include_bytes!("../assets/lutris.png");

/// How long the icon takes to roll in, when the name starts to appear, and
/// when it is all over.
const ROLL_SECONDS: f32 = 0.9;
const NAME_AT: f32 = 0.5;
const END_AT: f32 = 2.3;

/// How long the icon takes to become solid, to grow to its size, and the
/// name to appear, in seconds.
const ICON_FADE_SECONDS: f32 = 0.4;
const GROW_SECONDS: f32 = 0.8;
const NAME_FADE_SECONDS: f32 = 0.5;

/// The rolling slows down as the cube of the time left.
const ROLL_EASING_POWER: i32 = 3;

/// How far from upright the icon starts out, in degrees.
const START_ANGLE: f32 = 110.0;

/// The icon's scale when it starts out, and how much it gains on the way;
/// together they make 1.
const START_SCALE: f32 = 0.55;
const SCALE_GAIN: f32 = 0.45;

/// How far `overshoot` goes too far: the constant of the usual "back"
/// easing, which overshoots by a tenth, and the same plus one.
const OVERSHOOT: f32 = 1.70158;
const OVERSHOOT_PLUS_ONE: f32 = 2.70158;

/// Where everything is, a given time into the animation.
#[derive(Debug, PartialEq)]
struct Pose {
    /// How solid the icon is, and how far it still has to turn, in radians.
    icon: f32,
    angle: f32,
    scale: f32,
    /// How far the name has appeared.
    name: f32,
}

/// Eases in and out: the smoothstep polynomial, 3x² - 2x³.
fn smooth(x: f32) -> f32 {
    let x = x.clamp(0.0, 1.0);

    x * x * (3.0 - 2.0 * x)
}

/// Eases out, going a little too far and coming back.
fn overshoot(x: f32) -> f32 {
    let x = x.clamp(0.0, 1.0) - 1.0;

    1.0 + OVERSHOOT_PLUS_ONE * x * x * x + OVERSHOOT * x * x
}

fn pose(seconds: f32) -> Pose {
    let roll = 1.0 - (1.0 - (seconds / ROLL_SECONDS).clamp(0.0, 1.0)).powi(ROLL_EASING_POWER);

    Pose {
        icon: smooth(seconds / ICON_FADE_SECONDS),
        angle: (1.0 - roll) * -START_ANGLE.to_radians(),
        // It grows as it arrives.
        scale: START_SCALE + SCALE_GAIN * overshoot(seconds / GROW_SECONDS),
        name: smooth((seconds - NAME_AT) / NAME_FADE_SECONDS),
    }
}

pub struct Splash {
    icon: TextureHandle,
    /// When the animation began, once it has.
    started: Option<f64>,
}

impl Splash {
    /// None if the icon cannot be shown, in which case there is no
    /// animation; it is not worth failing over.
    pub fn new(ctx: &egui::Context) -> Option<Self> {
        let image = image::load_from_memory(ICON).ok()?.to_rgba8();
        let size = [image.width() as usize, image.height() as usize];
        let icon = ctx.load_texture(
            "splash",
            egui::ColorImage::from_rgba_unmultiplied(size, image.as_raw()),
            TextureOptions::LINEAR,
        );

        Some(Self { icon, started: None })
    }

    fn seconds(&self, now: f64) -> f32 {
        self.started.map_or(0.0, |started| (now - started) as f32)
    }

    /// True while the animation is playing; what the user does then is not
    /// meant for the interface underneath, but cuts the animation short.
    pub fn blocks_input(&self, now: f64) -> bool {
        self.seconds(now) < END_AT
    }

    /// Ends the animation at once.
    pub fn skip(&mut self, now: f64) {
        self.started = Some(now - f64::from(END_AT));
    }

    /// Draws the animation over everything else. Returns false once it is
    /// over, and can be let go of.
    pub fn draw(&mut self, ctx: &egui::Context, painter: &Painter, screen: Rect, u: f32, now: f64) -> bool {
        // Sizes in units (one unit is one pixel on a 1080p screen).

        /// The icon: its size, and how far above the middle of the screen
        /// its centre is.
        const ICON_SIZE: f32 = 220.0;
        const ICON_RAISE: f32 = 44.0;

        /// The glow's brightness goes up and down around this, by this
        /// much either way, at this speed in radians per second.
        const GLOW_LEVEL: f32 = 0.75;
        const GLOW_SWING: f32 = 0.25;
        const GLOW_SPEED: f32 = 2.4;

        /// How solid the glow is at its middle (0 to 1), and how far it
        /// reaches, in icon sizes.
        const HALO_ALPHA: f32 = 0.3;
        const HALO_REACH: f32 = 1.25;

        /// Triangles the halo is made of.
        const SPOKES: u32 = 64;

        /// The name: its size, the extra space between its letters, how
        /// far below the middle of the screen it ends up, and how far it
        /// rises to get there.
        const NAME_SIZE: f32 = 44.0;
        const LETTER_SPACING: f32 = 13.0;
        const NAME_DROP: f32 = 104.0;
        const NAME_RISE: f32 = 16.0;

        let started = *self.started.get_or_insert(now);
        let seconds = (now - started) as f32;
        if seconds >= END_AT {
            return false;
        }

        ctx.request_repaint();

        let pose = pose(seconds);

        painter.rect_filled(screen, 0.0, BG);

        let center = screen.center() - vec2(0.0, ICON_RAISE * u);
        let size = ICON_SIZE * u * pose.scale;

        // The ball's glow, breathing behind the icon.
        let glow = pose.icon * (GLOW_LEVEL + GLOW_SWING * (seconds * GLOW_SPEED).sin());
        // A fan of triangles, bright in the middle and fading to nothing at
        // the rim, which shades evenly where rings would show as bands.
        let mut halo = egui::Mesh::default();

        halo.colored_vertex(center, draw::with_alpha(ACCENT, HALO_ALPHA * glow));

        for spoke in 0..SPOKES {
            let angle = std::f32::consts::TAU * spoke as f32 / SPOKES as f32;

            halo.colored_vertex(
                center + size * HALO_REACH * vec2(angle.cos(), angle.sin()),
                Color32::TRANSPARENT,
            );
            halo.add_triangle(0, 1 + spoke, 1 + (spoke + 1) % SPOKES);
        }

        painter.add(egui::Shape::mesh(halo));

        let mut mesh = egui::Mesh::with_texture(self.icon.id());

        mesh.add_rect_with_uv(
            Rect::from_center_size(center, vec2(size, size)),
            Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
            draw::with_alpha(Color32::WHITE, pose.icon),
        );
        mesh.rotate(Rot2::from_angle(pose.angle), center);
        painter.add(egui::Shape::mesh(mesh));

        // The name, letter by letter so that it can be spaced out, rising
        // into place as it appears.
        let color = draw::with_alpha(TEXT, pose.name);
        let font = draw::bold(NAME_SIZE * u);
        let letters: Vec<_> = "LUTRIS"
            .chars()
            .map(|letter| painter.layout_no_wrap(letter.to_string(), font.clone(), color))
            .collect();
        let spacing = LETTER_SPACING * u;
        let width: f32 =
            letters.iter().map(|letter| letter.size().x).sum::<f32>() + spacing * (letters.len() - 1) as f32;
        let mut x = screen.center().x - width / 2.0;
        let y = screen.center().y + NAME_DROP * u + (1.0 - pose.name) * NAME_RISE * u;

        for letter in letters {
            let advance = letter.size().x + spacing;

            painter.galley(pos2(x, y), letter, color);
            x += advance;
        }

        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_icon_rolls_in_and_is_named() {
        let start = pose(0.0);

        assert_eq!(start.icon, 0.0, "nothing to see at first");
        assert!(start.angle < -1.5, "turned well away");
        assert_eq!(start.name, 0.0);

        // Well before the end it has arrived, and stays as it is.
        for seconds in [1.3, END_AT] {
            let arrived = pose(seconds);

            assert_eq!(arrived.icon, 1.0);
            assert_eq!(arrived.angle, 0.0, "upright");
            assert!((arrived.scale - 1.0).abs() < 1e-4, "at its size");
            assert_eq!(arrived.name, 1.0, "and named");
        }

        // It only ever turns one way, and never past upright.
        let angles: Vec<f32> = (0..=20).map(|i| pose(i as f32 * 0.05).angle).collect();

        assert!(angles.windows(2).all(|pair| pair[0] <= pair[1] && pair[1] <= 0.0));
    }

    #[test]
    fn it_ends_in_one_cut_and_at_once_when_skipped() {
        let ctx = egui::Context::default();
        let mut splash = Splash::new(&ctx).unwrap();

        splash.started = Some(10.0);

        assert!(
            splash.blocks_input(10.0 + f64::from(END_AT) - 0.01),
            "there to the last"
        );
        assert!(!splash.blocks_input(10.0 + f64::from(END_AT)), "and then not at all");

        splash.started = Some(10.0);
        splash.skip(10.3);

        assert!(!splash.blocks_input(10.3));
    }

    #[test]
    fn the_icon_is_there_to_be_shown() {
        let image = image::load_from_memory(ICON).unwrap();

        assert_eq!((image.width(), image.height()), (768, 768));
    }
}
