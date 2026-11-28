//! Lutris Big Picture: a fullscreen, controller-friendly view of the Lutris
//! library. It is the user interface only - Lutris starts it, feeds it the
//! library and carries out what the user asks for (see `protocol`).

mod app;
mod covers;
mod draw;
mod input;
mod protocol;
mod sounds;
mod splash;

use std::io::IsTerminal;

use eframe::egui;

const USAGE: &str = "\
Usage: lutris-bigpicture [OPTIONS]

The Big Picture interface of Lutris. It is started by Lutris itself: use the
Big Picture button in the Lutris window, or run `lutris --big-picture`.

Options:
  --windowed         Run in a window instead of fullscreen
  --no-splash        Start without the opening animation
  --debug-protocol   Accept the test messages of the protocol
  -h, --help         Show this help
  -V, --version      Show the version";

/// Size of the window in points, when not fullscreen.
const WINDOW_SIZE: [f32; 2] = [1280.0, 720.0];

/// Exit status when started wrongly: with an unknown option, or by hand.
const EXIT_USAGE: i32 = 2;

fn main() -> eframe::Result {
    let mut windowed = false;
    let mut debug_protocol = false;
    let mut splash = true;

    for arg in std::env::args().skip(1) {
        match arg.as_str() {
            "--windowed" => windowed = true,
            "--debug-protocol" => debug_protocol = true,
            "--no-splash" => splash = false,
            "-h" | "--help" => {
                println!("{USAGE}");

                return Ok(());
            }
            "-V" | "--version" => {
                println!("lutris-bigpicture {}", env!("CARGO_PKG_VERSION"));

                return Ok(());
            }
            other => {
                eprintln!("lutris-bigpicture: unknown option '{other}'\n\n{USAGE}");
                std::process::exit(EXIT_USAGE);
            }
        }
    }

    if std::io::stdin().is_terminal() {
        eprintln!("{USAGE}");
        std::process::exit(EXIT_USAGE);
    }

    let viewport = egui::ViewportBuilder::default()
        .with_title("Lutris Big Picture")
        // Sharing the application ID gives the window the Lutris icon.
        .with_app_id("net.lutris.Lutris")
        .with_inner_size(WINDOW_SIZE)
        .with_fullscreen(!windowed)
        .with_decorations(windowed);
    let options = eframe::NativeOptions {
        viewport,
        ..Default::default()
    };

    eframe::run_native(
        "lutris-bigpicture",
        options,
        Box::new(move |cc| Ok(Box::new(app::App::new(cc, splash, debug_protocol)))),
    )?;

    if app::QUIT_LUTRIS.load(std::sync::atomic::Ordering::Relaxed) {
        std::process::exit(protocol::EXIT_QUIT_LUTRIS);
    }

    Ok(())
}
