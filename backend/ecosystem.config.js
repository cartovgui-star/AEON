module.exports = {
  apps: [{
    name: "aeon-backend",
    script: "/bin/bash",
    args: "-c 'venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000'",
    cwd: "/root/aeon-finale-formv1.2.3.6/backend",
    uid: "aeon",
    gid: "aeon",
    out_file: "/var/log/aeon/out.log",
    error_file: "/var/log/aeon/error.log",
    env_file: "/root/aeon-finale-formv1.2.3.6/backend/.env",
    kill_timeout: 5000,
    restart_delay: 3000,
    max_restarts: 20,
    watch: false
  }]
};
