import pathlib

code = r'''// Axum v6.0 backend - POC
fn main() { println!("test"); }
'''

pathlib.Path(r'C:\Users\User\Downloads\AURA\aria-backend-axum\src\main.rs').write_text(code)
print('OK')