# JIRA Auto-Assignment Scheduler - Docker Deployment Guide

## 🐳 Deploy Using Docker Image

This guide shows how to build a Docker image and deploy it to a VM.

---

## Prerequisites

- VM with Docker installed (Ubuntu/RHEL/CentOS)
- Docker Compose (optional but recommended)
- SSH access to the VM
- Network access to:
  - jira.ngage.netapp.com
  - mailhost.netapp.com
  - NetApp LLM Proxy

---

## Deployment Options

### Option 1: Docker Compose (Recommended)
Deploys both ChromaDB and the scheduler in containers

### Option 2: Docker Only
Deploy scheduler container, connect to external ChromaDB

### Option 3: Build & Push to Registry
Build image, push to Docker registry, pull on VM

---

## Option 1: Docker Compose Deployment (RECOMMENDED)

### Step 1: Prepare Your Local Machine

#### 1.1 Package the Application
```bash
cd /Users/tc12411/JiraBot/netapp-jira-autoassign

# Create deployment package (excluding unnecessary files)
tar -czf jira-autoassign-docker.tar.gz \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='logs/*.log' \
  --exclude='chromadb-data' \
  app/ \
  scripts/ \
  requirements.txt \
  Dockerfile \
  docker-compose.yml \
  .env.example \
  README.md
```

#### 1.2 Copy .env File (with your credentials)
```bash
# Create a separate .env file for production
cp .env .env.production

# Edit to ensure correct values
nano .env.production
```

### Step 2: Transfer to VM

```bash
# Upload the package
scp jira-autoassign-docker.tar.gz your_username@your-vm-ip:/tmp/

# Upload the .env file
scp .env.production your_username@your-vm-ip:/tmp/.env
```

### Step 3: Setup on VM

#### 3.1 Connect to VM
```bash
ssh your_username@your-vm-ip
```

#### 3.2 Install Docker (if not installed)
```bash
# For Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# For RHEL/CentOS
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and log back in for group changes
exit
ssh your_username@your-vm-ip
```

#### 3.3 Extract and Setup
```bash
# Create application directory
sudo mkdir -p /opt/jira-autoassign
sudo chown $USER:$USER /opt/jira-autoassign
cd /opt/jira-autoassign

# Extract package
tar -xzf /tmp/jira-autoassign-docker.tar.gz
mv /tmp/.env .env

# Create logs directory
mkdir -p logs

# Verify files
ls -la
```

### Step 4: Initial Training (Before Starting Scheduler)

#### 4.1 Start Only ChromaDB First
```bash
cd /opt/jira-autoassign
docker-compose up -d chromadb

# Wait for ChromaDB to be ready
sleep 10
docker-compose logs chromadb
```

#### 4.2 Run Training Script
```bash
# Build the image first
docker-compose build jira-autoassign-scheduler

# Run training (one-time)
docker run --rm \
  --network jira-autoassign_default \
  --env-file .env \
  -e CHROMA_HOST=chromadb \
  -e CHROMA_PORT=8000 \
  jira-autoassign_jira-autoassign-scheduler \
  python scripts/fetch_and_train_by_team.py
```

#### 4.3 Verify Training
```bash
# Check ChromaDB status
docker run --rm \
  --network jira-autoassign_default \
  --env-file .env \
  -e CHROMA_HOST=chromadb \
  -e CHROMA_PORT=8000 \
  jira-autoassign_jira-autoassign-scheduler \
  python scripts/check_chromadb_status.py
```

### Step 5: Start the Scheduler

```bash
cd /opt/jira-autoassign

# Start all services (ChromaDB + Scheduler)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f jira-autoassign-scheduler
```

### Step 6: Monitor and Manage

#### View Logs
```bash
# Real-time logs
docker-compose logs -f jira-autoassign-scheduler

# Last 100 lines
docker-compose logs --tail=100 jira-autoassign-scheduler

# Check application logs
tail -f logs/auto_assign_scheduler.log
```

#### Container Management
```bash
# Stop services
docker-compose stop

# Start services
docker-compose start

# Restart services
docker-compose restart

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (WARNING: deletes ChromaDB data)
docker-compose down -v

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

#### Health Checks
```bash
# Check container health
docker ps

# Check ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Check scheduler process
docker exec jira-autoassign-scheduler pgrep -f auto_assign_scheduler.py
```

---

## Option 2: Docker Only (External ChromaDB)

If you already have ChromaDB running elsewhere:

### Build the Image
```bash
cd /opt/jira-autoassign
docker build -t jira-autoassign:latest .
```

### Run the Container
```bash
docker run -d \
  --name jira-autoassign-scheduler \
  --restart unless-stopped \
  --env-file .env \
  -e CHROMA_HOST=your-chromadb-host \
  -e CHROMA_PORT=8000 \
  -v $(pwd)/logs:/app/logs \
  jira-autoassign:latest
```

### Manage Container
```bash
# View logs
docker logs -f jira-autoassign-scheduler

# Stop container
docker stop jira-autoassign-scheduler

# Start container
docker start jira-autoassign-scheduler

# Restart container
docker restart jira-autoassign-scheduler

# Remove container
docker rm -f jira-autoassign-scheduler
```

---

## Option 3: Docker Registry Deployment

Push image to a registry (Docker Hub, Azure Container Registry, etc.) and pull on VM.

### On Your Local Machine

#### 3.1 Build and Tag Image
```bash
cd /Users/tc12411/JiraBot/netapp-jira-autoassign

# Build image
docker build -t jira-autoassign:latest .

# Tag for registry
docker tag jira-autoassign:latest your-registry/jira-autoassign:latest
docker tag jira-autoassign:latest your-registry/jira-autoassign:v1.0.0
```

#### 3.2 Push to Registry
```bash
# Login to registry
docker login your-registry

# Push images
docker push your-registry/jira-autoassign:latest
docker push your-registry/jira-autoassign:v1.0.0
```

### On VM

#### 3.3 Create docker-compose.yml on VM
```bash
ssh your_username@your-vm-ip
mkdir -p /opt/jira-autoassign
cd /opt/jira-autoassign
nano docker-compose.yml
```

Add:
```yaml
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    container_name: chromadb
    ports:
      - "8000:8000"
    volumes:
      - chromadb-data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
      - ANONYMIZED_TELEMETRY=FALSE
    restart: unless-stopped

  jira-autoassign-scheduler:
    image: your-registry/jira-autoassign:latest
    container_name: jira-autoassign-scheduler
    env_file:
      - .env
    environment:
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
    volumes:
      - ./logs:/app/logs
    depends_on:
      - chromadb
    restart: unless-stopped

volumes:
  chromadb-data:
```

#### 3.4 Create .env File
```bash
nano .env
# Add your configuration (see .env.example)
```

#### 3.5 Pull and Run
```bash
# Login to registry
docker login your-registry

# Pull and start
docker-compose pull
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## Running One-Time Scripts in Docker

### Test Email
```bash
docker-compose exec jira-autoassign-scheduler python scripts/test_email.py
```

### Predict Team for Ticket
```bash
docker-compose exec jira-autoassign-scheduler python scripts/simple_predict.py NFSAAS-XXXXX
```

### Find Unassigned Tickets
```bash
docker-compose exec jira-autoassign-scheduler python scripts/find_unassigned_tickets.py
```

### Check ChromaDB Status
```bash
docker-compose exec jira-autoassign-scheduler python scripts/check_chromadb_status.py
```

### Show Trained Teams
```bash
docker-compose exec jira-autoassign-scheduler python scripts/show_trained_teams.py
```

---

## Backup and Restore

### Backup ChromaDB Data
```bash
# Create backup
docker run --rm \
  -v jira-autoassign_chromadb-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/chromadb-backup-$(date +%Y%m%d).tar.gz -C /data .

# List backups
ls -lh chromadb-backup-*.tar.gz
```

### Restore ChromaDB Data
```bash
# Stop services
docker-compose down

# Restore backup
docker run --rm \
  -v jira-autoassign_chromadb-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/chromadb-backup-20251211.tar.gz"

# Start services
docker-compose up -d
```

### Backup Application Logs
```bash
# Compress logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# Copy to local machine
scp your_username@your-vm-ip:/opt/jira-autoassign/logs-backup-*.tar.gz .
```

---

## Updating the Application

### Method 1: Rebuild Image on VM
```bash
cd /opt/jira-autoassign

# Upload new code
scp jira-autoassign-docker.tar.gz your_username@your-vm-ip:/tmp/

# On VM
cd /opt/jira-autoassign
docker-compose down
tar -xzf /tmp/jira-autoassign-docker.tar.gz
docker-compose build --no-cache
docker-compose up -d
```

### Method 2: Pull from Registry
```bash
cd /opt/jira-autoassign

# Pull new version
docker-compose pull jira-autoassign-scheduler

# Restart with new image
docker-compose up -d jira-autoassign-scheduler

# Check logs
docker-compose logs -f jira-autoassign-scheduler
```

---

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs jira-autoassign-scheduler

# Check for errors
docker-compose logs jira-autoassign-scheduler 2>&1 | grep -i error

# Check container status
docker-compose ps

# Inspect container
docker inspect jira-autoassign-scheduler
```

### ChromaDB Connection Issues
```bash
# Check ChromaDB is running
docker-compose ps chromadb

# Test ChromaDB endpoint
docker-compose exec jira-autoassign-scheduler curl http://chromadb:8000/api/v1/heartbeat

# Check ChromaDB logs
docker-compose logs chromadb

# Restart ChromaDB
docker-compose restart chromadb
```

### Network Issues
```bash
# Check Docker networks
docker network ls

# Inspect network
docker network inspect jira-autoassign_default

# Test connectivity
docker-compose exec jira-autoassign-scheduler ping chromadb
```

### Permission Issues
```bash
# Fix log directory permissions
sudo chown -R $USER:$USER logs/

# Check volume permissions
docker-compose exec jira-autoassign-scheduler ls -la /app/logs
```

### Out of Memory
```bash
# Check container resource usage
docker stats

# Add memory limits to docker-compose.yml
services:
  jira-autoassign-scheduler:
    ...
    mem_limit: 2g
    memswap_limit: 2g
```

### Debug Mode
```bash
# Run container interactively
docker-compose run --rm jira-autoassign-scheduler /bin/bash

# Inside container:
python scripts/check_chromadb_status.py
python scripts/find_unassigned_tickets.py
python scripts/auto_assign_scheduler.py
```

---

## Monitoring and Maintenance

### Resource Usage
```bash
# Monitor containers
docker stats

# Check disk usage
docker system df

# Check volume sizes
docker volume ls
docker volume inspect jira-autoassign_chromadb-data
```

### Log Rotation (on VM)
```bash
# Configure Docker log rotation
sudo nano /etc/docker/daemon.json
```

Add:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:
```bash
sudo systemctl restart docker
docker-compose up -d
```

### Cleanup Old Images
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (BE CAREFUL!)
docker volume prune

# Full cleanup
docker system prune -a --volumes
```

### Auto-Start on Boot
Docker Compose with `restart: unless-stopped` will automatically start containers on boot if Docker is enabled:

```bash
# Enable Docker to start on boot
sudo systemctl enable docker
```

---

## Production Recommendations

### 1. Use a Reverse Proxy (Optional)
If you want to expose metrics or API endpoints:

```yaml
# Add to docker-compose.yml
nginx:
  image: nginx:alpine
  container_name: nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./ssl:/etc/nginx/ssl
  depends_on:
    - chromadb
  restart: unless-stopped
```

### 2. Setup Monitoring
```yaml
# Add Prometheus monitoring
prometheus:
  image: prom/prometheus
  container_name: prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
  restart: unless-stopped
```

### 3. Use Docker Secrets for Credentials
```yaml
services:
  jira-autoassign-scheduler:
    secrets:
      - jira_token
      - openai_key
    environment:
      - JIRA_API_TOKEN_FILE=/run/secrets/jira_token

secrets:
  jira_token:
    file: ./secrets/jira_token.txt
  openai_key:
    file: ./secrets/openai_key.txt
```

### 4. Resource Limits
```yaml
services:
  jira-autoassign-scheduler:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

---

## Quick Reference Commands

### Start/Stop
```bash
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose restart            # Restart all services
docker-compose stop               # Stop without removing
docker-compose start              # Start stopped services
```

### Logs
```bash
docker-compose logs -f                              # All services
docker-compose logs -f jira-autoassign-scheduler   # Specific service
docker-compose logs --tail=100                     # Last 100 lines
tail -f logs/auto_assign_scheduler.log             # Application log
```

### Execute Commands
```bash
docker-compose exec jira-autoassign-scheduler python scripts/test_email.py
docker-compose exec jira-autoassign-scheduler python scripts/simple_predict.py NFSAAS-XXXXX
docker-compose exec chromadb curl http://localhost:8000/api/v1/heartbeat
```

### Health Checks
```bash
docker-compose ps                 # Container status
docker stats                      # Resource usage
docker-compose logs --tail=50     # Recent logs
```

### Updates
```bash
docker-compose pull               # Pull new images
docker-compose build --no-cache   # Rebuild from scratch
docker-compose up -d              # Apply changes
```

---

## Environment Variables Reference

Required in `.env` file:

```bash
# JIRA
JIRA_BASE_URL=https://jira.ngage.netapp.com
JIRA_API_TOKEN=your_token
JIRA_EMAIL=your_email@netapp.com
JIRA_USE_BEARER_AUTH=true

# LLM
OPENAI_API_KEY=your_key
NETAPP_LLM_API_KEY=your_key
NETAPP_LLM_BASE_URL=https://your-proxy.netapp.com/v1
NETAPP_LLM_MODEL=gpt-4
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=1000

# ChromaDB (handled by docker-compose)
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# SMTP
SMTP_SERVER=mailhost.netapp.com
SMTP_PORT=25
SMTP_USER=your_email@netapp.com
SMTP_PASSWORD=
NOTIFICATION_EMAIL=your_email@netapp.com

# Other
SIMILARITY_THRESHOLD=0.35
ASSIGNMENT_METHOD=hybrid
```

---

## Success Criteria

✅ Both containers running: `docker-compose ps` shows "Up"  
✅ ChromaDB accessible: `curl http://localhost:8000/api/v1/heartbeat` returns 200  
✅ Scheduler processing tickets: Check `logs/auto_assign_scheduler.log`  
✅ No errors in logs: `docker-compose logs | grep -i error` shows minimal/no errors  
✅ Assignments working: Log shows "Successfully updated Technical Owner"  
✅ Containers restart automatically: Survives VM reboot  

---

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Check container health: `docker-compose ps`
3. Run debug commands inside container
4. Check application logs: `tail -f logs/auto_assign_scheduler.log`

---

**Docker Deployment Complete! 🐳**

Your scheduler is now running in containers with automatic restarts and easy management.
