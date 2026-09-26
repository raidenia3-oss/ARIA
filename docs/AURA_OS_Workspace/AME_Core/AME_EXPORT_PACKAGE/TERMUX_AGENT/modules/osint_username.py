#!/usr/bin/env python3
"""
USERNAME SLURPER - Reconocimiento pasivo de usuarios en 15 plataformas.
Python 3 puro, timeouts agresivos, output JSON estructurado.
"""
import requests
import json
from datetime import datetime

PLATFORMS = [
    {"name": "GitHub",    "url": "https://github.com/{}",           "user_format": "{user}"},
    {"name": "Instagram", "url": "https://www.instagram.com/{}/",   "user_format": "{user}"},
    {"name": "Reddit",    "url": "https://www.reddit.com/user/{}",  "user_format": "{user}"},
    {"name": "Twitter/X", "url": "https://x.com/{}",                "user_format": "{user}"},
    {"name": "Telegram",  "url": "https://t.me/{}",                 "user_format": "{user}"},
    {"name": "TikTok",    "url": "https://www.tiktok.com/@{}",      "user_format": "@{user}"},
    {"name": "YouTube",   "url": "https://www.youtube.com/@{}",     "user_format": "@{user}"},
    {"name": "Twitch",    "url": "https://www.twitch.tv/{}",        "user_format": "{user}"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}/",   "user_format": "{user}"},
    {"name": "Medium",    "url": "https://medium.com/@{}",          "user_format": "@{user}"},
    {"name": "Dev.to",    "url": "https://dev.to/{}",               "user_format": "{user}"},
    {"name": "Keybase",   "url": "https://keybase.io/{}",           "user_format": "{user}"},
    {"name": "GitLab",    "url": "https://gitlab.com/{}",           "user_format": "{user}"},
    {"name": "BitBucket", "url": "https://bitbucket.org/{}/",       "user_format": "{user}"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AURA-OSINT/1.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

def check_platform(platform, username):
    """Verifica si un username existe en una plataforma."""
    url = platform["url"].format(username)
    try:
        r = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            return {
                "platform": platform["name"],
                "username": platform["user_format"].format(user=username),
                "profile_url": url,
                "status": "found",
                "response_code": r.status_code
            }
        elif r.status_code in (301, 302, 303, 307, 308):
            return {
                "platform": platform["name"],
                "username": platform["user_format"].format(user=username),
                "profile_url": url,
                "status": "redirected",
                "response_code": r.status_code
            }
        else:
            return {
                "platform": platform["name"],
                "username": platform["user_format"].format(user=username),
                "profile_url": url,
                "status": "not_found",
                "response_code": r.status_code
            }
    except requests.ConnectionError:
        return {"platform": platform["name"], "username": username, "status": "error", "detail": "connection_error"}
    except requests.Timeout:
        return {"platform": platform["name"], "username": username, "status": "error", "detail": "timeout"}
    except Exception as e:
        return {"platform": platform["name"], "username": username, "status": "error", "detail": str(e)[:50]}

def check_platforms(username):
    """Verifica username en todas las plataformas."""
    results = []
    for platform in PLATFORMS:
        result = check_platform(platform, username)
        results.append(result)
    return results

def build_report(username, results):
    """Construye reporte JSON estructurado."""
    found = [r for r in results if r["status"] == "found"]
    redirected = [r for r in results if r["status"] == "redirected"]
    not_found = [r for r in results if r["status"] == "not_found"]
    errors = [r for r in results if r.get("status") == "error"]

    report = {
        "command": "/target",
        "target": username,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
        "summary": {
            "total_checked": len(results),
            "found": len(found),
            "redirected": len(redirected),
            "not_found": len(not_found),
            "errors": len(errors)
        }
    }
    return report

def format_for_discord(report):
    """Formatea reporte JSON a texto estético para Discord."""
    lines = []
    lines.append("```")
    lines.append("╔════════════════════════════════════╗")
    lines.append(f"║ AURA OSINT - TARGET: {report['target']:<14} ║")
    lines.append("╚════════════════════════════════════╝")
    lines.append(f"› Timestamp: {report['timestamp']}")
    lines.append("")

    results = report["results"]
    found = [r for r in results if r["status"] == "found"]
    if found:
        lines.append("──ENCONTRADO──")
        for r in found[:10]:
            lines.append(f"  ✅ {r['platform']:<12} ➜ {r['profile_url']}")

    redirected = [r for r in results if r["status"] == "redirected"]
    if redirected:
        lines.append("──REDIRECT──")
        for r in redirected:
            lines.append(f"  🔀 {r['platform']:<12} (HTTP {r['response_code']})")

    errors = [r for r in results if r.get("status") == "error"]
    if errors:
        lines.append("──ERRORES──")
        for r in errors:
            lines.append(f"  ❌ {r['platform']:<12} {r.get('detail','')}")

    lines.append("")
    lines.append("──RESUMEN──")
    lines.append(f"  Total: {report['summary']['total_checked']}")
    lines.append(f"  ✅ Encontrados: {report['summary']['found']}")
    lines.append(f"  ❌ No encontrados: {report['summary']['not_found']}")
    lines.append(f"  ⚠️  Errores/Timeouts: {report['summary']['errors']}")
    lines.append("```")
    return "\n".join(lines)

def main():
    import sys
    if len(sys.argv) < 2:
        print("Uso: python osint_username.py <username>")
        sys.exit(1)
    username = sys.argv[1]
    results = check_platforms(username)
    report = build_report(username, results)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()