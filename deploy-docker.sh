#!/bin/bash

# JIRA Auto-Assignment - Quick Docker Deployment Script
# This script packages and deploys the application to a VM using Docker

set -e

echo "==================================="
echo "JIRA Auto-Assignment Docker Deploy"
echo "==================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
VM_USER=""
VM_HOST=""
VM_PATH="/opt/jira-autoassign"
DEPLOY_METHOD="compose"  # compose, docker, or registry

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --vm-user)
            VM_USER="$2"
            shift 2
            ;;
        --vm-host)
            VM_HOST="$2"
            shift 2
            ;;
        --vm-path)
            VM_PATH="$2"
            shift 2
            ;;
        --method)
            DEPLOY_METHOD="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --vm-user <user> --vm-host <host> [options]"
            echo ""
            echo "Options:"
            echo "  --vm-user <user>     SSH username for VM (required)"
            echo "  --vm-host <host>     VM hostname or IP (required)"
            echo "  --vm-path <path>     Installation path on VM (default: /opt/jira-autoassign)"
            echo "  --method <method>    Deployment method: compose, docker, or registry (default: compose)"
            echo "  --help               Show this help message"
            echo ""
            echo "Example:"
            echo "  $0 --vm-user tc12411 --vm-host 192.168.1.100 --method compose"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$VM_USER" ] || [ -z "$VM_HOST" ]; then
    echo -e "${RED}Error: --vm-user and --vm-host are required${NC}"
    echo "Run '$0 --help' for usage information"
    exit 1
fi

VM_SSH="$VM_USER@$VM_HOST"

echo -e "${GREEN}Configuration:${NC}"
echo "  VM: $VM_SSH"
echo "  Path: $VM_PATH"
echo "  Method: $DEPLOY_METHOD"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file with your configuration"
    exit 1
fi

# Step 1: Create deployment package
echo -e "${YELLOW}Step 1: Creating deployment package...${NC}"
PACKAGE_NAME="jira-autoassign-docker.tar.gz"

tar -czf "$PACKAGE_NAME" \
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
    README.md \
    2>/dev/null || true

echo -e "${GREEN}✓ Package created: $PACKAGE_NAME${NC}"
echo ""

# Step 2: Test SSH connection
echo -e "${YELLOW}Step 2: Testing SSH connection...${NC}"
echo "Attempting to connect to $VM_SSH..."
if ssh -o ConnectTimeout=10 "$VM_SSH" "echo 'SSH connection successful'" 2>&1; then
    echo -e "${GREEN}✓ SSH connection successful${NC}"
else
    echo -e "${RED}✗ SSH connection failed${NC}"
    echo "Please check your SSH credentials and ensure you can connect to the VM"
    exit 1
fi
echo ""

# Step 3: Upload files
echo -e "${YELLOW}Step 3: Uploading files to VM...${NC}"
scp "$PACKAGE_NAME" "$VM_SSH:/tmp/" || {
    echo -e "${RED}✗ Failed to upload package${NC}"
    exit 1
}

scp .env "$VM_SSH:/tmp/.env" || {
    echo -e "${RED}✗ Failed to upload .env file${NC}"
    exit 1
}

echo -e "${GREEN}✓ Files uploaded${NC}"
echo ""

# Step 4: Setup on VM
echo -e "${YELLOW}Step 4: Setting up on VM...${NC}"
echo "You may be prompted for your sudo password on the VM..."

# Create directory with sudo (interactive) - hardcode the username to avoid shell issues
ssh -t "$VM_SSH" "sudo mkdir -p $VM_PATH && sudo chown $VM_USER:$VM_USER $VM_PATH"

# Extract files (no sudo needed)
ssh "$VM_SSH" "cd $VM_PATH && tar -xzf /tmp/$PACKAGE_NAME && mv /tmp/.env .env && mkdir -p logs && echo 'Files extracted successfully'"

# Check and install Docker
echo "Checking Docker installation..."
ssh "$VM_SSH" bash << 'ENDSSH'
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    sudo usermod -aG docker $USER
    rm /tmp/get-docker.sh
    echo ""
    echo "=========================================="
    echo "Docker installed successfully!"
    echo "You need to log out and back in for Docker permissions to take effect."
    echo "Then re-run this script."
    echo "=========================================="
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose not found. Installing..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed successfully!"
fi

echo "Docker is ready!"
ENDSSH

if [ $? -ne 0 ]; then
    echo -e "${RED}Setup failed. Please check the output above.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ VM setup complete${NC}"
echo ""

# Step 5: Deploy based on method
case $DEPLOY_METHOD in
    compose)
        echo -e "${YELLOW}Step 5: Deploying with Docker Compose...${NC}"
        
        echo "Starting ChromaDB..."
        ssh "$VM_SSH" "cd $VM_PATH && docker-compose up -d chromadb"
        echo "Waiting for ChromaDB to be ready..."
        sleep 10

        echo "Building application image..."
        ssh "$VM_SSH" "cd $VM_PATH && docker-compose build jira-autoassign-scheduler"

        echo "Running initial training (this may take a few minutes)..."
        ssh "$VM_SSH" "cd $VM_PATH && docker run --rm --network jira-autoassign_default --env-file .env -e CHROMA_HOST=chromadb -e CHROMA_PORT=8000 jira-autoassign_jira-autoassign-scheduler python scripts/fetch_and_train_by_team.py"

        echo "Starting scheduler..."
        ssh "$VM_SSH" "cd $VM_PATH && docker-compose up -d"

        echo ""
        echo "Waiting for services to start..."
        sleep 5

        echo ""
        echo "Service status:"
        ssh "$VM_SSH" "cd $VM_PATH && docker-compose ps"
        ;;
    
    docker)
        echo -e "${YELLOW}Step 5: Deploying with Docker...${NC}"
        
        echo "Building image..."
        ssh "$VM_SSH" "cd $VM_PATH && docker build -t jira-autoassign:latest ."

        echo "Running container..."
        ssh "$VM_SSH" "cd $VM_PATH && docker run -d --name jira-autoassign-scheduler --restart unless-stopped --env-file .env -v \$(pwd)/logs:/app/logs jira-autoassign:latest"

        echo ""
        echo "Container status:"
        ssh "$VM_SSH" "docker ps -f name=jira-autoassign-scheduler"
        ;;
    
    registry)
        echo -e "${YELLOW}Step 5: Building and pushing to registry...${NC}"
        echo "Registry deployment requires manual configuration."
        echo "Please follow the instructions in DOCKER_DEPLOYMENT.md"
        ;;
    
    *)
        echo -e "${RED}Unknown deployment method: $DEPLOY_METHOD${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}✓ Deployment complete${NC}"
echo ""

# Step 6: Verify deployment
echo -e "${YELLOW}Step 6: Verifying deployment...${NC}"

if [ "$DEPLOY_METHOD" = "compose" ]; then
    echo "Checking ChromaDB..."
    ssh "$VM_SSH" "curl -s http://localhost:8000/api/v1/heartbeat > /dev/null && echo '✓ ChromaDB is running' || echo '✗ ChromaDB is not responding'"

    echo ""
    echo "Checking scheduler..."
    ssh "$VM_SSH" "cd $VM_PATH && docker-compose exec -T jira-autoassign-scheduler pgrep -f auto_assign_scheduler.py > /dev/null && echo '✓ Scheduler process is running' || echo '✗ Scheduler process not found'"

    echo ""
    echo "Recent logs:"
    ssh "$VM_SSH" "cd $VM_PATH && docker-compose logs --tail=20 jira-autoassign-scheduler"
fi

echo ""
echo -e "${GREEN}==================================="
echo "Deployment Summary"
echo "===================================${NC}"
echo ""
echo "Application deployed to: $VM_SSH:$VM_PATH"
echo ""
echo "Useful commands:"
echo ""
echo "  # View logs"
echo "  ssh $VM_SSH 'cd $VM_PATH && docker-compose logs -f'"
echo ""
echo "  # Check status"
echo "  ssh $VM_SSH 'cd $VM_PATH && docker-compose ps'"
echo ""
echo "  # Restart services"
echo "  ssh $VM_SSH 'cd $VM_PATH && docker-compose restart'"
echo ""
echo "  # Stop services"
echo "  ssh $VM_SSH 'cd $VM_PATH && docker-compose down'"
echo ""
echo "  # Test email"
echo "  ssh $VM_SSH 'cd $VM_PATH && docker-compose exec jira-autoassign-scheduler python scripts/test_email.py'"
echo ""
echo -e "${GREEN}Deployment successful! 🚀${NC}"

# Cleanup local package
rm -f "$PACKAGE_NAME"
