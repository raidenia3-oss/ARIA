path = r"ARIA_APP\desktop_ui.py"
c = open(path, encoding="utf-8", errors="ignore").read()
header = "_start_heartbeat = lambda *a,**k: None\n_stop_heartbeat = lambda *a,**k: None\n_autonomy_runtime=None\n_beat_summary=lambda: {}\n_episode_line=lambda: \"\"\n_goal_line=lambda: \"\"\n_last_episode=lambda: None\n_lesson_line=lambda: \"\"\n_autonomy_mode=lambda: \"off\"\n"
if "_start_heartbeat" not in c[:500]:
    c2 = header + c
    open(path, "w", encoding="utf-8").write(c2)
    print("added")
else:
    print("ok")
