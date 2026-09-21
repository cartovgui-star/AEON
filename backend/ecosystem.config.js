module.exports = {
  apps: [{
    name: "aeon-backend",
    script: "/bin/bash",
    args: "-c '/var/www/aeon-finale-formv1.2.3.6.5/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000'",
    cwd: "/var/www/aeon-finale-formv1.2.3.6.5/backend",
    out_file: "/var/log/aeon/out.log",
    error_file: "/var/log/aeon/error.log",
    env_file: "/var/www/aeon-finale-formv1.2.3.6.5/backend/.env",
    kill_timeout: 5000,
    restart_delay: 3000,
    max_restarts: 20,
    watch: false
  }]
};
