"""
Sube las paginas web a GitHub Pages (gratis, sin servidor).
URL resultante: https://tu-usuario.github.io/aura-tools/
Esa URL se registra en Adsterra para monetizar.
"""


def deploy():
    print("Desplegando paginas web a GitHub Pages...")
    print()
    print("PASOS:")
    print("1. Crear repo en GitHub llamado 'aura-tools'")
    print("2. Ejecutar estos comandos:")
    print()

    commands = [
        "cd web_pages",
        "git init",
        "git add .",
        'git commit -m "AURA Tools - Paginas web"',
        "git branch -M main",
        "git remote add origin https://github.com/TU_USUARIO/aura-tools.git",
        "git push -u origin main",
    ]

    for cmd in commands:
        print(f"  $ {cmd}")

    print()
    print("3. En GitHub -> Settings -> Pages -> Source: main branch")
    print("4. URL: https://TU_USUARIO.github.io/aura-tools/")
    print()
    print("5. Registrar esa URL en Adsterra:")
    print("   beta.publishers.adsterra.com -> Agregar Sitio Web")
    print("   URL: https://TU_USUARIO.github.io/aura-tools/")
    print("   Categoria: Technology")
    print()
    print("6. Adsterra revisara el sitio (1-3 dias)")
    print("7. Cuando aprueben, copiar el codigo de anuncio")
    print("   y reemplazar los comentarios en index.html")


if __name__ == "__main__":
    deploy()
