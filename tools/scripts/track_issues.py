"""ARIA OS — Issues & Improvements Tracker"""

import json
from datetime import datetime
from pathlib import Path

ISSUES_FILE = Path('issues_and_improvements.json')

def add_issue(category, title, description, severity='MEDIUM', status='OPEN'):
    """Add a new issue"""

    data = load_issues()

    issue = {
        'id': len(data['issues']) + 1,
        'category': category,
        'title': title,
        'description': description,
        'severity': severity,
        'status': status,
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat()
    }

    data['issues'].append(issue)
    save_issues(data)

    print(f"✅ Issue #{issue['id']} added: {title}")

def update_issue(issue_id, **kwargs):
    """Update issue status"""
    data = load_issues()

    for issue in data['issues']:
        if issue['id'] == issue_id:
            for key, value in kwargs.items():
                issue[key] = value
            issue['updated'] = datetime.now().isoformat()
            save_issues(data)
            print(f"✅ Issue #{issue_id} updated")
            return

    print(f"❌ Issue #{issue_id} not found")

def load_issues():
    """Load issues from file"""
    if not ISSUES_FILE.exists():
        return {'issues': []}

    with open(ISSUES_FILE) as f:
        return json.load(f)

def save_issues(data):
    """Save issues to file"""
    with open(ISSUES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def report_issues():
    """Generate issues report"""
    data = load_issues()

    print("\n" + "=" * 80)
    print("ARIA OS — Issues & Improvements Report")
    print("=" * 80)

    by_severity = {}
    for issue in data['issues']:
        sev = issue['severity']
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(issue)

    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        if severity in by_severity:
            print(f"\n{severity} SEVERITY ({len(by_severity[severity])} issues):")
            print("-" * 80)

            for issue in by_severity[severity]:
                status_icon = {
                    'OPEN': '🔴',
                    'IN_PROGRESS': '🟡',
                    'CLOSED': '✅',
                    'WONTFIX': '⚪'
                }.get(issue['status'], '?')

                print(f"{status_icon} #{issue['id']}: {issue['title']}")
                print(f"   Status: {issue['status']} | Category: {issue['category']}")
                print(f"   {issue['description']}")
                print()

def register_common_issues():
    """Register common issues found during testing"""

    issues = [
        {
            'category': 'performance',
            'title': 'Chat endpoint slow (54s)',
            'description': 'Ollama inference + build_context takes too long. Solution: cache context with TTL, optimize process_iter',
            'severity': 'HIGH'
        },
        {
            'category': 'performance',
            'title': 'Screen capture delay',
            'description': 'Screen capture happens every 1s. Should be async/threaded to not block.',
            'severity': 'MEDIUM'
        },
        {
            'category': 'bug',
            'title': 'WebSocket /api/aria/observe not tested',
            'description': 'WS endpoint defined but no active test. Need real WebSocket client test.',
            'severity': 'MEDIUM'
        },
        {
            'category': 'feature',
            'title': 'Implement ARIA v4.0 desktop (no HTTP)',
            'description': 'Convert from FastAPI server to IPC pipes architecture. See PHASE_RESEARCH_DESKTOP_ARCHITECTURE.txt',
            'severity': 'CRITICAL'
        },
        {
            'category': 'optimization',
            'title': 'Reduce model size (quantization)',
            'description': 'Whisper/Ollama models are large. Use quantized versions (Q4, Q5) to reduce disk/memory.',
            'severity': 'MEDIUM'
        },
        {
            'category': 'optimization',
            'title': 'Memory leak in explanation_generator',
            'description': 'tracemalloc shows 327 KiB growth. Investigate cache/list accumulation.',
            'severity': 'LOW'
        },
        {
            'category': 'feature',
            'title': 'Add system tray integration',
            'description': 'Implement pystray for minimize-to-tray and hotkey Ctrl+Shift+A.',
            'severity': 'MEDIUM'
        },
        {
            'category': 'feature',
            'title': 'Voice activation (wake word)',
            'description': 'Implement Vosk for passive "ARIA" wake-word detection.',
            'severity': 'HIGH'
        },
    ]

    for issue in issues:
        add_issue(**issue)

if __name__ == '__main__':
    register_common_issues()
    report_issues()
