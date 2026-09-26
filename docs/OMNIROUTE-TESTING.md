# Omniroute Testing & Benchmarking

Guía completa para testing y benchmarking de la integración Omniroute.

## Unit Tests

Ejecutar unit tests:

```bash
pytest tests/test_omniroute.py -v
```

### Cobertura de tests

- ✅ OmnirouteClient
  - get_providers()
  - get_best_provider()
  - chat()
  - get_health()
  - Fallback mechanisms

- ✅ ProviderManager
  - start_monitoring()
  - stop_monitoring()
  - get_provider_stats()
  - get_recommendations()

- ✅ Integration tests
  - Live Omniroute connectivity

## Benchmarking

### Provider Benchmark

Mide performance de cada proveedor:

```bash
python scripts/benchmark-omniroute.py
```

**Métricas:**
- Latencia promedio
- Latencia mín/máx
- Tasa de éxito
- Desviación estándar

**Output:** HTML report (`omniroute-benchmark-report.html`)

### Stress Testing

Load testing para validar escalabilidad:

```bash
python scripts/stress-test-omniroute.py
```

**Escenarios:**
- Light load: 30s, 5 clientes
- Medium load: 60s, 10 clientes
- Heavy load: 60s, 20 clientes

**Métricas:**
- Total requests
- Throughput (req/sec)
- Percentiles de latencia (P50, P95, P99)
- Error rate

## Testing Checklist

```bash
# 1. Unit tests
pytest tests/test_omniroute.py -v --cov=backend/omniroute

# 2. Integration tests (requiere Omniroute corriendo)
pytest tests/test_omniroute.py -v -m integration

# 3. Benchmarking
python scripts/benchmark-omniroute.py

# 4. Stress testing
python scripts/stress-test-omniroute.py

# 5. Health check
curl http://localhost:8000/api/omniroute/health

# 6. Provider stats
curl http://localhost:8000/api/providers/stats
```

## Performance Targets

| Métrica | Target |
|---------|--------|
| Avg latency | < 500ms |
| P95 latency | < 1s |
| P99 latency | < 2s |
| Success rate | > 95% |
| Throughput | > 10 req/sec |
| Error rate | < 5% |

## Troubleshooting

### Tests fail: "Omniroute not available"

```bash
# Verificar que Omniroute está corriendo
curl http://localhost:8080/api/health

# Si Docker:
docker ps | grep omniroute

# Si local:
ps aux | grep omniroute
```

### Benchmark shows high latency

```bash
# Ver qué proveedores están saludables
curl http://localhost:8000/api/providers

# Ver recomendaciones
curl http://localhost:8000/api/providers/recommendations
```

### Stress test shows errors

```bash
# Ver logs de AURA
tail -f logs/aura.log

# Ver logs de Omniroute (si Docker)
docker logs omniroute
```

## Continuous Testing

Para CI/CD, agregar a `.github/workflows/ci-cd.yml`:

```yaml
- name: Run Omniroute Tests
  run: |
    pytest tests/test_omniroute.py -v --cov
    python scripts/benchmark-omniroute.py
```

## Métricas Esperadas en Producción

| Métrica | Valor |
|---------|-------|
| Providers disponibles | 300+ |
| Providers saludables | 95%+ |
| Latencia promedio | 200-500ms |
| Uptime | 99.5%+ |
| Fallback success rate | 100% |
| Error rate | < 5% |
