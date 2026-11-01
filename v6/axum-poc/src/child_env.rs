use std::collections::BTreeSet;
use tokio::process::Command;

/// Variables que un hijo necesita legitimamente para arrancar.
///
/// El padre hereda ARIA_API_KEY y DISCORD_WEBHOOK_*; esos NO deben llegar
/// al hijo. La allowlist es la primera línea de defensa; el filtro por
/// patrón (secret_pattern) es defensa en profundidad para secretos futuros
/// que alguien añada a ALLOWED por error.
const ALLOWED: &[&str] = &[
    "PATH", "PATHEXT", "SystemRoot", "SystemDrive", "COMSPEC", "WINDIR",
    "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE",
    "HOMEDRIVE", "HOMEPATH", "USERNAME", "USERDOMAIN",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "COMPUTERNAME",
    "HOME", "LANG", "LC_ALL", "TZ", "SHELL",
    "ARIA_HOME", "ARIA_MODEL", "ARIA_OLLAMA_URL", "ARIA_LOG_LEVEL",
    "ARIA_VIDEO_DIR", "ARIA_VIDEO_MAX_CONCURRENT",
    "ARIA_DB_PATH", "ARIA_USB_PATH", "ARIA_VIDEO_SOURCES",
    "PYTHONPATH", "PYTHONUNBUFFERED",
    "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE",
    "NO_COLOR", "TERM",
];

pub fn sanitize(cmd: &mut Command) {
    rebuild_env(cmd.as_std_mut());
}

/// Reconstruye el entorno del hijo desde ALLOWED.
///
/// Punto único de verdad: lo llama tanto sanitize() como los tests.
fn rebuild_env(cmd: &mut std::process::Command) {
    cmd.env_clear();
    let mut seen = BTreeSet::new();
    for key in ALLOWED {
        if !seen.insert(*key) { continue; }
        if secret_pattern(key) { continue; }
        if let Ok(value) = std::env::var(key) {
            cmd.env(key, value);
        }
    }
}

/// Defensa en profundidad: aunque un secreto futuro entre en ALLOWED por
/// error, este filtro lo retiene. La allowlist sigue siendo la primera
/// línea de defensa (deny-list sola no conoce los secretos de mañana).
fn secret_pattern(key: &str) -> bool {
    let k = key.to_ascii_uppercase();
    k.ends_with("_API_KEY")
        || k.ends_with("_TOKEN")
        || k.ends_with("_SECRET")
        || k.ends_with("_PASSWORD")
        || k.ends_with("_WEBHOOK")
        || k.contains("WEBHOOK")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, OnceLock};

    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    fn env_lock() -> &'static Mutex<()> {
        ENV_LOCK.get_or_init(|| Mutex::new(()))
    }

    #[test]
    fn secrets_are_never_forwarded() {
        for s in ["ARIA_API_KEY", "DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK_SECRET", "DISCORD_WEBHOOK"] {
            assert!(!ALLOWED.contains(&s), "{s} nunca debe reenviarse");
            assert!(secret_pattern(s), "{s} debe caer en el filtro por patrón");
        }
        // Defensa en profundidad: secretos futuros hipotéticos.
        for s in ["OPENAI_API_KEY", "GITHUB_TOKEN", "DB_SECRET", "ADMIN_PASSWORD", "HOOK_WEBHOOK"] {
            assert!(secret_pattern(s), "{s} debe caer en el filtro por patrón");
        }
        // No-secretos legítimos no deben filtrarse.
        for s in ["ARIA_DB_PATH", "PATH", "PYTHONPATH", "TERM"] {
            assert!(!secret_pattern(s), "{s} no es secreto");
        }
    }

    #[test]
    fn allowlist_has_no_duplicates() {
        let set: BTreeSet<_> = ALLOWED.iter().collect();
        assert_eq!(set.len(), ALLOWED.len(), "entrada duplicada en ALLOWED");
    }

    #[test]
    fn sanitized_child_still_runs() {
        // Edition 2021: set_var es safe. Mutex porque el env del proceso
        // de test es compartido entre tests paralelos.
        let _guard = env_lock().lock().unwrap();
        let prev_key = std::env::var("ARIA_API_KEY").ok();
        std::env::set_var("ARIA_API_KEY", "super-secret");
        std::env::set_var("ARIA_TEST_ALLOWLIST_PROBE", "probe-value");
        let result = (|| -> bool {
            // std (sync): tokio::process::Command::status() es async.
            // rebuild_env() opera sobre std::process::Command: punto único
            // de verdad compartido con sanitize().
            let mut cmd = if cfg!(windows) {
                let mut c = std::process::Command::new("cmd");
                c.args(["/C", "echo %ARIA_API_KEY%|findstr super-secret >NUL && exit 1 || exit 0"]);
                c
            } else {
                let mut c = std::process::Command::new("sh");
                c.args(["-c", "test -z \"$ARIA_API_KEY\""]);
                c
            };
            rebuild_env(&mut cmd);
            cmd.stdin(std::process::Stdio::null())
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        })();
        std::env::remove_var("ARIA_TEST_ALLOWLIST_PROBE");
        match prev_key {
            Some(v) => std::env::set_var("ARIA_API_KEY", v),
            None => std::env::remove_var("ARIA_API_KEY"),
        }
        assert!(result, "el hijo sanitizado debe arrancar sin ver ARIA_API_KEY");
    }

    #[test]
    fn rebuild_env_drops_secrets_from_the_real_builder() {
        let _guard = env_lock().lock().unwrap();
        let prev = std::env::var("ARIA_API_KEY").ok();
        let prev_db = std::env::var("ARIA_DB_PATH").ok();
        let prev_hook = std::env::var("DISCORD_WEBHOOK_URL").ok();
        std::env::set_var("ARIA_API_KEY", "leak-me-not");
        std::env::set_var("ARIA_DB_PATH", "db-value-ok");
        std::env::set_var("DISCORD_WEBHOOK_URL", "hook-leak-no");

        let mut cmd = std::process::Command::new("unused");
        rebuild_env(&mut cmd);

        let envs: Vec<_> = cmd.get_envs().collect();
        assert!(
            !envs.iter().any(|(k, _)| *k == "ARIA_API_KEY"),
            "ARIA_API_KEY present in child environment"
        );
        assert!(
            !envs.iter().any(|(k, _)| *k == "DISCORD_WEBHOOK_URL"),
            "DISCORD_WEBHOOK_URL present in child environment"
        );
        assert!(
            envs.iter().any(|(k, v)| *k == "ARIA_DB_PATH" && *v == Some(std::ffi::OsStr::new("db-value-ok"))),
            "ARIA_DB_PATH missing: el hijo lo necesita y no es secreto"
        );
        assert!(
            envs.iter().any(|(k, _)| *k == "PATH"),
            "PATH missing: child cannot start on Windows"
        );

        match prev {
            Some(v) => std::env::set_var("ARIA_API_KEY", v),
            None => std::env::remove_var("ARIA_API_KEY"),
        }
        match prev_db {
            Some(v) => std::env::set_var("ARIA_DB_PATH", v),
            None => std::env::remove_var("ARIA_DB_PATH"),
        }
        match prev_hook {
            Some(v) => std::env::set_var("DISCORD_WEBHOOK_URL", v),
            None => std::env::remove_var("DISCORD_WEBHOOK_URL"),
        }
    }
}
