"""AURA OSINT Dashboard — unified tools panel and identity generator.

Usage:
    from osint_dashboard import OSINTDashboard
    dash = OSINTDashboard()
    tools = dash.list_tools("people")
    identity = dash.generate_identity()
"""

from __future__ import annotations

import json
import random
import string
from typing import Any, Dict, List, Optional


class OSINTDashboard:
    def __init__(self) -> None:
        self.categories = {
            "people": [
                {"name": "Namechk", "url": "https://namechk.com", "desc": "Username availability checker"},
                {"name": "Google Dorks", "url": "https://www.google.com/advanced_search", "desc": "Advanced Google search operators"},
                {"name": "Yandex Images", "url": "https://yandex.com/images/", "desc": "Reverse image search"},
                {"name": "Bing Images", "url": "https://www.bing.com/images", "desc": "Visual search"},
                {"name": "Sherlock", "url": "https://github.com/sherlock-project/sherlock", "desc": "Username hunting"},
                {"name": "Maigret", "url": "https://github.com/soxoj/maigret", "desc": "Profile scraper"},
            ],
            "search": [
                {"name": "Shodan", "url": "https://www.shodan.io", "desc": "Internet-connected devices"},
                {"name": "Censys", "url": "https://search.censys.io", "desc": "Attack surface discovery"},
                {"name": "VirusTotal", "url": "https://www.virustotal.com", "desc": "File/URL/domain scanner"},
                {"name": "Wayback Machine", "url": "https://web.archive.org", "desc": "Historical web archive"},
                {"name": "URLScan", "url": "https://urlscan.io", "desc": "URL scanner"},
                {"name": "Hybrid Analysis", "url": "https://www.hybrid-analysis.com", "desc": "Malware sandbox"},
            ],
            "darknet": [
                {"name": "Ahmia", "url": "https://ahmia.fi", "desc": "Tor search engine"},
                {"name": "Torch", "url": "http://torchdeedp3i2jigzjdmf7ln5dait5dz4neot2jkxs5slhpyrfimd.com", "desc": "Tor search"},
                {"name": "OnionList", "url": "https://onionlist.com", "desc": "Hidden services directory"},
            ],
            "maps": [
                {"name": "Google Maps", "url": "https://maps.google.com", "desc": "Maps and Street View"},
                {"name": "Bing Maps", "url": "https://www.bing.com/maps", "desc": "Aerial imagery"},
                {"name": "Waze", "url": "https://www.waze.com", "desc": "Real-time traffic"},
                {"name": "Liveuamap", "url": "https://liveuamap.com", "desc": "Conflict and news map"},
            ],
            "breach": [
                {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com", "desc": "Data breach checker"},
                {"name": "BreachDirectory", "url": "https://breachdirectory.org", "desc": "Compromised account search"},
                {"name": "DeHashed", "url": "https://dehashed.com", "desc": "Data breach search engine"},
            ],
            "domain": [
                {"name": "WHOIS", "url": "https://who.is", "desc": "Domain registration lookup"},
                {"name": "DNS Dumpster", "url": "https://dnsdumpster.com", "desc": "DNS mapper"},
                {"name": "Subdomain Finder", "url": "https://subdomainfinder.c99.nl", "desc": "Subdomain enumeration"},
                {"name": "SSL Labs", "url": "https://www.ssllabs.com/ssltest", "desc": "SSL/TLS assessment"},
            ],
            "documents": [
                {"name": "Google Docs", "url": "https://docs.google.com", "desc": "Document search"},
                {"name": "PDF Drive", "url": "https://www.pdfdrive.com", "desc": "PDF search"},
                {"name": "SlideShare", "url": "https://www.slideshare.net", "desc": "Presentation search"},
            ],
        }

    def list_categories(self) -> List[str]:
        return list(self.categories.keys())

    def list_tools(self, category: str) -> List[Dict[str, str]]:
        return self.categories.get(category, [])

    def search_tools(self, query: str) -> List[Dict[str, str]]:
        query = query.lower()
        results = []
        for cat, tools in self.categories.items():
            for tool in tools:
                if query in tool["name"].lower() or query in tool.get("desc", "").lower():
                    results.append({**tool, "category": cat})
        return results

    def generate_identity(self, country: str = "US", age_range: tuple = (18, 65)) -> Dict[str, Any]:
        first_names_m = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph"]
        first_names_f = ["Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
        streets = ["Main St", "Oak Ave", "Pine Rd", "Maple Dr", "Cedar Ln", "Elm St", "Washington Blvd"]
        cities_us = ["Springfield", "Franklin", "Clinton", "Madison", "Georgetown", "Arlington", "Salem"]
        cities_es = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga", "Murcia"]
        cities_mx = ["Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Tijuana"]
        cities_ar = ["Buenos Aires", "Córdoba", "Rosario", "Mendoza", "Tucumán"]

        gender = random.choice(["male", "female"])
        first = random.choice(first_names_m if gender == "male" else first_names_f)
        last = random.choice(last_names)
        name = f"{first} {last}"

        if country == "ES":
            city = random.choice(cities_es)
            phone = f"+34 {random.randint(600, 699)} {random.randint(100, 999)} {random.randint(100, 999)}"
        elif country == "MX":
            city = random.choice(cities_mx)
            phone = f"+52 {random.randint(55, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
        elif country == "AR":
            city = random.choice(cities_ar)
            phone = f"+54 {random.randint(11, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
        else:
            city = random.choice(cities_us)
            phone = f"+1 ({random.randint(200, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}"

        street = f"{random.randint(100, 9999)} {random.choice(streets)}"
        zip_code = f"{random.randint(10000, 99999)}"
        age = random.randint(*age_range)
        birth_year = 2026 - age
        email_user = f"{first.lower()}.{last.lower()}{random.randint(1, 99)}"
        email = f"{email_user}@example.com"
        password = self._generate_password()
        username = f"{first.lower()}{random.randint(10, 99)}"
        return {
            "name": name,
            "gender": gender,
            "age": age,
            "birth_year": birth_year,
            "address": f"{street}, {city}, {zip_code}",
            "city": city,
            "country": country,
            "email": email,
            "phone": phone,
            "username": username,
            "password": password,
            "note": "Synthetic identity for testing purposes only.",
        }

    def _generate_password(self, length: int = 12) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(random.choice(chars) for _ in range(length))

    def quick_search(self, query: str) -> List[Dict[str, str]]:
        return [
            {"name": "Google", "url": f"https://www.google.com/search?q={query}", "desc": "General search"},
            {"name": "Bing", "url": f"https://www.bing.com/search?q={query}", "desc": "Microsoft search"},
            {"name": "DuckDuckGo", "url": f"https://duckduckgo.com/?q={query}", "desc": "Privacy search"},
            {"name": "Yandex", "url": f"https://yandex.com/search/?text={query}", "desc": "Russian search"},
            {"name": "Baidu", "url": f"https://www.baidu.com/s?wd={query}", "desc": "Chinese search"},
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "categories": len(self.categories),
            "tools": sum(len(v) for v in self.categories.values()),
            "mode": "local",
        }
