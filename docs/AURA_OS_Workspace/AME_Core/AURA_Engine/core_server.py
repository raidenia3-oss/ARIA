from fastapi import FastAPI
import psutil
import uvicorn

app = FastAPI(title="AURA Engine", version="0.1.0")


@app.get("/status")
def status():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": cpu,
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "free": mem.free,
            "percent": mem.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
