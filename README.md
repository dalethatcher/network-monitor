# network-monitor
Simple python script to do some basic network checks.

## Install

```shell
sudo apt install python3-venv rclone sqlite3
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
mkdir ~/log
```

## Launch at Startup


### systemd config file ~/.config/systemd/user/network-monitor.service

```
[Unit]
Description=Network monitor

[Service]
ExecStart=/home/YOURUSER/bin/run-network-monitor.sh

[Install]
WantedBy=default.target
```

### Enable

```shell
systemctl --user enable network-monitor.service
```

### launch script ~/bin/run-network-monitor.sh

```shell
#!/bin/sh

cd ~/network-monitor
. venv/bin/activate
exec python app.py >> ~/log/network-monitor.log 2>&1
```

## Backup

### backup script ~/bin/backup.sh

```shell
#!/bin/sh

rclone copy ~/network-monitor/monitor-db.sqlite gdrive:network-monitor
```
