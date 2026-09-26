const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000';
const results: any[] = [];

async function testEndpoint(path: string, method = 'GET', body?: any) {
  const start = Date.now();
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const elapsed = Date.now() - start;
    results.push({ path, status: res.status, elapsed, ok: res.ok });
  } catch (e: any) {
    results.push({ path, status: 0, elapsed: Date.now() - start, ok: false, error: e.message });
  }
}

async function runTests() {
  await testEndpoint("/api/health");
  await testEndpoint("/api/ame-core");
  await testEndpoint("/api/webhooks", "POST", { event: "test", data: {} });
  await testEndpoint("/api/slack/events");
  await testEndpoint("/api/discord/webhook");
  await testEndpoint("/api/telegram/webhook");
  await testEndpoint("/api/teams");

  const passed = results.filter(r => r.ok).length;
  const avgLatency = Math.round(results.reduce((a, r) => a + r.elapsed, 0) / results.length);

  console.log("\n=== INTEGRATION TEST RESULTS ===");
  results.forEach(r => console.log(`${r.ok ? '✅' : '❌'} ${r.path} - ${r.status} (${r.elapsed}ms) `));
  console.log(`\nPassed: ${passed}/${results.length}`);
  console.log(`Avg Latency: ${avgLatency}ms`);

  if (passed < results.length) {
    console.log("\nFailed:", results.filter(r => !r.ok));
    process.exit(1);
  }
}

runTests();
