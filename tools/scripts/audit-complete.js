const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class CompleteAudit {
  constructor() {
    this.results = {
      timestamp: new Date().toISOString(),
      highSeverity: [],
      mediumSeverity: [],
      lowSeverity: [],
      security: [],
      performance: [],
      codeQuality: [],
      dependencies: [],
      summary: {}
    };
  }

  async run() {
    console.log('🔍 INICIANDO AUDITORÍA COMPLETA...\n');

    await this.checkSecurity();
    await this.checkDependencies();
    await this.checkCodeQuality();
    await this.checkPerformance();
    await this.checkBuildErrors();
    await this.checkEnvironment();
    await this.checkAPISecurity();

    this.generateReport();
    this.saveReport();

    console.log('\n✅ AUDITORÍA COMPLETADA\n');
  }

  searchFiles(dir, pattern) {
    const results = [];
    try {
      const files = fs.readdirSync(dir, { recursive: true });
      for (const file of files) {
        const fullPath = path.join(dir, file);
        if (fs.statSync(fullPath).isFile() && (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx') || fullPath.endsWith('.js') || fullPath.endsWith('.jsx'))) {
          const content = fs.readFileSync(fullPath, 'utf8');
          if (pattern.test(content)) {
            results.push({ file: fullPath, content });
          }
        }
      }
    } catch (e) {}
    return results;
  }

  checkSecurity() {
    console.log('🔒 Auditando Seguridad...');
    const issues = [];
    const frontendDir = path.join(process.cwd(), 'frontend');

    // 1. Buscar console.logs
    const logs = this.searchFiles(path.join(frontendDir, 'app'), /console\.(log|warn)/);
    if (logs.length > 0) {
      issues.push({
        severity: 'HIGH', type: 'Security/Debug',
        issue: `${logs.length} console.log/warn en código de producción`,
        files: logs.slice(0, 5).map(l => l.file),
        fix: 'Eliminar o migrar a logger'
      });
    }

    // 2. Buscar secrets en código
    const secrets = this.searchFiles(frontendDir, /(SECRET|API_KEY|PASSWORD|TOKEN)\s*[:=]\s*['"][^'"]+/);
    const filtered = secrets.filter(s => !s.file.includes('.env') && !s.file.includes('node_modules'));
    if (filtered.length > 0) {
      issues.push({
        severity: 'HIGH', type: 'Security',
        issue: `Posibles secrets en código (${filtered.length} archivos)`,
        files: filtered.slice(0, 3).map(l => l.file),
        fix: 'Mover a variables de entorno'
      });
    }

    // 3. Verificar APIs sin auth
    const apiDir = path.join(frontendDir, 'app', 'api');
    if (fs.existsSync(apiDir)) {
      const apis = this.searchFiles(apiDir, /export\s+(async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)/);
      for (const api of apis) {
        if (!api.content.includes('auth') && !api.content.includes('verifyToken') && !api.content.includes('Authorization') && !api.file.includes('health')) {
          issues.push({
            severity: 'MEDIUM', type: 'Security',
            issue: `API sin auth: ${path.relative(frontendDir, api.file)}`,
            fix: 'Agregar verificación de autenticación'
          });
        }
      }
    }

    this.results.security = issues;
  }

  checkDependencies() {
    console.log('📦 Auditando Dependencias...');
    const pkgPath = path.join(process.cwd(), 'frontend', 'package.json');
    if (fs.existsSync(pkgPath)) {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
      const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };
      const outdated = ['next-auth@4', 'tailwindcss@4'];
      for (const [name, version] of Object.entries(allDeps)) {
        if (version.includes('^') && parseInt(version.replace('^', '').split('.')[0]) <= 1) {
          this.results.lowSeverity.push({
            type: 'Dependency',
            issue: `${name}@${version} - versión temprana, revisar updates`,
            fix: `npm update ${name}`
          });
        }
      }
    }
  }

  checkCodeQuality() {
    console.log('📝 Auditando Calidad de Código...');
    const issues = [];
    const frontendDir = path.join(process.cwd(), 'frontend');

    // Buscar @ts-ignore
    const tsIgnores = this.searchFiles(frontendDir, /@ts-ignore/);
    if (tsIgnores.length > 0) {
      issues.push({
        severity: 'MEDIUM', type: 'Code Quality',
        issue: `${tsIgnores.length} @ts-ignore en el código`,
        fix: 'Corregir tipos en lugar de usar @ts-ignore'
      });
    }

    // Buscar TODO sin asignar
    const todos = this.searchFiles(frontendDir, /TODO/);
    if (todos.length > 0) {
      issues.push({
        severity: 'LOW', type: 'Code Quality',
        issue: `${todos.length} TODOs pendientes`,
        fix: 'Revisar y completar tareas pendientes'
      });
    }

    // Buscar any en TypeScript
    const anyTypes = this.searchFiles(frontendDir, /:\s*any\b/);
    if (anyTypes.length > 0) {
      issues.push({
        severity: 'MEDIUM', type: 'TypeScript',
        issue: `${anyTypes.length} uso de tipo 'any'`,
        fix: 'Reemplazar con tipos específicos'
      });
    }

    this.results.codeQuality = issues;
  }

  checkPerformance() {
    console.log('⚡ Auditando Performance...');
    const issues = [];
    const publicDir = path.join(process.cwd(), 'frontend', 'public');

    // Buscar imágenes grandes
    if (fs.existsSync(publicDir)) {
      const walkDir = (dir) => {
        try {
          const entries = fs.readdirSync(dir, { withFileTypes: true });
          for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) walkDir(fullPath);
            else if (entry.name.match(/\.(jpg|png)$/i)) {
              const stats = fs.statSync(fullPath);
              if (stats.size > 500 * 1024) {
                issues.push({
                  severity: 'MEDIUM', type: 'Performance',
                  issue: `Imagen grande: ${path.relative(publicDir, fullPath)} (${(stats.size / 1024).toFixed(0)}KB)`,
                  fix: 'Comprimir a webp, usar next/image'
                });
              }
            }
          }
        } catch (e) {}
      };
      walkDir(publicDir);
    }

    this.results.performance = issues;
  }

  checkBuildErrors() {
    console.log('🔨 Auditando Build...');
    try {
      const output = execSync('cd frontend && npm run build 2>&1', { encoding: 'utf8', maxBuffer: 1024 * 1024 * 10 });
      const errors = output.split('\n').filter(l => l.toLowerCase().includes('error') && !l.includes('warn'));
      if (errors.length > 0) {
        this.results.highSeverity.push({
          type: 'Build', severity: 'HIGH',
          issue: `${errors.length} errores de build`,
          fix: 'Revisar logs de build'
        });
      }
    } catch (e) {
      const output = e.stdout || e.stderr || '';
      const errors = output.split('\n').filter(l => l.toLowerCase().includes('error'));
      if (errors.length > 0) {
        this.results.highSeverity.push({
          type: 'Build', severity: 'HIGH',
          issue: `${errors.length} errores de build (build falló)`,
          errors: errors.slice(0, 5),
          fix: 'Corregir errores de compilación'
        });
      }
    }
  }

  checkEnvironment() {
    console.log('⚙️ Auditando Configuración...');
    const issues = [];
    const envPath = path.join(process.cwd(), 'frontend', '.env.local');
    if (!fs.existsSync(envPath)) {
      issues.push({
        severity: 'MEDIUM', type: 'Environment',
        issue: 'Archivo .env.local no encontrado',
        fix: 'Crear .env.local con variables necesarias'
      });
    }
    try {
      const nodeVersion = execSync('node --version').toString().trim();
      console.log(`   Node version: ${nodeVersion}`);
    } catch (e) {}
    this.results.mediumSeverity.push(...issues);
  }

  checkAPISecurity() {
    console.log('🔐 Auditando Seguridad de APIs...');
    const frontendDir = path.join(process.cwd(), 'frontend');
    const issues = [];

    // Rate limiting
    const rateLimit = this.searchFiles(path.join(frontendDir, 'app', 'api'), /rateLimit|rateLimiter|throttle/);
    if (rateLimit.length === 0) {
      issues.push({
        severity: 'HIGH', type: 'API Security',
        issue: 'Sin rate limiting en APIs',
        fix: 'Implementar express-rate-limit o similar'
      });
    }

    // Validación de inputs
    const validation = this.searchFiles(path.join(frontendDir, 'app', 'api'), /zod|joi|validator/);
    if (validation.length === 0) {
      issues.push({
        severity: 'HIGH', type: 'API Security',
        issue: 'Sin validación de inputs en APIs',
        fix: 'Usar Zod para validar inputs'
      });
    }

    this.results.highSeverity.push(...issues);
  }

  generateReport() {
    this.results.summary = {
      totalHighSeverity: this.results.highSeverity.length,
      totalMediumSeverity: this.results.mediumSeverity.length,
      totalLowSeverity: this.results.lowSeverity.length,
      totalSecurityIssues: this.results.security.length,
      totalPerformanceIssues: this.results.performance.length,
      totalCodeQualityIssues: this.results.codeQuality.length,
      status: this.results.highSeverity.length === 0 ? '✅ SEGURO' : '⚠️ REQUIERE FIXES'
    };
  }

  saveReport() {
    const reportPath = path.join(process.cwd(), 'AUDITORÍA-RESULTADOS.md');
    
    let markdown = `# 🔍 AUDITORÍA COMPLETA - AURA/AME\n\n`;
    markdown += `**Fecha:** ${this.results.timestamp}\n\n`;

    markdown += `## 📊 RESUMEN\n\n`;
    markdown += `| Métrica | Valor |\n`;
    markdown += `|---------|-------|\n`;
    markdown += `| High Severity | ${this.results.summary.totalHighSeverity} |\n`;
    markdown += `| Medium Severity | ${this.results.summary.totalMediumSeverity} |\n`;
    markdown += `| Low Severity | ${this.results.summary.totalLowSeverity} |\n`;
    markdown += `| Security Issues | ${this.results.summary.totalSecurityIssues} |\n`;
    markdown += `| Performance Issues | ${this.results.summary.totalPerformanceIssues} |\n`;
    markdown += `| Code Quality Issues | ${this.results.summary.totalCodeQualityIssues} |\n`;
    markdown += `| Status | ${this.results.summary.status} |\n\n`;

    markdown += `## 🚨 HIGH SEVERITY ISSUES\n\n`;
    for (const issue of this.results.highSeverity) {
      markdown += `### ${issue.type}\n`;
      markdown += `- **Issue:** ${issue.issue}\n`;
      markdown += `- **Severity:** HIGH\n`;
      markdown += `- **Fix:** ${issue.fix}\n\n`;
    }

    markdown += `## ⚠️ MEDIUM SEVERITY ISSUES\n\n`;
    for (const issue of this.results.mediumSeverity) {
      markdown += `- **${issue.type}:** ${issue.issue}\n`;
      markdown += `  - Fix: ${issue.fix}\n\n`;
    }

    markdown += `## ℹ️ LOW SEVERITY ISSUES\n\n`;
    for (const issue of this.results.lowSeverity) {
      markdown += `- ${issue.issue} (Fix: ${issue.fix})\n`;
    }

    markdown += `\n## 🔐 SECURITY CHECKS\n\n`;
    for (const sec of this.results.security) {
      markdown += `- **${sec.type}:** ${sec.issue}\n`;
      markdown += `  - Fix: ${sec.fix}\n\n`;
    }

    markdown += `\n## ⚡ PERFORMANCE\n\n`;
    for (const perf of this.results.performance) {
      markdown += `- ${perf.issue}\n`;
      markdown += `  - Fix: ${perf.fix}\n\n`;
    }

    fs.writeFileSync(reportPath, markdown);
    console.log(`\n✅ Reporte guardado: ${reportPath}`);
  }
}

new CompleteAudit().run();