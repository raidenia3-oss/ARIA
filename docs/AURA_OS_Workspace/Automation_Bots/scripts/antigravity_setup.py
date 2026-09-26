"""
antigravity_setup.py - Configura Google Antigravity/Gemini para AURA (gratis)
"""
import subprocess, os, sys

def check_installed():
    try:
        import google.generativeai
        print("✅ google-generativeai instalado")
        return True
    except ImportError:
        print("❌ Instalando dependencias...")
        subprocess.run([sys.executable, "-m", "pip", "install",
                       "google-generativeai", "python-dotenv", "websockets"])
        return True

def setup_free_tier():
    """Configura Gemini gratis (sin tarjeta de crédito)"""
    print("\n=== CONFIGURACIÓN GEMINI GRATUITA ===")
    print("1. Ve a: https://aistudio.google.com/apikey")
    print("2. Click 'Create API Key'")
    print("3. Copia la API key")

    api_key = input("\nPega tu API key (o Enter para saltar): ").strip()

    if api_key:
        env_path = ".env"
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path) as f:
                env_content = f.read()

        if "ANTIGRAVITY_API_KEY" not in env_content:
            with open(env_path, "a") as f:
                f.write(f"\nANTIGRAVITY_API_KEY={api_key}\n")
                f.write("ANTIGRAVITY_MODEL=gemini-2.0-flash\n")
            print("✅ API key guardada en .env")
        else:
            print("✅ API key ya configurada")
    else:
        print("⚠️  Sin API key. Configura después editando .env")

def test_connection():
    """Prueba que la API key funciona"""
    api_key = os.environ.get("ANTIGRAVITY_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key and os.path.exists(".env"):
        for line in open(".env"):
            if "ANTIGRAVITY_API_KEY" in line:
                api_key = line.split("=", 1)[1].strip()
                break

    if not api_key:
        print("❌ Sin API key configurada")
        return False

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content("Di solo: AURA conectado")
        print(f"✅ Conexión OK: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    check_installed()
    setup_free_tier()
    print("\n=== TEST DE CONEXIÓN ===")
    from dotenv import load_dotenv
    load_dotenv()
    test_connection()
    print("\n✅ Setup completo.")
    print("Próximo paso: python scripts/antigravity_bridge.py --task 'hola'")