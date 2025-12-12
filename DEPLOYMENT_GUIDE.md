# JIRA Auto-Assignment Scheduler - VM Deployment Guide

## Prerequisites
- Fresh VM (Linux - Ubuntu/RHEL/CentOS)
- SSH access to the VM
- Root or sudo privileges
- Network access to:
  - jira.ngage.netapp.com
  - ChromaDB server (localhost:8000 or remote)
  - mailhost.netapp.com (for email notifications)
  - NetApp LLM Proxy

---

## Step 1: Initial VM Setup

### 1.1 Connect to VM
```bash
ssh your_username@your-vm-ip
```

### 1.2 Update System Packages
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# RHEL/CentOS
sudo yum update -y
```

### 1.3 Install Required System Packages
```bash
# Ubuntu/Debian
sudo apt install -y python3.11 python3.11-venv python3-pip git curl

# RHEL/CentOS
sudo yum install -y python3.11 python3.11-devel git curl
```

---

## Step 2: Setup Application Directory

### 2.1 Create Application Directory
```bash
sudo mkdir -p /opt/jira-autoassign
sudo chown $USER:$USER /opt/jira-autoassign
cd /opt/jira-autoassign
```

### 2.2 Clone or Upload Code
**Option A: Using Git (if you have a repository)**
```bash
git clone https://github.com/tarunchakkilam/netapp-jira-autoassign.git .
```

**Option B: Manual Upload (from your local machine)**
```bash
# On your local machine (Mac):
cd /Users/tc12411/JiraBot/netapp-jira-autoassign
tar -czf jira-autoassign.tar.gz \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='logs/*.log' \
  app/ scripts/ requirements.txt .env

# Upload to VM
scp jira-autoassign.tar.gz your_username@your-vm-ip:/opt/jira-autoassign/

# On VM, extract:
cd /opt/jira-autoassign
tar -xzf jira-autoassign.tar.gz
rm jira-autoassign.tar.gz
```

---

## Step 3: Python Virtual Environment Setup

### 3.1 Create Virtual Environment
```bash
cd /opt/jira-autoassign
python3.11 -m venv venv
```

### 3.2 Activate Virtual Environment
```bash
source venv/bin/activate
```

### 3.3 Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.4 Verify Installation
```bash
python -c "import chromadb, openai, requests; print('All packages installed successfully!')"
```

---

## Step 4: Configure Environment Variables

### 4.1 Create/Edit .env File
```bash
cd /opt/jira-autoassign
nano .env
```

### 4.2 Add Configuration (use your actual values)
```bash
# JIRA Configuration
JIRA_BASE_URL=https://jira.ngage.netapp.com
JIRA_API_TOKEN=your_bearer_token_here
JIRA_EMAIL=your_email@netapp.com
JIRA_USE_BEARER_AUTH=true

# OpenAI/LLM Configuration
OPENAI_API_KEY=your_api_key_here
NETAPP_LLM_API_KEY=your_netapp_llm_key_here
NETAPP_LLM_BASE_URL=https://your-llm-proxy.netapp.com/v1
NETAPP_LLM_MODEL=gpt-4
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=1000

# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000

# SMTP Configuration (NetApp Internal)
SMTP_SERVER=mailhost.netapp.com
SMTP_PORT=25
SMTP_USER=your_email@netapp.com
SMTP_PASSWORD=
NOTIFICATION_EMAIL=your_email@netapp.com

# Other Settings
SIMILARITY_THRESHOLD=0.35
ASSIGNMENT_METHOD=hybrid
ASSIGNMENT_LABEL=auto-assigned
```

### 4.3 Secure the .env File
```bash
chmod 600 .env
```

---

## Step 5: Setup ChromaDB (if not already running)

### 5.1 Check if ChromaDB is Running
```bash
curl http://localhost:8000/api/v1/heartbeat
```

### 5.2 If Not Running, Start ChromaDB
**Option A: Using Docker (Recommended)**
```bash
# Install Docker if not present
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Run ChromaDB
sudo docker run -d \
  --name chromadb \
  -p 8000:8000 \
  -v /opt/chromadb-data:/chroma/chroma \
  --restart unless-stopped \
  chromadb/chroma:latest
```

**Option B: Manual Python Installation**
```bash
# In a separate directory
mkdir -p /opt/chromadb
cd /opt/chromadb
python3.11 -m venv venv
source venv/bin/activate
pip install chromadb
chroma run --host 0.0.0.0 --port 8000 --path /opt/chromadb-data
```

### 5.3 Verify ChromaDB Status
```bash
cd /opt/jira-autoassign
source venv/bin/activate
python scripts/check_chromadb_status.py
```

---

## Step 6: Initial Training (Load Tickets into ChromaDB)

### 6.1 Run Training Script
```bash
cd /opt/jira-autoassign
source venv/bin/activate
python scripts/fetch_and_train_by_team.py
```

### 6.2 Verify Training
```bash
python scripts/show_trained_teams.py
```

Expected output: List of teams with ticket counts (should have ~5,000+ tickets total)

---

## Step 7: Test the Scheduler Manually

### 7.1 Test Email Configuration
```bash
python scripts/test_email.py
```

### 7.2 Test Team Prediction
```bash
python scripts/simple_predict.py NFSAAS-XXXXX
# Replace NFSAAS-XXXXX with an actual ticket number
```

### 7.3 Test Finding Unassigned Tickets
```bash
python scripts/find_unassigned_tickets.py
```

### 7.4 Run Scheduler Once (Dry Run)
```bash
python scripts/auto_assign_scheduler.py
# Press Ctrl+C after it processes one batch
```

Check logs:
```bash
tail -50 logs/auto_assign_scheduler.log
```

---

## Step 8: Create Systemd Service (Production)

### 8.1 Create Service File
```bash
sudo nano /etc/systemd/system/jira-autoassign.service
```

### 8.2 Add Service Configuration
```ini
[Unit]
Description=JIRA Auto-Assignment Scheduler
After=network.target

[Service]
Type=simple
User=tc12411
Group=tc12411
WorkingDirectory=/opt/jira-autoassign
Environment="PATH=/opt/jira-autoassign/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/jira-autoassign/venv/bin/python3.11 /opt/jira-autoassign/scripts/auto_assign_scheduler.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/jira-autoassign/logs/systemd.log
StandardError=append:/opt/jira-autoassign/logs/systemd-error.log

[Install]
WantedBy=multi-user.target
```

### 8.3 Create Log Directory
```bash
mkdir -p /opt/jira-autoassign/logs
```

### 8.4 Reload Systemd and Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable jira-autoassign.service
```

---

## Step 9: Start and Monitor the Service

### 9.1 Start the Service
```bash
sudo systemctl start jira-autoassign.service
```

### 9.2 Check Service Status
```bash
sudo systemctl status jira-autoassign.service
```

Expected output:
```
● jira-autoassign.service - JIRA Auto-Assignment Scheduler
   Loaded: loaded (/etc/systemd/system/jira-autoassign.service; enabled)
   Active: active (running) since Wed 2025-12-11 15:30:00 UTC
```

### 9.3 Monitor Logs in Real-Time
```bash
# Application logs
tail -f /opt/jira-autoassign/logs/auto_assign_scheduler.log

# Systemd logs
sudo journalctl -u jira-autoassign.service -f
```

### 9.4 Check Service Commands
```bash
# Stop service
sudo systemctl stop jira-autoassign.service

# Restart service
sudo systemctl restart jira-autoassign.service

# View recent logs
sudo journalctl -u jira-autoassign.service -n 100 --no-pager
```

---

## Step 10: Monitoring and Maintenance

### 10.1 Setup Log Rotation
```bash
sudo nano /etc/logrotate.d/jira-autoassign
```

Add:
```
/opt/jira-autoassign/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 tc12411 tc12411
    sharedscripts
    postrotate
        systemctl reload jira-autoassign.service > /dev/null 2>&1 || true
    endscript
}
```

### 10.2 Monitor Disk Space
```bash
df -h /opt/jira-autoassign
du -sh /opt/jira-autoassign/logs/
```

### 10.3 Check ChromaDB Storage
```bash
du -sh /opt/chromadb-data/
```

### 10.4 Regular Maintenance Commands
```bash
# Check service status
sudo systemctl status jira-autoassign.service

# View last 100 log lines
tail -100 /opt/jira-autoassign/logs/auto_assign_scheduler.log

# Check for errors
grep -i "error\|exception\|failed" /opt/jira-autoassign/logs/auto_assign_scheduler.log | tail -20

# Count successful assignments today
grep "Successfully updated Technical Owner" /opt/jira-autoassign/logs/auto_assign_scheduler.log | grep "$(date +%Y-%m-%d)" | wc -l
```

---

## Step 11: Troubleshooting

### 11.1 Service Won't Start
```bash
# Check service logs
sudo journalctl -u jira-autoassign.service -n 50

# Check Python errors
/opt/jira-autoassign/venv/bin/python3.11 /opt/jira-autoassign/scripts/auto_assign_scheduler.py
```

### 11.2 No Tickets Being Processed
```bash
# Test JIRA connection
python scripts/find_unassigned_tickets.py

# Check ChromaDB connection
python scripts/check_chromadb_status.py

# Verify environment variables
cd /opt/jira-autoassign && source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('JIRA_BASE_URL:', os.getenv('JIRA_BASE_URL'))"
```

### 11.3 Email Notifications Not Working
```bash
# Test email
python scripts/test_email.py

# Check SMTP connectivity
telnet mailhost.netapp.com 25
```

### 11.4 ChromaDB Connection Issues
```bash
# Check if ChromaDB is running
curl http://localhost:8000/api/v1/heartbeat

# Restart ChromaDB (if using Docker)
sudo docker restart chromadb

# Check ChromaDB logs (if using Docker)
sudo docker logs chromadb --tail 50
```

---

## Step 12: Updating the Application

### 12.1 Stop the Service
```bash
sudo systemctl stop jira-autoassign.service
```

### 12.2 Backup Current Version
```bash
cd /opt
sudo tar -czf jira-autoassign-backup-$(date +%Y%m%d).tar.gz jira-autoassign/
```

### 12.3 Update Code
```bash
# If using git
cd /opt/jira-autoassign
git pull

# If manual upload, upload new tar.gz and extract
```

### 12.4 Update Dependencies (if requirements.txt changed)
```bash
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### 12.5 Restart Service
```bash
sudo systemctl start jira-autoassign.service
sudo systemctl status jira-autoassign.service
```

---

## Quick Reference Commands

### Service Management
```bash
# Start
sudo systemctl start jira-autoassign.service

# Stop
sudo systemctl stop jira-autoassign.service

# Restart
sudo systemctl restart jira-autoassign.service

# Status
sudo systemctl status jira-autoassign.service

# Enable auto-start
sudo systemctl enable jira-autoassign.service

# Disable auto-start
sudo systemctl disable jira-autoassign.service
```

### Log Viewing
```bash
# Real-time application logs
tail -f /opt/jira-autoassign/logs/auto_assign_scheduler.log

# Real-time systemd logs
sudo journalctl -u jira-autoassign.service -f

# Last 100 lines
tail -100 /opt/jira-autoassign/logs/auto_assign_scheduler.log

# Search for errors
grep -i error /opt/jira-autoassign/logs/auto_assign_scheduler.log | tail -20
```

### Testing
```bash
cd /opt/jira-autoassign
source venv/bin/activate

# Test email
python scripts/test_email.py

# Test prediction
python scripts/simple_predict.py NFSAAS-XXXXX

# Find unassigned tickets
python scripts/find_unassigned_tickets.py

# Check ChromaDB
python scripts/check_chromadb_status.py
```

---

## Security Checklist

- [ ] .env file has 600 permissions (readable only by owner)
- [ ] Service runs as non-root user
- [ ] JIRA API token is valid and has minimum required permissions
- [ ] VM firewall allows outbound HTTPS to JIRA and LLM proxy
- [ ] VM firewall allows connection to ChromaDB (port 8000) if remote
- [ ] Logs directory has appropriate permissions
- [ ] No sensitive credentials in logs

---

## Expected Behavior

### Normal Operation
- Scheduler runs every 5 minutes (300 seconds)
- Each run queries for unassigned Azure tickets
- Processes each ticket:
  - Skips if Technical Owner already set
  - Predicts team using ChromaDB + GPT-4
  - Assigns if confidence > 50%
  - Sends email notification on success
- Logs detailed information for each ticket
- Job summary logged after each run

### Performance Metrics
- Typical processing time: 5-15 seconds per ticket
- Memory usage: ~200-500 MB
- CPU usage: Low (spikes during LLM calls)
- Log file growth: ~10-50 KB per day

---

## Support Contacts

- **JIRA Issues**: NetApp IT Support
- **ChromaDB Issues**: Check documentation at https://docs.trychroma.com
- **LLM Proxy Issues**: NetApp AI/ML Team
- **Application Issues**: tc12411@netapp.com

---

## Appendix: File Structure

```
/opt/jira-autoassign/
├── app/
│   ├── __init__.py
│   ├── jira_client.py                  # JIRA API client
│   └── enhanced_chroma_client.py       # ChromaDB + GPT-4 prediction
├── scripts/
│   ├── auto_assign_scheduler.py        # Main scheduler (RUN THIS)
│   ├── fetch_and_train_by_team.py      # Initial training
│   ├── check_chromadb_status.py        # Health check
│   ├── simple_predict.py               # Test predictions
│   ├── find_unassigned_tickets.py      # Query unassigned
│   ├── test_email.py                   # Test SMTP
│   └── show_trained_teams.py           # Show teams
├── logs/
│   ├── auto_assign_scheduler.log       # Application logs
│   ├── systemd.log                     # Systemd stdout
│   └── systemd-error.log               # Systemd stderr
├── venv/                               # Python virtual environment
├── requirements.txt                    # Python dependencies
├── .env                                # Configuration (SECURE THIS!)
└── README.md                           # Project documentation
```

---

## Success Criteria

✅ Service is running: `sudo systemctl status jira-autoassign.service` shows "active (running)"  
✅ Logs are being written: `tail -f logs/auto_assign_scheduler.log` shows new entries every 5 minutes  
✅ Tickets are being processed: Log shows "Found X issues" with ticket counts  
✅ Assignments are successful: Log shows "Successfully updated Technical Owner"  
✅ Email notifications working: Recipients receive assignment notifications  
✅ No errors in logs: No Python exceptions or JIRA API errors  

---

**Deployment Complete! 🚀**

The scheduler will now run automatically every 5 minutes, processing unassigned Azure tickets and assigning them to the appropriate teams.
