# gunicorn settings for the TSCE portal (used by systemd/tsce-gunicorn.service).
bind = "unix:/run/tsce/gunicorn.sock"
umask = 0o007            # socket readable by the tsce group (nginx's www-data is a member)
# One process with threads: ~100 MB instead of ~300 MB for three workers. The VPS is
# shared and short of memory; a school's admissions traffic fits comfortably in this.
workers = 1
worker_class = "gthread"
threads = 4
timeout = 90             # a request may wait up to 30 s on Zainpay
graceful_timeout = 30
max_requests = 1000      # recycle workers now and then
max_requests_jitter = 100
accesslog = "-"          # → journald (journalctl -u tsce-gunicorn)
errorlog = "-"
loglevel = "info"
