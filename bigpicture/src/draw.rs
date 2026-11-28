//! Drawing helpers shared by the screens: colours, fonts, text and tiles.

use std::sync::Arc;

use eframe::egui::{
    self, epaint, pos2, vec2, Align2, Color32, FontFamily, FontId, Galley, Painter, Pos2, Rect, Stroke, StrokeKind,
};

use crate::covers::CoverCache;
use crate::input::Glyph;
use crate::protocol::{Game, RunState};

pub const BG: Color32 = Color32::from_rgb(11, 14, 20);
pub const PANEL: Color32 = Color32::from_rgb(24, 29, 40);
pub const PANEL_HI: Color32 = Color32::from_rgb(40, 47, 63);
pub const TEXT: Color32 = Color32::from_rgb(240, 242, 246);
pub const DIM: Color32 = Color32::from_rgb(150, 158, 172);
pub const ACCENT: Color32 = Color32::from_rgb(255, 152, 0);
pub const GOOD: Color32 = Color32::from_rgb(96, 208, 120);
pub const BAD: Color32 = Color32::from_rgb(150, 40, 40);

/// The badge behind a key or button name in a hint.
const HINT_BADGE: Color32 = Color32::from_rgb(214, 218, 226);

/// How far the focus ring stands off what it surrounds, and how thick it
/// is, in units (one unit is one pixel on a 1080p screen).
pub const FOCUS_RING_GAP: f32 = 4.0;
pub const FOCUS_RING_WIDTH: f32 = 3.0;

/// The bits of fontconfig's font index that number the face in the file.
const FACE_INDEX_MASK: u32 = 0xffff;

const BOLD_FAMILY: &str = "bold";

pub fn regular(size: f32) -> FontId {
    FontId::new(size, FontFamily::Proportional)
}

pub fn bold(size: f32) -> FontId {
    FontId::new(size, FontFamily::Name(BOLD_FAMILY.into()))
}

/// Uses the system's interface font, so the look matches the desktop and bold
/// text is available. Falls back on the built-in font if it cannot be found.
pub fn setup_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();

    if let Some(data) = system_font("sans-serif:weight=regular") {
        fonts.font_data.insert("ui".to_owned(), Arc::new(data));
        fonts
            .families
            .entry(FontFamily::Proportional)
            .or_default()
            .insert(0, "ui".to_owned());
    }

    let mut bold_fonts = fonts
        .families
        .get(&FontFamily::Proportional)
        .cloned()
        .unwrap_or_default();
    if let Some(data) = system_font("sans-serif:weight=bold") {
        fonts.font_data.insert("ui-bold".to_owned(), Arc::new(data));
        bold_fonts.insert(0, "ui-bold".to_owned());
    }

    fonts.families.insert(FontFamily::Name(BOLD_FAMILY.into()), bold_fonts);
    ctx.set_fonts(fonts);
}

fn system_font(pattern: &str) -> Option<egui::FontData> {
    let output = std::process::Command::new("fc-match")
        .args(["-f", "%{file}\n%{index}", pattern])
        .output()
        .ok()?;
    let text = String::from_utf8(output.stdout).ok()?;
    let mut lines = text.lines();
    let file = lines.next()?;
    let index: u32 = lines.next()?.trim().parse().ok()?;
    let lower = file.to_ascii_lowercase();
    if !(lower.ends_with(".ttf") || lower.ends_with(".otf") || lower.ends_with(".ttc")) {
        return None;
    }

    let mut data = egui::FontData::from_owned(std::fs::read(file).ok()?);

    // The upper bits select a named instance of a variable font.
    data.index = index & FACE_INDEX_MASK;

    Some(data)
}

pub fn with_alpha(color: Color32, alpha: f32) -> Color32 {
    color.gamma_multiply(alpha.clamp(0.0, 1.0))
}

/// Lays out text limited to `rows` rows of `max_width`, ending in an ellipsis
/// if it does not fit.
pub fn fit_text(
    painter: &Painter,
    text: &str,
    font: FontId,
    color: Color32,
    max_width: f32,
    rows: usize,
) -> Arc<Galley> {
    let mut job = epaint::text::LayoutJob::simple(text.to_owned(), font, color, max_width);

    job.wrap.max_rows = rows;
    job.wrap.break_anywhere = rows == 1;
    job.wrap.overflow_character = Some('…');

    painter.layout_job(job)
}

/// The part of a texture to show so that it fills `rect` without distortion.
pub fn cover_uv(image_aspect: f32, rect: Rect) -> Rect {
    let rect_aspect = rect.width() / rect.height().max(1.0);
    if image_aspect > rect_aspect {
        let width = rect_aspect / image_aspect;

        Rect::from_min_max(pos2(0.5 - width / 2.0, 0.0), pos2(0.5 + width / 2.0, 1.0))
    } else {
        let height = image_aspect / rect_aspect;

        Rect::from_min_max(pos2(0.0, 0.5 - height / 2.0), pos2(1.0, 0.5 + height / 2.0))
    }
}

pub fn textured_rect(painter: &Painter, rect: Rect, radius: f32, texture: egui::TextureId, uv: Rect, tint: Color32) {
    painter.add(epaint::RectShape::filled(rect, radius, tint).with_texture(texture, uv));
}

pub fn focus_ring(painter: &Painter, rect: Rect, radius: f32, u: f32, strength: f32) {
    if strength <= 0.0 {
        return;
    }

    painter.rect_stroke(
        rect.expand(FOCUS_RING_GAP * u),
        radius + FOCUS_RING_GAP * u,
        Stroke::new(FOCUS_RING_WIDTH * u, with_alpha(Color32::WHITE, strength)),
        StrokeKind::Outside,
    );
}

/// A stable colour for a game without a cover, derived from its name.
fn placeholder_color(name: &str) -> Color32 {
    /// The starting value and the multiplier of the 64-bit FNV-1a hash.
    const FNV_OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;
    const FNV_PRIME: u64 = 0x0100_0000_01b3;

    /// How many different hues there are to pick from.
    const HUES: u64 = 360;

    /// Muted and dark, so the name can be read on it (0 to 1).
    const SATURATION: f32 = 0.45;
    const VALUE: f32 = 0.32;

    let hash = name
        .bytes()
        .fold(FNV_OFFSET_BASIS, |h, b| (h ^ u64::from(b)).wrapping_mul(FNV_PRIME));

    let hue = (hash % HUES) as f32 / HUES as f32;

    egui::ecolor::Hsva::new(hue, SATURATION, VALUE, 1.0).into()
}

/// Draws a game's cover in `rect`, growing with `focus` (0 to 1).
pub fn game_tile(painter: &Painter, covers: &mut CoverCache, game: &Game, rect: Rect, focus: f32, u: f32) {
    // Sizes in units.

    /// How much of its size the tile gains when focused.
    const FOCUS_GROWTH: f32 = 0.07;
    const RADIUS: f32 = 10.0;

    /// The shadow under a focused tile: how far down, how soft, how dark.
    const SHADOW_OFFSET: f32 = 10.0;
    const SHADOW_BLUR: f32 = 36.0;
    const SHADOW_ALPHA: f32 = 0.7;

    /// The name on a tile without a cover.
    const NAME_SIZE: f32 = 22.0;
    const NAME_PADDING: f32 = 14.0;
    const NAME_ROWS: usize = 4;

    /// The dot marking a running game: its distance from the tile's corner,
    /// its radius, and the dark ring around it.
    const DOT_INSET: f32 = 22.0;
    const DOT_RADIUS: f32 = 7.0;
    const DOT_RING_RADIUS: f32 = 11.0;
    const DOT_RING_ALPHA: f32 = 0.6;

    let rect = Rect::from_center_size(rect.center(), rect.size() * (1.0 + FOCUS_GROWTH * focus));
    let radius = RADIUS * u;

    if focus > 0.0 {
        let shadow = epaint::Shadow {
            offset: [0, (SHADOW_OFFSET * u) as i8],
            blur: (SHADOW_BLUR * u).min(f32::from(u8::MAX)) as u8,
            spread: 0,
            color: with_alpha(Color32::BLACK, SHADOW_ALPHA * focus),
        };

        painter.add(shadow.as_shape(rect, radius));
    }

    let cover = game.cover.as_deref().and_then(|path| covers.get(path));
    if let Some(cover) = cover {
        let uv = cover_uv(cover.aspect, rect);

        textured_rect(painter, rect, radius, cover.texture.id(), uv, Color32::WHITE);
    } else {
        painter.rect_filled(rect, radius, placeholder_color(&game.name));

        // With no cover on file the name is all there is to show; while one
        // is still loading it would only flicker.
        if game.cover.is_none() {
            let width = rect.width() - 2.0 * NAME_PADDING * u;
            let galley = fit_text(painter, &game.name, bold(NAME_SIZE * u), TEXT, width, NAME_ROWS);
            let pos = rect.center() - galley.size() / 2.0;

            painter.galley(pos, galley, TEXT);
        }
    }

    if game.state != RunState::Stopped {
        let center = rect.left_top() + vec2(DOT_INSET * u, DOT_INSET * u);

        painter.circle_filled(center, DOT_RING_RADIUS * u, with_alpha(Color32::BLACK, DOT_RING_ALPHA));
        painter.circle_filled(center, DOT_RADIUS * u, GOOD);
    }

    focus_ring(painter, rect, radius, u, focus);
}

/// A button hint such as "(A) Select". Returns the x where it starts, so the
/// next one can be placed to its left.
pub fn hint(painter: &Painter, right: Pos2, glyph: Glyph, label: &str, u: f32) -> f32 {
    // Sizes in units.
    const LABEL_SIZE: f32 = 22.0;
    const BADGE_HEIGHT: f32 = 34.0;
    const BADGE_TEXT_SIZE: f32 = 18.0;

    /// Space on either side of the text in a badge.
    const BADGE_PADDING: f32 = 9.0;

    /// Space between the badge and its label.
    const BADGE_GAP: f32 = 10.0;

    /// A controller symbol's size from its centre, and its line width.
    const SYMBOL_SIZE: f32 = 7.5;
    const SYMBOL_STROKE: f32 = 2.6;

    let label_galley = painter.layout_no_wrap(label.to_owned(), regular(LABEL_SIZE * u), DIM);
    let height = BADGE_HEIGHT * u;
    let label_x = right.x - label_galley.size().x;
    let glyph_left = match glyph {
        Glyph::Text(text) => {
            let glyph_galley = painter.layout_no_wrap(text.to_owned(), bold(BADGE_TEXT_SIZE * u), BG);
            let width = (glyph_galley.size().x + 2.0 * BADGE_PADDING * u).max(height);
            let rect = Rect::from_min_size(
                pos2(label_x - BADGE_GAP * u - width, right.y - height / 2.0),
                vec2(width, height),
            );

            painter.rect_filled(rect, height / 2.0, HINT_BADGE);
            painter.galley(rect.center() - glyph_galley.size() / 2.0, glyph_galley, BG);
            rect.left()
        }
        symbol => {
            let center = pos2(label_x - BADGE_GAP * u - height / 2.0, right.y);

            painter.circle_filled(center, height / 2.0, HINT_BADGE);
            pad_symbol(
                painter,
                center,
                symbol,
                SYMBOL_SIZE * u,
                Stroke::new(SYMBOL_STROKE * u, BG),
            );
            center.x - height / 2.0
        }
    };

    painter.galley(pos2(label_x, right.y - label_galley.size().y / 2.0), label_galley, DIM);

    glyph_left
}

/// Draws one of the symbols on a PlayStation controller's buttons. They are
/// drawn rather than written, as fonts cannot be relied on to have them.
fn pad_symbol(painter: &Painter, center: Pos2, symbol: Glyph, size: f32, stroke: Stroke) {
    // Proportions of `size`, chosen so the symbols look equally large.
    const CROSS_ARM: f32 = 0.85;
    const SQUARE_HALF_SIDE: f32 = 0.9;
    const TRIANGLE_TOP: f32 = 1.1;
    const TRIANGLE_HALF_BASE: f32 = 1.05;
    const TRIANGLE_BOTTOM: f32 = 0.72;

    match symbol {
        Glyph::Cross => {
            let arm = size * CROSS_ARM;

            painter.line_segment([center + vec2(-arm, -arm), center + vec2(arm, arm)], stroke);
            painter.line_segment([center + vec2(-arm, arm), center + vec2(arm, -arm)], stroke);
        }
        Glyph::Circle => {
            painter.circle_stroke(center, size, stroke);
        }
        Glyph::Square => {
            let side = size * SQUARE_HALF_SIDE;

            painter.rect_stroke(
                Rect::from_center_size(center, vec2(2.0 * side, 2.0 * side)),
                0.0,
                stroke,
                StrokeKind::Middle,
            );
        }
        Glyph::Triangle => {
            // Centred on its middle, not on its bounding box, so that it
            // looks centred.
            let points = vec![
                center + vec2(0.0, -size * TRIANGLE_TOP),
                center + vec2(size * TRIANGLE_HALF_BASE, size * TRIANGLE_BOTTOM),
                center + vec2(-size * TRIANGLE_HALF_BASE, size * TRIANGLE_BOTTOM),
            ];

            painter.add(epaint::Shape::closed_line(points, stroke));
        }
        Glyph::Text(_) => {}
    }
}

/// A rounded button with centred text; returns nothing, the caller knows the rect.
pub fn button(painter: &Painter, rect: Rect, label: &str, fill: Color32, text_color: Color32, focus: f32, u: f32) {
    // Sizes in units.

    /// How much of its size the button gains when focused.
    const FOCUS_GROWTH: f32 = 0.04;
    const RADIUS: f32 = 12.0;
    const TEXT_SIZE: f32 = 26.0;

    /// Space kept free on either side of the text.
    const PADDING: f32 = 12.0;

    let rect = Rect::from_center_size(rect.center(), rect.size() * (1.0 + FOCUS_GROWTH * focus));
    let radius = RADIUS * u;

    painter.rect_filled(rect, radius, fill);

    let width = rect.width() - 2.0 * PADDING * u;
    let galley = fit_text(painter, label, bold(TEXT_SIZE * u), text_color, width, 1);

    painter.galley(rect.center() - galley.size() / 2.0, galley, text_color);
    focus_ring(painter, rect, radius, u, focus);
}

pub fn text(painter: &Painter, pos: Pos2, anchor: Align2, text: &str, font: FontId, color: Color32) -> Rect {
    painter.text(pos, anchor, text, font, color)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wide_image_in_tall_rect_is_cropped_at_the_sides() {
        let rect = Rect::from_min_size(pos2(0.0, 0.0), vec2(100.0, 200.0));
        let uv = cover_uv(2.0, rect);

        assert!((uv.width() - 0.25).abs() < 1e-6);
        assert!((uv.height() - 1.0).abs() < 1e-6);
        assert!((uv.center().x - 0.5).abs() < 1e-6);
    }

    #[test]
    fn tall_image_in_wide_rect_is_cropped_top_and_bottom() {
        let rect = Rect::from_min_size(pos2(0.0, 0.0), vec2(200.0, 100.0));
        let uv = cover_uv(0.5, rect);

        assert!((uv.width() - 1.0).abs() < 1e-6);
        assert!((uv.height() - 0.25).abs() < 1e-6);
    }

    #[test]
    fn matching_aspect_shows_the_whole_image() {
        let rect = Rect::from_min_size(pos2(0.0, 0.0), vec2(300.0, 400.0));
        let uv = cover_uv(0.75, rect);

        assert!((uv.width() - 1.0).abs() < 1e-6 && (uv.height() - 1.0).abs() < 1e-6);
    }
}
