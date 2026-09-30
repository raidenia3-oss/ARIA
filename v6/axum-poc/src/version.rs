//! Single source of the ARIA OS version for the Rust runtime.
//!
//! GENERATED FILE. The literal below is rewritten from `pyproject.toml`
//! (`[project].version`) by `tools/sync_version.py` and checked by
//! `tools/verify_version.py`. Do not hand-edit it.

/// Canonical ARIA OS release version.
pub const ARIA_VERSION: &str = "6.0.0";

#[cfg(test)]
mod tests {
    use super::ARIA_VERSION;

    #[test]
    fn version_is_plain_semver() {
        let parts: Vec<&str> = ARIA_VERSION.split('.').collect();
        assert_eq!(parts.len(), 3, "expected MAJOR.MINOR.PATCH, got {ARIA_VERSION}");
        assert!(parts.iter().all(|p| p.parse::<u32>().is_ok()));
    }
}
