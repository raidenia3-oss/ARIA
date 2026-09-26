#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E test: Chat → Ollama → RAG → Response
"""
import io
import sys
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

def log(msg, status="ℹ️"):
    print(f"{status} [{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_backend_health():
    """Test 1: Backend health"""
    log("Test 1: Backend health check", "🔍")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code == 200:
            log(f"✅ Backend alive: {resp.json()}", "✅")
            return True
        else:
            log(f"❌ Backend returned {resp.status_code}", "❌")
            return False
    except Exception as e:
        log(f"❌ Backend unreachable: {e}", "❌")
        return False

def test_ollama():
    """Test 2: Ollama inference"""
    log("Test 2: Ollama inference", "🔍")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/ai/local/inference",
            json={"prompt": "¿Qué eres tú?", "model": "dolphin-2_6-phi-2"}
        )
        if resp.status_code == 200:
            data = resp.json()
            log(f"✅ Ollama response: {data.get('text', data.get('response', ''))[:100]}...", "✅")
            return True
        else:
            log(f"❌ Ollama error {resp.status_code}: {resp.text}", "❌")
            return False
    except Exception as e:
        log(f"❌ Ollama test failed: {e}", "❌")
        return False

def test_vector_memory():
    """Test 3: Vector memory add + search"""
    log("Test 3: Vector memory add + search", "🔍")
    try:
        # Add - vector/add expects a list of document objects
        add_resp = requests.post(
            f"{BASE_URL}/api/memory/vector/add",
            json=[{"content": "ARIA OS es un asistente personal avanzado estilo Jarvis"}]
        )
        if add_resp.status_code != 200:
            log(f"❌ Add failed: {add_resp.status_code}", "❌")
            return False

        log(f"✅ Added 1 document to vector store", "✅")

        # Search
        time.sleep(0.5)  # small delay
        search_resp = requests.post(
            f"{BASE_URL}/api/memory/vector/search",
            json={"query": "¿Qué es ARIA?", "top_k": 3}
        )
        if search_resp.status_code == 200:
            results = search_resp.json()
            log(f"✅ Vector search returned {len(results.get('results', []))} results", "✅")
            return True
        else:
            log(f"❌ Search failed: {search_resp.status_code}", "❌")
            return False
    except Exception as e:
        log(f"❌ Vector memory test failed: {e}", "❌")
        return False

def test_rag():
    """Test 4: RAG (chat with context)"""
    log("Test 4: RAG pipeline (chat with context)", "🔍")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/memory/vector/rag",
            json={"query": "¿Qué es ARIA OS?"}
        )
        if resp.status_code == 200:
            data = resp.json()
            log(f"✅ RAG response: {data.get('response', 'N/A')[:100]}...", "✅")
            return True
        else:
            log(f"❌ RAG failed: {resp.status_code}", "❌")
            return False
    except Exception as e:
        log(f"❌ RAG test failed: {e}", "❌")
        return False

def test_chat_endpoint():
    """Test 5: Chat endpoint (full flow)"""
    log("Test 5: Chat endpoint (/api/chat)", "🔍")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "message": "Hola, ¿cómo estás?",
                "provider": "local"
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            log(f"✅ Chat response: {data.get('response', 'N/A')[:100]}...", "✅")
            log(f"   Latency: {data.get('latency', 'N/A')}ms", "   ")
            return True
        else:
            log(f"❌ Chat failed: {resp.status_code}", "❌")
            return False
    except Exception as e:
        log(f"❌ Chat test failed: {e}", "❌")
        return False

def main():
    print("\n" + "="*80)
    print("ARIA v5.0 E2E TEST SUITE")
    print("="*80 + "\n")

    tests = [
        ("Backend Health", test_backend_health),
        ("Ollama Inference", test_ollama),
        ("Vector Memory", test_vector_memory),
        ("RAG Pipeline", test_rag),
        ("Chat Endpoint", test_chat_endpoint)
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
        print()

    # Summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} | {name}")

    print("="*80)
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - E2E FLOW WORKING!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - check logs above")

    print("="*80 + "\n")

if __name__ == "__main__":
    main()
