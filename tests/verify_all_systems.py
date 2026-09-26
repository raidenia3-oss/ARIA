#!/usr/bin/env python3
"""ARIA OS v3.2 — Complete System Verification"""

import asyncio
import sys
import time
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# 1. BACKEND VERIFICATION
# ============================================================================

class BackendVerification:
    def __init__(self):
        self.results = []
        self.base_url = "http://localhost:8000"
        self.timeout = 10

    async def verify_server_running(self):
        """Verify backend server is running"""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            status = "✅ PASS" if resp.status_code == 200 else "❌ FAIL"
            self.results.append({
                'test': 'Server running',
                'status': status,
                'latency_ms': resp.elapsed.total_seconds() * 1000
            })
            return resp.status_code == 200
        except Exception as e:
            self.results.append({
                'test': 'Server running',
                'status': '❌ FAIL',
                'error': str(e)
            })
            return False

    async def verify_endpoints(self):
        """Verify critical endpoints"""
        endpoints = [
            ('GET', '/health', 'Health check'),
            ('GET', '/api/system/status', 'System status'),
            ('GET', '/api/aria/health', 'ARIA health'),
            ('GET', '/api/aria/profile', 'User profile'),
            ('GET', '/api/skills', 'Skills registry'),
            ('GET', '/api/memory/recent', 'Recent memory'),
            ('GET', '/api/ai/ollama', 'Ollama status'),
            ('GET', '/api/plugins', 'Plugins'),
            ('GET', '/api/learning/rules', 'Learning rules'),
        ]

        for method, path, name in endpoints:
            try:
                if method == 'GET':
                    resp = requests.get(f"{self.base_url}{path}", timeout=5)
                status = "✅ PASS" if resp.status_code == 200 else f"❌ {resp.status_code}"
                self.results.append({
                    'test': f'Endpoint: {name}',
                    'endpoint': path,
                    'status': status,
                    'latency_ms': resp.elapsed.total_seconds() * 1000
                })
            except Exception as e:
                self.results.append({
                    'test': f'Endpoint: {name}',
                    'endpoint': path,
                    'status': '❌ FAIL',
                    'error': str(e)
                })

    async def verify_chat_endpoint(self):
        """Verify chat functionality"""
        try:
            start = time.time()
            resp = requests.post(
                f"{self.base_url}/api/aria/chat",
                json={"message": "¿Qué hora es?"},
                timeout=60
            )
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                has_response = bool(data.get('response'))
                status = "✅ PASS" if has_response else "⚠️ WARN (empty)"
            else:
                status = f"❌ {resp.status_code}"

            self.results.append({
                'test': 'Chat endpoint',
                'status': status,
                'latency_ms': latency,
                'response_length': len(data.get('response', '')) if resp.status_code == 200 else 0
            })
        except Exception as e:
            self.results.append({
                'test': 'Chat endpoint',
                'status': '❌ FAIL',
                'error': str(e),
                'latency_ms': 'N/A'
            })

    async def verify_ollama_connection(self):
        """Verify Ollama is running"""
        try:
            resp = requests.get(f"{self.base_url}/api/ai/ollama", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                model = data.get('active', 'N/A')
                status = "✅ PASS" if data.get('online', False) else "⚠️ DOWN"
            else:
                status = f"❌ {resp.status_code}"
                model = "N/A"

            self.results.append({
                'test': 'Ollama connection',
                'status': status,
                'model': model,
                'available': data.get('online', False) if resp.status_code == 200 else False
            })
        except Exception as e:
            self.results.append({
                'test': 'Ollama connection',
                'status': '❌ FAIL',
                'error': str(e)
            })

    async def verify_database(self):
        """Verify database integrity"""
        try:
            import sqlite3
            db_path = Path(__file__).parent.parent / 'AURA_APP' / 'cerebro.db'

            if not db_path.exists():
                db_path = Path(__file__).parent.parent / 'AURA_APP' / 'memory'
                if not db_path.exists():
                    self.results.append({
                        'test': 'Database',
                        'status': '⚠️ NOT_FOUND',
                        'path': str(db_path)
                    })
                    return

                self.results.append({
                    'test': 'Database (memory JSON)',
                    'status': '✅ PASS',
                    'path': str(db_path),
                    'note': 'Using JSON memory store'
                })
                return

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            if len(tables) > 0:
                status = "✅ PASS"
            else:
                status = "⚠️ EMPTY"

            self.results.append({
                'test': 'Database',
                'status': status,
                'tables_count': len(tables),
                'size_mb': db_path.stat().st_size / (1024 * 1024)
            })

            conn.close()
        except Exception as e:
            self.results.append({
                'test': 'Database',
                'status': '❌ FAIL',
                'error': str(e)
            })

# ============================================================================
# 2. MODULE VERIFICATION
# ============================================================================

class ModuleVerification:
    def __init__(self):
        self.results = []

    async def verify_imports(self):
        """Verify all modules import correctly"""
        modules = [
            'AURA_APP.backend.app',
            'AURA_APP.backend.aria_engine',
            'AURA_APP.backend.aria_observer_v2',
            'AURA_APP.backend.aria_suggestion_engine',
            'AURA_APP.backend.aria_integration',
            'AURA_APP.backend.generation.content_generator',
            'AURA_APP.backend.ml.lora_trainer',
            'AURA_APP.backend.connectors.base',
            'AURA_APP.backend.aria_brain',
            'AURA_APP.backend.training.fine_tuning_pipeline',
            'AURA_APP.backend.resilience.circuit_breaker',
            'AURA_APP.backend.observability.metrics_collector',
        ]

        for module in modules:
            try:
                __import__(module)
                status = "✅ PASS"
                error = None
            except Exception as e:
                status = "❌ FAIL"
                error = str(e)

            self.results.append({
                'test': f'Import: {module}',
                'status': status,
                'error': error
            })

    async def verify_classes(self):
        """Verify critical classes exist and instantiate"""
        try:
            from AURA_APP.backend.aria_engine import AriaEngine
            aria = AriaEngine()
            self.results.append({
                'test': 'AriaEngine instantiation',
                'status': '✅ PASS'
            })
        except Exception as e:
            self.results.append({
                'test': 'AriaEngine instantiation',
                'status': '❌ FAIL',
                'error': str(e)
            })

        try:
            from AURA_APP.backend.aria_brain import AriaBrain
            brain = AriaBrain()
            self.results.append({
                'test': 'AriaBrain instantiation',
                'status': '✅ PASS'
            })
        except Exception as e:
            self.results.append({
                'test': 'AriaBrain instantiation',
                'status': '❌ FAIL',
                'error': str(e)
            })

# ============================================================================
# 3. PERFORMANCE VERIFICATION
# ============================================================================

class PerformanceVerification:
    def __init__(self):
        self.results = []

    async def verify_response_times(self):
        """Verify endpoint response times are acceptable"""
        endpoints = [
            ('/health', 100),
            ('/api/system/status', 200),
            ('/api/aria/health', 200),
            ('/api/skills', 300),
            ('/api/memory/recent', 500),
        ]

        for path, max_ms in endpoints:
            try:
                start = time.time()
                resp = requests.get(f"http://localhost:8000{path}", timeout=5)
                latency = (time.time() - start) * 1000

                if latency < max_ms:
                    status = "✅ PASS"
                else:
                    status = f"⚠️ SLOW ({latency:.0f}ms > {max_ms}ms)"

                self.results.append({
                    'test': f'Response time: {path}',
                    'status': status,
                    'latency_ms': latency,
                    'threshold_ms': max_ms
                })
            except Exception as e:
                self.results.append({
                    'test': f'Response time: {path}',
                    'status': '❌ FAIL',
                    'error': str(e)
                })

    async def verify_memory_usage(self):
        """Verify memory usage is reasonable"""
        try:
            resp = requests.get("http://localhost:8000/api/system/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                memory_mb = data.get('memory_mb', 0)

                if memory_mb < 2000:
                    status = "✅ PASS"
                else:
                    status = f"⚠️ HIGH ({memory_mb}MB)"

                self.results.append({
                    'test': 'Memory usage',
                    'status': status,
                    'memory_mb': memory_mb,
                    'threshold_mb': 2000
                })
        except Exception as e:
            self.results.append({
                'test': 'Memory usage',
                'status': '⚠️ UNABLE_TO_CHECK',
                'error': str(e)
            })

# ============================================================================
# 4. FUNCTIONAL VERIFICATION
# ============================================================================

class FunctionalVerification:
    def __init__(self):
        self.results = []

    async def verify_chat_quality(self):
        """Verify chat produces reasonable responses"""
        test_messages = [
            ("Hola", "greeting"),
            ("¿Qué hora es?", "time_query"),
            ("Abre notepad", "system_command"),
            ("Cuéntame un chiste", "creative"),
        ]

        for msg, category in test_messages:
            try:
                resp = requests.post(
                    "http://localhost:8000/api/aria/chat",
                    json={"message": msg},
                    timeout=60
                )

                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get('response', '')

                    if len(response_text) > 0:
                        status = "✅ PASS"
                    else:
                        status = "⚠️ EMPTY_RESPONSE"
                else:
                    status = f"❌ {resp.status_code}"

                self.results.append({
                    'test': f'Chat quality: {category}',
                    'message': msg,
                    'status': status,
                    'response_length': len(response_text) if resp.status_code == 200 else 0
                })
            except Exception as e:
                self.results.append({
                    'test': f'Chat quality: {category}',
                    'message': msg,
                    'status': '❌ FAIL',
                    'error': str(e)
                })

# ============================================================================
# 5. REPORT GENERATION
# ============================================================================

class VerificationReport:
    def __init__(self, results_list):
        self.results = results_list
        self.timestamp = datetime.now().isoformat()

    def generate_summary(self):
        """Generate summary stats"""
        pass_count = sum(1 for r in self.results if '✅' in r.get('status', ''))
        fail_count = sum(1 for r in self.results if '❌' in r.get('status', ''))
        warn_count = sum(1 for r in self.results if '⚠️' in r.get('status', ''))

        return {
            'timestamp': self.timestamp,
            'total_tests': len(self.results),
            'passed': pass_count,
            'failed': fail_count,
            'warnings': warn_count,
            'success_rate': f"{(pass_count / len(self.results) * 100):.1f}%" if self.results else "N/A"
        }

    def generate_json(self):
        """Generate JSON report"""
        report = {
            'summary': self.generate_summary(),
            'results': self.results
        }
        return json.dumps(report, indent=2)

    def generate_html(self):
        """Generate HTML report"""
        summary = self.generate_summary()

        html = f"""
        <html>
        <head>
            <title>ARIA OS v3.2 — Verification Report</title>
            <style>
                body {{ font-family: monospace; background: #0a0e27; color: #00ff88; padding: 20px; }}
                h1 {{ color: #ff006e; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #00d9ff; padding: 10px; text-align: left; }}
                th {{ background: #1a1f3a; color: #00d9ff; }}
                tr:nth-child(even) {{ background: #141829; }}
                .pass {{ color: #00ff88; }}
                .fail {{ color: #ff006e; }}
                .warn {{ color: #ffd600; }}
                .summary {{ background: #1a1f3a; padding: 15px; border: 1px solid #00d9ff; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>ARIA OS v3.2 — Verification Report</h1>

            <div class="summary">
                <h2>Summary</h2>
                <p>Timestamp: {summary['timestamp']}</p>
                <p>Total Tests: {summary['total_tests']}</p>
                <p><span class="pass">Passed: {summary['passed']}</span></p>
                <p><span class="fail">Failed: {summary['failed']}</span></p>
                <p><span class="warn">Warnings: {summary['warnings']}</span></p>
                <p>Success Rate: {summary['success_rate']}</p>
            </div>

            <h2>Detailed Results</h2>
            <table>
                <tr>
                    <th>Test</th>
                    <th>Status</th>
                    <th>Details</th>
                </tr>
        """

        for result in self.results:
            status_class = 'pass' if '✅' in result['status'] else ('fail' if '❌' in result['status'] else 'warn')
            details = json.dumps({k: v for k, v in result.items() if k != 'test' and k != 'status'}, indent=0)

            html += f"""
                <tr>
                    <td>{result['test']}</td>
                    <td class="{status_class}">{result['status']}</td>
                    <td><pre>{details}</pre></td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html

# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def run_all_verifications():
    """Run all verification suites"""

    print("🔍 ARIA OS v3.2 — Complete Verification")
    print("=" * 80)
    print()

    all_results = []

    # Backend verification
    print("▶ Backend verification...")
    backend = BackendVerification()
    await backend.verify_server_running()
    await backend.verify_endpoints()
    await backend.verify_chat_endpoint()
    await backend.verify_ollama_connection()
    await backend.verify_database()
    all_results.extend(backend.results)

    # Module verification
    print("▶ Module verification...")
    modules = ModuleVerification()
    await modules.verify_imports()
    await modules.verify_classes()
    all_results.extend(modules.results)

    # Performance verification
    print("▶ Performance verification...")
    perf = PerformanceVerification()
    await perf.verify_response_times()
    await perf.verify_memory_usage()
    all_results.extend(perf.results)

    # Functional verification
    print("▶ Functional verification...")
    func = FunctionalVerification()
    await func.verify_chat_quality()
    all_results.extend(func.results)

    # Generate reports
    print("▶ Generating reports...")
    report = VerificationReport(all_results)

    # Save JSON
    with open('verification_report.json', 'w') as f:
        f.write(report.generate_json())

    # Save HTML
    with open('verification_report.html', 'w') as f:
        f.write(report.generate_html())

    # Print summary
    summary = report.generate_summary()
    print()
    print("=" * 80)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 80)
    print(f"Passed: {summary['passed']}/{summary['total_tests']}")
    print(f"Failed: {summary['failed']}/{summary['total_tests']}")
    print(f"Warnings: {summary['warnings']}/{summary['total_tests']}")
    print(f"Success Rate: {summary['success_rate']}")
    print()
    print(f"📄 Reports saved:")
    print(f"   - verification_report.json")
    print(f"   - verification_report.html")

if __name__ == '__main__':
    asyncio.run(run_all_verifications())
