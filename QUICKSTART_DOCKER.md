# 🚀 Quick Start - Docker Deployment

Deploy JIRA Auto-Assignment Scheduler to a VM using Docker in 3 simple steps.

---

## Prerequisites

✅ VM with SSH access (Ubuntu/RHEL/CentOS)  
✅ Your `.env` file configured (see `.env.example`)  
✅ Network access from VM to JIRA, ChromaDB, and LLM proxy  

---

## Option 1: Automated Deployment (Recommended)

### Single Command Deployment

```bash
./deploy-docker.sh --vm-user your_username --vm-host your-vm-ip
```

This script will:
1. ✅ Package the application
2. ✅ Upload to VM
3. ✅ Install Docker (if needed)
4. ✅ Build images
5. ✅ Run initial training
6. ✅ Start services
7. ✅ Verify deployment

### Example

```bash
./deploy-docker.sh --vm-user tc12411 --vm-host 192.168.1.100
```

### Custom Path

```bash
./deploy-docker.sh \
  --vm-user tc12411 \
  --vm-host 192.168.1.100 \
  --vm-path /home/tc12411/jira-autoassign
```

---

## Option 2: Manual Docker Compose Deployment

### Step 1: Package and Upload

```bash
# On your local machine
cd /Users/tc12411/JiraBot/netapp-jira-autoassign

# Create package
tar -czf jira-autoassign.tar.gz \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='logs/*.log' \
  app/ scripts/ requirements.txt Dockerfile docker-compose.yml .env

# Upload to VM
scp jira-autoassign.tar.gz your_username@your-vm-ip:/tmp/
```

### Step 2: Setup on VM

```bash
# SSH to VM
ssh your_username@your-vm-ip

# Create directory
sudo mkdir -p /opt/jira-autoassign
sudo chown $USER:$USER /opt/jira-autoassign
cd /opt/jira-autoassign

# Extract
tar -xzf /tmp/jira-autoassign.tar.gz
mkdir -p logs
```

### Step 3: Install Docker (if needed)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in
exit
ssh your_username@your-vm-ip
```

### Step 4: Initial Training

```bash
cd /opt/jira-autoassign

# Start ChromaDB
docker-compose up -d chromadb
sleep 10

# Build image
docker-compose build jira-autoassign-scheduler

# Run training
docker run --rm \
  --network jira-autoassign_default \
  --env-file .env \
  -e CHROMA_HOST=chromadb \
  -e CHROMA_PORT=8000 \
  jira-autoassign_jira-autoassign-scheduler \
  python scripts/fetch_and_train_by_team.py
```

### Step 5: Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

---

## Verify Deployment

### Check Services

```bash
# Check container status
docker-compose ps

# Expected output:
#   chromadb                    Up
#   jira-autoassign-scheduler   Up
```

### Check ChromaDB

```bash
curl http://localhost:8000/api/v1/heartbeat

# Expected output:
# {"nanosecond heartbeat": ...}
```

### Check Scheduler

```bash
# View logs
docker-compose logs -f jira-autoassign-scheduler

# Check process
docker-compose exec jira-autoassign-scheduler pgrep -f auto_assign_scheduler.py

# Expected: Process ID number
```

### Test Email

```bash
docker-compose exec jira-autoassign-scheduler python scripts/test_email.py
```

### Check Application Logs

```bash
tail -f logs/auto_assign_scheduler.log
```

---

## Daily Operations

### View Logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Application log
tail -f logs/auto_assign_scheduler.log
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart scheduler only
docker-compose restart jira-autoassign-scheduler
```

### Stop/Start

```bash
# Stop all
docker-compose stop

# Start all
docker-compose start

# Stop and remove
docker-compose down
```

### Run Test Scripts

```bash
# Test email
docker-compose exec jira-autoassign-scheduler python scripts/test_email.py

# Predict team
docker-compose exec jira-autoassign-scheduler python scripts/simple_predict.py NFSAAS-XXXXX

# Find unassigned tickets
docker-compose exec jira-autoassign-scheduler python scripts/find_unassigned_tickets.py

# Check ChromaDB
docker-compose exec jira-autoassign-scheduler python scripts/check_chromadb_status.py
```

---

## Update Application

### Method 1: Replace Files

```bash
# On local machine, create new package
tar -czf jira-autoassign.tar.gz app/ scripts/ requirements.txt Dockerfile

# Upload
scp jira-autoassign.tar.gz your_username@your-vm-ip:/tmp/

# On VM
cd /opt/jira-autoassign
docker-compose down
tar -xzf /tmp/jira-autoassign.tar.gz
docker-compose build --no-cache
docker-compose up -d
```

### Method 2: Re-run Deploy Script

```bash
./deploy-docker.sh --vm-user your_username --vm-host your-vm-ip
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Check for errors
docker-compose logs 2>&1 | grep -i error

# Remove and recreate
docker-compose down
docker-compose up -d
```

### ChromaDB Connection Failed

```bash
# Restart ChromaDB
docker-compose restart chromadb

# Check ChromaDB logs
docker-compose logs chromadb

# Test connectivity
docker-compose exec jira-autoassign-scheduler curl http://chromadb:8000/api/v1/heartbeat
```

### No Tickets Being Processed

```bash
# Check application logs
docker-compose logs jira-autoassign-scheduler | tail -50

# Test JIRA connection
docker-compose exec jira-autoassign-scheduler python scripts/find_unassigned_tickets.py

# Check environment variables
docker-compose exec jira-autoassign-scheduler env | grep JIRA
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up
docker system prune -a
docker volume prune
```

---

## Backup

### Backup ChromaDB Data

```bash
# Create backup
docker run --rm \
  -v jira-autoassign_chromadb-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/chromadb-backup-$(date +%Y%m%d).tar.gz -C /data .
```

### Backup Logs

```bash
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/
```

### Restore ChromaDB

```bash
docker-compose down
docker run --rm \
  -v jira-autoassign_chromadb-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/chromadb-backup-20251211.tar.gz"
docker-compose up -d
```

---

## Remote Access Commands

From your local machine:

```bash
# View logs
ssh your_username@your-vm-ip 'cd /opt/jira-autoassign && docker-compose logs -f'

# Check status
ssh your_username@your-vm-ip 'cd /opt/jira-autoassign && docker-compose ps'

# Restart
ssh your_username@your-vm-ip 'cd /opt/jira-autoassign && docker-compose restart'

# View application logs
ssh your_username@your-vm-ip 'tail -50 /opt/jira-autoassign/logs/auto_assign_scheduler.log'
```

---

## File Structure on VM

```
/opt/jira-autoassign/
├── app/
│   ├── jira_client.py
│   └── enhanced_chroma_client.py
├── scripts/
│   ├── auto_assign_scheduler.py    (Main scheduler)
│   ├── fetch_and_train_by_team.py  (Training)
│   ├── test_email.py               (Test SMTP)
│   └── simple_predict.py           (Test predictions)
├── logs/
│   └── auto_assign_scheduler.log   (Application logs)
├── docker-compose.yml              (Service definition)
├── Dockerfile                      (Image definition)
├── requirements.txt                (Dependencies)
└── .env                            (Configuration)
```

---

## Success Checklist

- [x] Both containers show "Up" status
- [x] ChromaDB heartbeat responds
- [x] Scheduler process is running
- [x] Logs show "Found X issues" every 5 minutes
- [x] Successful assignments appear in logs
- [x] Email notifications working
- [x] No error messages in logs
- [x] Containers survive VM reboot

---

## Getting Help

### Check Documentation

- `DOCKER_DEPLOYMENT.md` - Complete Docker deployment guide
- `DEPLOYMENT_GUIDE.md` - Manual VM deployment guide
- `README.md` - Project overview

### Debug Commands

```bash
# Container shell access
docker-compose exec jira-autoassign-scheduler /bin/bash

# Check Python environment
docker-compose exec jira-autoassign-scheduler python --version
docker-compose exec jira-autoassign-scheduler pip list

# Network debugging
docker-compose exec jira-autoassign-scheduler ping chromadb
docker-compose exec jira-autoassign-scheduler curl http://chromadb:8000/api/v1/heartbeat
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Deploy | `./deploy-docker.sh --vm-user USER --vm-host HOST` |
| Start | `docker-compose up -d` |
| Stop | `docker-compose down` |
| Restart | `docker-compose restart` |
| Logs | `docker-compose logs -f` |
| Status | `docker-compose ps` |
| Update | Rebuild with `docker-compose build --no-cache` |
| Backup | `tar czf backup.tar.gz logs/ .env` |

---

**🎉 You're all set! The scheduler will now automatically process unassigned Azure tickets every 5 minutes.**
