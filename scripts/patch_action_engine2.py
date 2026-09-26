p = 'backend/services/action_engine.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

old_run_tool = '''    def _run_tool(self, tool: ToolDefinition, params: Dict[str, Any]) -> Any:
        name = tool.name
        if name == "run_command":
            return self._tool_run_command(params)
        if name == "launch_app":
            return self._tool_launch_app(params)
        if name == "list_directory":
            return self._tool_list_directory(params)
        if name == "read_file":
            return self._tool_read_file(params)
        if name == "write_file":
            return self._tool_write_file(params)
        if name == "delete_path":
            return self._tool_delete_path(params)
        if name == "web_fetch":
            return self._tool_web_fetch(params)
        if name == "open_url":
            return self._tool_open_url(params)
        raise ValueError(f"Herramienta no implementada: {name}")'''

new_run_tool = '''    def _run_tool(self, tool: ToolDefinition, params: Dict[str, Any]) -> Any:
        name = tool.name
        if name == "run_command":
            return self._tool_run_command(params)
        if name == "launch_app" or name == "system.open":
            return self._tool_launch_app(params)
        if name == "list_directory" or name == "files.list":
            return self._tool_list_directory(params)
        if name == "read_file" or name == "files.read":
            return self._tool_read_file(params)
        if name == "write_file" or name == "files.write":
            return self._tool_write_file(params)
        if name == "delete_path":
            return self._tool_delete_path(params)
        if name == "web_fetch" or name == "browser.read":
            return self._tool_web_fetch(params)
        if name == "open_url" or name == "browser.open":
            return self._tool_open_url(params)
        if name == "browser.search":
            return self._tool_browser_search(params)
        if name == "browser.screenshot" or name == "system.screenshot":
            return self._tool_screenshot(params)
        if name == "browser.wait":
            return self._tool_wait(params)
        if name == "files.move":
            return self._tool_files_move(params)
        if name == "files.organize":
            return self._tool_files_organize(params)
        if name == "system.status":
            return self._tool_system_status()
        if name == "system.apps":
            return self._tool_system_apps(params)
        if name == "automation.create":
            return self._tool_automation_create(params)
        if name == "automation.run":
            return self._tool_automation_run(params)
        if name == "automation.cancel":
            return self._tool_automation_cancel(params)
        if name == "memory.remember":
            return self._tool_memory_remember(params)
        if name == "memory.search":
            return self._tool_memory_search(params)
        raise ValueError(f"Herramienta no implementada: {name}")'''

text = text.replace(old_run_tool, new_run_tool)

extra_methods = '''
    def _tool_browser_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = str(params.get("query", "")).strip()
        if not query:
            return {"results": [], "error": "query_required"}
        url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        return self._tool_web_fetch({"url": url})

    def _tool_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import pyautogui
            img = pyautogui.screenshot()
            return {"captured": True, "width": img.width, "height": img.height, "mode": img.mode}
        except Exception as exc:
            return {"captured": False, "error": str(exc)}

    def _tool_wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import time as _time
        seconds = float(params.get("seconds", 1))
        _time.sleep(seconds)
        return {"waited": True, "seconds": seconds}

    def _tool_files_move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src = str(params.get("src", "")).strip()
        dst = str(params.get("dst", "")).strip()
        try:
            import shutil
            shutil.move(src, dst)
            return {"moved": True, "src": src, "dst": dst}
        except Exception as exc:
            return {"moved": False, "error": str(exc)}

    def _tool_files_organize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        base = str(params.get("path", ".")).strip()
        moved = 0
        try:
            for name in os.listdir(base):
                full = os.path.join(base, name)
                if os.path.isfile(full):
                    ext = os.path.splitext(name)[1].lower().strip(".") or "unknown"
                    target_dir = os.path.join(base, ext)
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.move(full, os.path.join(target_dir, name))
                    moved += 1
            return {"organized": True, "moved": moved, "path": base}
        except Exception as exc:
            return {"organized": False, "moved": moved, "error": str(exc)}

    def _tool_system_status(self) -> Dict[str, Any]:
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": psutil.disk_usage(os.path.expanduser("~"))._asdict(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _tool_system_apps(self, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(params.get("limit", 20))
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                procs.append(p.info)
            return {"apps": procs[:limit]}
        except Exception as exc:
            return {"apps": [], "error": str(exc)}

    def _tool_automation_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            name = str(params.get("name", "")).strip()
            goal = str(params.get("goal", "")).strip()
            steps = params.get("steps", [])
            if not name or not steps:
                return {"created": False, "error": "name and steps are required"}
            result = asyncio.get_event_loop().run_until_complete(
                task_manager.learn_procedure(name, steps, goal)
            )
            return {"created": True, "procedure": result}
        except Exception as exc:
            return {"created": False, "error": str(exc)}

    def _tool_automation_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            proc_id = str(params.get("procedure_id", "")).strip()
            proc = asyncio.get_event_loop().run_until_complete(task_manager.get_learned_procedure(proc_id))
            if not proc:
                return {"started": False, "error": "procedure_not_found"}
            steps = proc.get("steps", [])
            task = asyncio.get_event_loop().run_until_complete(
                task_manager.create_task(name=proc["name"], action_type="automation", goal=proc["goal"], parameters={"procedure_id": proc_id})
            )
            asyncio.get_event_loop().run_until_complete(task_manager.start_task(task.task_id, steps))
            asyncio.get_event_loop().run_until_complete(task_manager.increment_procedure_execution(proc_id))
            return {"started": True, "task_id": task.task_id}
        except Exception as exc:
            return {"started": False, "error": str(exc)}

    def _tool_automation_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            task_id = str(params.get("task_id", "")).strip()
            result = asyncio.get_event_loop().run_until_complete(task_manager.cancel_task(task_id))
            return {"cancelled": result}
        except Exception as exc:
            return {"cancelled": False, "error": str(exc)}

    def _tool_memory_remember(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.routers.memory import memory_engine
            text = str(params.get("text", "")).strip()
            memory_type = str(params.get("type", "episodic"))
            source = str(params.get("source", "user"))
            if not text:
                return {"remembered": False, "error": "text is required"}
            result = memory_engine.remember(text, memory_type=memory_type, source=source)
            return {"remembered": True, "memory": result}
        except Exception as exc:
            return {"remembered": False, "error": str(exc)}

    def _tool_memory_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.routers.memory import memory_engine
            query = str(params.get("query", "")).strip()
            limit = int(params.get("limit", 5))
            if not query:
                return {"results": [], "error": "query is required"}
            result = memory_engine.search(query, max_results=limit)
            return {"results": result.get("results", [])}
        except Exception as exc:
            return {"results": [], "error": str(exc)}
'''

if extra_methods not in text:
    text = text + extra_methods

with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print('patched')
