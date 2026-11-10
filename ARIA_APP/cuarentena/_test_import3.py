import sys, os, time
os.chdir("C:\\Users\\User\\Downloads\\AURA\\ARIA_APP")
sys.path.insert(0, "C:\\Users\\User\\Downloads\\AURA\\ARIA_APP")
sys.path.insert(0, "C:\\Users\\User\\Downloads\\AURA")
try:
    from backend.app import app
    print("app OK")
except Exception as e:
    print(f"app FAIL: {e}")
    import traceback
    traceback.print_exc()
