# 📜 **SPECIFICATIONS: AME EDGE WORKER**
## **Distributed Task Processing for Mobile Edge Nodes**
**Version:** 1.0.0
**Date:** 02/06/2026
**Status:** Proposal & Specifications
**Author:** System Architect

---

## 🎯 **Objective**
Design a lightweight Python script (`ame_edge_worker.py`) that will be deployed to Android devices via SSH/SCP. This script will act as a **mobile edge worker** that:
1. **Polls** the AURA server for lightweight tasks.
2. **Executes** tasks locally using the device's resources.
3. **Returns** results to the AURA server.
4. **Self-terminates** if the connection to AURA is lost.

The worker will operate within the **Termux Python environment** on Android devices, minimizing memory usage and battery impact.

---

## 📋 **Architecture Overview**

### **1. System Components**
| **Component**               | **Description**                                                                                     |
|-----------------------------|-------------------------------------------------------------------------------------------------|
| **AURA Server**             | Central server that assigns tasks to edge workers.                                               |
| **Edge Worker (ame_edge_worker.py)** | Lightweight Python script running on the mobile device.                                           |
| **Task Queue**              | JSON-based queue of tasks assigned to the worker.                                                 |
| **WebSocket/HTTP API**      | Communication channel between the worker and the AURA server.                                      |
| **Termux Environment**      | Python runtime on the Android device where the worker executes.                                    |

---

## 🔄 **Worker Lifecycle**

### **1. Deployment**
- **Method:** Deployed via SSH/SCP from the AURA server to the mobile device.
- **Location:** `/data/data/com.termux/files/home/ame_edge_worker.py` (Termux home directory).
- **Execution:** Started manually or via Termux cron job.

### **2. Initialization**
1. **Configuration Load:**
   - Loads configuration from a JSON file (`config.json`) or environment variables.
   - Example config:
     ```json
     {
       "server_url": "wss://aura-server.example.com/tasks",
       "device_id": "ANDROID_EDGE_NODE_001",
       "poll_interval": 10,
       "max_retries": 3,
       "timeout": 30,
       "self_destruct_timeout": 300
     }
     ```

2. **Connection Test:**
   - Attempts to connect to the AURA server via WebSocket/HTTP.
   - If connection fails, logs the error and waits for the next poll interval.

### **3. Task Polling Loop**
1. **Poll for Tasks:**
   - Sends a `GET` request to the AURA server to fetch pending tasks.
   - Example payload:
     ```json
     {
       "device_id": "ANDROID_EDGE_NODE_001",
       "last_task_id": 12345,
       "capabilities": ["osint", "sensor_data", "file_operations"]
     }
     ```

2. **Task Processing:**
   - If tasks are available, processes them one by one.
   - For each task:
     - **Validate:** Check if the task is supported by the device.
     - **Execute:** Run the task locally.
     - **Return Results:** Send results back to the AURA server.
     - **Update Status:** Mark the task as completed or failed.

3. **Heartbeat:**
   - Sends a heartbeat signal every `poll_interval` seconds to indicate the worker is alive.
   - Example heartbeat payload:
     ```json
     {
       "device_id": "ANDROID_EDGE_NODE_001",
       "status": "active",
       "last_task_id": 12345,
       "timestamp": "2026-06-02T15:00:00Z"
     }
     ```

### **4. Self-Destruct Mechanism**
- If the connection to the AURA server is lost for more than `self_destruct_timeout` seconds (default: 300s), the worker will:
  1. Log the disconnection.
  2. Clean up resources (close connections, delete temporary files).
  3. Terminate gracefully.

---

## 📦 **Task Payload Structure**

### **1. Task Assignment (Server → Worker)**
```json
{
  "task_id": 12345,
  "device_id": "ANDROID_EDGE_NODE_001",
  "type": "osint|sensor_data|file_operation|custom",
  "priority": "low|medium|high",
  "payload": {
    "command": "termux-location",
    "args": ["--once"],
    "timeout": 10
  },
  "deadline": "2026-06-02T15:30:00Z",
  "retries": 3
}
```

### **2. Task Execution (Worker → Server)**
```json
{
  "task_id": 12345,
  "device_id": "ANDROID_EDGE_NODE_001",
  "status": "success|failed|timeout",
  "result": {
    "data": "{\"latitude\": -12.0464, \"longitude\": -77.0428}",
    "metadata": {
      "execution_time": 2.1,
      "memory_usage": 15.3,
      "timestamp": "2026-06-02T15:05:00Z"
    }
  },
  "error": null|"Command failed: Permission denied"
}
```

---

## 🔧 **Implementation Details**

### **1. Code Structure**
```python
#!/usr/bin/env python3
"""
ame_edge_worker.py - Lightweight edge worker for AURA mobile devices.
Runs in Termux environment and processes tasks assigned by the AURA server.
"""

import os
import sys
import json
import time
import requests
import websockets
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta

class AMEEdgeWorker:
    def __init__(self, config: Dict):
        self.config = config
        self.device_id = config.get("device_id", "ANDROID_EDGE_NODE_001")
        self.server_url = config.get("server_url", "wss://aura-server.example.com/tasks")
        self.poll_interval = config.get("poll_interval", 10)
        self.max_retries = config.get("max_retries", 3)
        self.timeout = config.get("timeout", 30)
        self.self_destruct_timeout = config.get("self_destruct_timeout", 300)
        self.last_heartbeat = time.time()
        self.running = True
        self.last_task_id = 0

    async def connect_to_server(self):
        """Establish connection to the AURA server."""
        try:
            async with websockets.connect(self.server_url) as ws:
                await self._handle_connection(ws)
        except Exception as e:
            print(f"[!] Connection error: {str(e)}")
            await self._check_self_destruct()

    async def _handle_connection(self, ws):
        """Handle WebSocket connection and task processing."""
        while self.running:
            try:
                # Send heartbeat
                await self._send_heartbeat(ws)

                # Poll for tasks
                tasks = await self._poll_for_tasks(ws)
                if tasks:
                    for task in tasks:
                        await self._process_task(task, ws)

                # Wait for next poll interval
                await asyncio.sleep(self.poll_interval)

            except websockets.exceptions.ConnectionClosed:
                print("[!] Connection closed by server")
                self.running = False
            except Exception as e:
                print(f"[!] Error during task processing: {str(e)}")
                await asyncio.sleep(self.poll_interval)

    async def _send_heartbeat(self, ws):
        """Send heartbeat to the server."""
        heartbeat = {
            "device_id": self.device_id,
            "status": "active",
            "last_task_id": self.last_task_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await ws.send(json.dumps(heartbeat))
        self.last_heartbeat = time.time()

    async def _poll_for_tasks(self, ws):
        """Poll the server for pending tasks."""
        payload = {
            "device_id": self.device_id,
            "last_task_id": self.last_task_id,
            "capabilities": ["osint", "sensor_data", "file_operations"]
        }
        try:
            await ws.send(json.dumps({"type": "poll", "payload": payload}))
            response = await ws.recv()
            return json.loads(response).get("tasks", [])
        except Exception as e:
            print(f"[!] Error polling for tasks: {str(e)}")
            return []

    async def _process_task(self, task: Dict, ws):
        """Process a single task."""
        try:
            print(f"[+] Processing task {task['task_id']}: {task['type']}")

            # Execute the task
            result = await self._execute_task(task)

            # Send result back to the server
            response = {
                "task_id": task["task_id"],
                "device_id": self.device_id,
                "status": "success" if result else "failed",
                "result": result if result else {"error": "Task execution failed"},
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            await ws.send(json.dumps({"type": "result", "payload": response}))

            # Update last_task_id
            self.last_task_id = task["task_id"]

        except Exception as e:
            print(f"[!] Error processing task {task['task_id']}: {str(e)}")
            response = {
                "task_id": task["task_id"],
                "device_id": self.device_id,
                "status": "failed",
                "result": {"error": str(e)},
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            await ws.send(json.dumps({"type": "result", "payload": response}))

    async def _execute_task(self, task: Dict) -> Optional[Dict]:
        """Execute the task locally."""
        try:
            if task["type"] == "osint":
                return await self._execute_osint_task(task["payload"])
            elif task["type"] == "sensor_data":
                return await self._execute_sensor_task(task["payload"])
            elif task["type"] == "file_operation":
                return await self._execute_file_operation(task["payload"])
            else:
                return {"error": f"Unsupported task type: {task['type']}"}

        except Exception as e:
            return {"error": str(e)}

    async def _execute_osint_task(self, payload: Dict) -> Dict:
        """Execute an OSINT task (e.g., termux-location)."""
        command = payload.get("command", "")
        args = payload.get("args", [])
        timeout = payload.get("timeout", self.timeout)

        # Example: termux-location --once
        if command == "termux-location":
            import subprocess
            result = subprocess.run(
                ["termux-location"] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return {"data": result.stdout, "status": "success"}
            else:
                return {"error": result.stderr, "status": "failed"}

        return {"error": f"Unsupported OSINT command: {command}", "status": "failed"}

    async def _execute_sensor_task(self, payload: Dict) -> Dict:
        """Execute a sensor data task (e.g., termux-sensors)."""
        # Placeholder for sensor data collection
        return {"data": "Sensor data collected", "status": "success"}

    async def _execute_file_operation(self, payload: Dict) -> Dict:
        """Execute a file operation task (e.g., read/write files)."""
        # Placeholder for file operations
        return {"data": "File operation completed", "status": "success"}

    async def _check_self_destruct(self):
        """Check if the worker should self-destruct due to inactivity."""
        if time.time() - self.last_heartbeat > self.self_destruct_timeout:
            print("[!] Self-destructing due to inactivity...")
            self.running = False
            await self._cleanup()

    async def _cleanup(self):
        """Clean up resources before termination."""
        print("[+] Cleaning up resources...")
        # Close connections, delete temp files, etc.
        sys.exit(0)

async def main():
    """Main entry point for the edge worker."""
    config = {
        "device_id": "ANDROID_EDGE_NODE_001",
        "server_url": "wss://aura-server.example.com/tasks",
        "poll_interval": 10,
        "max_retries": 3,
        "timeout": 30,
        "self_destruct_timeout": 300
    }

    worker = AMEEdgeWorker(config)
    await worker.connect_to_server()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📋 **Deployment Process**

### **1. Prerequisites**
- **Termux Environment:** Python 3 and required libraries (`requests`, `websockets`, `asyncio`) must be installed.
  ```bash
  pkg install python
  pip install requests websockets
  ```

- **SSH Access:** The AURA server must have SSH/SCP access to the mobile device.

### **2. Deployment Steps**
1. **Transfer the Script:**
   ```bash
   scp ame_edge_worker.py user@device-ip:/data/data/com.termux/files/home/
   ```

2. **Set Up Configuration:**
   - Create a `config.json` file on the device with the server URL and device-specific settings.

3. **Start the Worker:**
   ```bash
   termux-exec python ame_edge_worker.py
   ```

4. **Autostart (Optional):**
   - Add the worker to Termux autostart by editing `~/.bashrc` or using Termux's `boot` feature:
     ```bash
     echo "python /data/data/com.termux/files/home/ame_edge_worker.py &" >> ~/.bashrc
     ```

---

## 🔒 **Security Considerations**

### **1. Secure Communication**
- **WebSocket Encryption:** Use `wss://` for encrypted WebSocket connections.
- **Authentication:** Implement JWT or API keys for authenticating the worker with the AURA server.

### **2. Resource Management**
- **Memory Usage:** The worker is designed to be lightweight, using minimal resources.
- **Battery Impact:** Polling intervals and task execution are optimized to minimize battery drain.

### **3. Data Privacy**
- **Task Validation:** Only execute tasks that are explicitly supported by the device.
- **Result Encryption:** Encrypt sensitive results before sending them back to the server.

---

## 📋 **Error Handling & Recovery**

### **1. Connection Failures**
- **Retry Mechanism:** Retry failed connections up to `max_retries` times before self-destructing.
- **Graceful Shutdown:** If the connection is lost for more than `self_destruct_timeout`, the worker terminates gracefully.

### **2. Task Execution Errors**
- **Task-Specific Errors:** Log errors for individual tasks without crashing the worker.
- **Result Reporting:** Always report task results (success or failure) to the AURA server.

---

## 📌 **Testing & Validation**

### **1. Test Cases**
| **Test Case**                          | **Expected Result**                                                                                     |
|----------------------------------------|---------------------------------------------------------------------------------------------------|
| Successful task execution               | Task result is sent back to the server with `status: "success"`.                                      |
| Failed task execution                   | Task result is sent back with `status: "failed"` and error details.                                   |
| Server connection loss                  | Worker self-destructs after `self_destruct_timeout` seconds.                                         |
| Unsupported task type                  | Worker returns an error and continues polling for new tasks.                                          |
| High memory usage                       | Worker remains stable and does not crash.                                                             |

### **2. Validation Steps**
1. **Deploy the Worker:** Transfer and run the script on a test device.
2. **Simulate Tasks:** Send tasks from the AURA server and verify execution.
3. **Test Failures:** Simulate connection drops and verify self-destruct behavior.
4. **Monitor Resources:** Ensure the worker does not consume excessive memory or battery.

---

## 📝 **Non-Goals**
| **ID**  | **Description**                                                                                     |
|---------|-------------------------------------------------------------------------------------------------|
| NG-001  | Support for non-Python environments on Android.                                                   |
| NG-002  | Real-time video processing or heavy computations.                                                 |
| NG-003  | Integration with non-Termux Android environments.                                                   |
| NG-004  | Advanced task scheduling or distributed load balancing.                                            |

---

## 🎯 **Conclusion**
The **AME Edge Worker** specification outlines a lightweight, self-contained Python script designed to run on Android devices within the Termux environment. It will:
1. **Poll** the AURA server for tasks.
2. **Execute** tasks locally using device resources.
3. **Return** results to the AURA server.
4. **Self-destruct** if the connection is lost for an extended period.

This design ensures minimal memory usage, battery impact, and robust error handling, making it ideal for mobile edge computing in the AURA ecosystem.

**Next Steps:**
- Validate the specification with the Architect.
- Proceed to implementation once approved.

---
**Ready for Architect Validation!**