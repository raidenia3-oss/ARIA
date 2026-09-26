import subprocess, sys, time
proc = subprocess.Popen(
    [sys.executable, "test_ui2.py"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1
)
time.sleep(5)
proc.terminate()
out, err = proc.communicate(timeout=3)
print("STDOUT:", out[-500:])
print("STDERR:", err[-500:])