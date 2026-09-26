use tauri::{
    Manager, Runtime, Window, WindowBuilder,
};
use tauri_plugin_positioner::PositionerBuilder;
use tauri_plugin_single_instance::SingleInstanceState;
use tauri::SystemTray;
use tauri::SystemTrayMenu;
use tauri::SystemTrayMenuItem;

fn main() {
    let quit = SystemTrayMenuItem::new("quit".to_string(), "Salir");
    let tray_menu = SystemTrayMenu::new()
        .with_items(vec![quit]);

    let system_tray = SystemTray::new()
        .with_menu(tray_menu);

    tauri::Builder::default()
        .plugin(tauri_plugin_positioner::init())
        .plugin(tauri_plugin_single_instance::init(SingleInstanceState::default()))
        .system_tray(system_tray)
        .setup(|app| {
            let window = app.get_window("main").unwrap();

            // Configurar ventana sin bordes (frameless)
            window.set_decorations(false).unwrap();
            window.set_always_on_top(true).unwrap();

            // Configurar tamaño y posición inicial
            window.set_size(tauri::Size::Logical(tauri::LogicalSize {
                width: 1200.0,
                height: 800.0,
            })).unwrap();

            // Configurar esquinas redondeadas
            window.set_rounded_corner_radius(12.0).unwrap();

            // Configurar icono de la aplicación
            let icon_path = std::path::Path::new("assets/icon.png");
            if icon_path.exists() {
                window.set_window_icon(Some(icon_path)).unwrap();
            }

            // Configurar evento para minimizar a la bandeja del sistema
            app.handle_window_event(|window, event| {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    window.hide().unwrap();
                    window.set_always_on_top(false).unwrap();
                    event.prevent_close();
                }
            });

            Ok(())
        })
        .on_system_tray_event(|app, event| {
            if let tauri::SystemTrayEvent::MenuItemClick { id, .. } = event {
                if id == "quit" {
                    std::process::exit(0);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}