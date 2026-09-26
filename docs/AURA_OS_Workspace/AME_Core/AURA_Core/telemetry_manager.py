#!/usr/bin/env python3
"""
Telemetry Manager para AURA.
Recopila métricas de rendimiento y las expone a través de Prometheus.
"""

from flask import Flask, jsonify
from prometheus_client import make_wsgi_app, Counter, Gauge, Histogram, Summary
import psutil
import time
import GPUtil
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

# Métricas de Prometheus
REQUEST_COUNT = Counter('aura_request_count', 'Total requests to AURA API')
REQUEST_LATENCY = Histogram('aura_request_latency_seconds', 'Latency of AURA API requests')
CPU_USAGE = Gauge('aura_cpu_usage', 'CPU usage percentage')
MEMORY_USAGE = Gauge('aura_memory_usage_bytes', 'Memory usage in bytes')
GPU_USAGE = Gauge('aura_gpu_usage', 'GPU usage percentage')
DISK_USAGE = Gauge('aura_disk_usage', 'Disk usage percentage')
OLLAMA_LATENCY = Histogram('ollama_latency_seconds', 'Latency of Ollama responses')
NETWORK_IO = Gauge('aura_network_io_bytes', 'Network I/O in bytes')
PROCESS_COUNT = Gauge('aura_process_count', 'Number of running processes')

# Métricas específicas para cada servicio
SERVICES = {
    "ollama": {
        "latency": Histogram('ollama_latency_seconds', 'Latency of Ollama API responses'),
        "requests": Counter('ollama_request_count', 'Total requests to Ollama API')
    },
    "shadow_core": {
        "latency": Histogram('shadow_core_latency_seconds', 'Latency of Shadow Core API responses'),
        "requests": Counter('shadow_core_request_count', 'Total requests to Shadow Core API')
    },
    "action_executor": {
        "latency": Histogram('action_executor_latency_seconds', 'Latency of Action Executor API responses'),
        "requests": Counter('action_executor_request_count', 'Total requests to Action Executor API')
    }
}

def update_system_metrics():
    """Actualiza las métricas del sistema."""
    # CPU Usage
    CPU_USAGE.set(psutil.cpu_percent(interval=1))

    # Memory Usage
    memory = psutil.virtual_memory()
    MEMORY_USAGE.set(memory.used)

    # GPU Usage (si está disponible)
    gpus = GPUtil.getGPUs()
    if gpus:
        gpu = gpus[0]
        GPU_USAGE.set(gpu.load * 100)

    # Disk Usage
    disk = psutil.disk_usage('/')
    DISK_USAGE.set(disk.percent)

    # Network I/O
    net_io = psutil.net_io_counters()
    NETWORK_IO.set(net_io.bytes_sent + net_io.bytes_recv)

    # Process Count
    PROCESS_COUNT.set(len(psutil.pids()))

def update_ollama_metrics():
    """Simula actualización de métricas de Ollama."""
    # Ejemplo de latencia de Ollama (simulada)
    OLLAMA_LATENCY.observe(0.15)  # Latencia simulada de 150ms
    SERVICES["ollama"]["requests"].inc()

def update_shadow_core_metrics():
    """Simula actualización de métricas de Shadow Core."""
    # Ejemplo de latencia de Shadow Core (simulada)
    SERVICES["shadow_core"]["latency"].observe(0.08)  # Latencia simulada de 80ms
    SERVICES["shadow_core"]["requests"].inc()

def update_action_executor_metrics():
    """Simula actualización de métricas de Action Executor."""
    # Ejemplo de latencia de Action Executor (simulada)
    SERVICES["action_executor"]["latency"].observe(0.2)  # Latencia simulada de 200ms
    SERVICES["action_executor"]["requests"].inc()

@app.route('/metrics')
def metrics():
    """Exponer métricas en formato Prometheus."""
    REQUEST_COUNT.inc()
    start_time = time.time()
    update_system_metrics()
    update_ollama_metrics()
    update_shadow_core_metrics()
    update_action_executor_metrics()
    REQUEST_LATENCY.observe(time.time() - start_time)
    return make_wsgi_app().wsgi_app(environ={}, start_response=lambda *args: None)

@app.route('/api/telemetry/system')
def get_system_metrics():
    """Obtener métricas del sistema en formato JSON."""
    update_system_metrics()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "cpu_usage": CPU_USAGE._value.get(),
        "memory_usage": MEMORY_USAGE._value.get(),
        "gpu_usage": GPU_USAGE._value.get(),
        "disk_usage": DISK_USAGE._value.get(),
        "network_io": NETWORK_IO._value.get(),
        "process_count": PROCESS_COUNT._value.get(),
        "ollama": {
            "latency": OLLAMA_LATENCY._summarize().quantiles[0.95],
            "requests": SERVICES["ollama"]["requests"]._value.get()
        },
        "shadow_core": {
            "latency": SERVICES["shadow_core"]["latency"]._summarize().quantiles[0.95],
            "requests": SERVICES["shadow_core"]["requests"]._value.get()
        },
        "action_executor": {
            "latency": SERVICES["action_executor"]["latency"]._summarize().quantiles[0.95],
            "requests": SERVICES["action_executor"]["requests"]._value.get()
        }
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5008, debug=False)