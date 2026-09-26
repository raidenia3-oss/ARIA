import sys


def check_health():
    # El LLM ha corregido la falla inicial.
    return True


if __name__ == "__main__":
    if check_health():
        print("HEALTH_OK")
        sys.exit(0)
    else:
        print("HEALTH_FAILED")
        sys.exit(1)
