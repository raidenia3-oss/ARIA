module.exports = {
  apps: [
    {
      name: 'aura-servidor-ame',
      script: 'AURA_Core/crash_overseer.py',
      cwd: __dirname,
      interpreter: process.env.PYTHON || 'python',
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      autorestart: true,
      max_restarts: 5,
      restart_delay: 5000,
      max_memory_restart: '1G',
      env: {
        FLASK_ENV: 'production',
        PYTHONUNBUFFERED: 1
      },
      error_file: './AURA_Core/logs/aura-error.log',
      out_file: './AURA_Core/logs/aura-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true
    }
  ]
};
