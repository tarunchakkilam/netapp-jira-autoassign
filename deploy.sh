#!/bin/bash
# Quick deployment script for production server

set -e

echo "🚀 Jira Auto-Assignment Service - Deployment Script"
echo "=================================================="

# Configuration
SERVICE_NAME="jira-autoassign"
INSTALL_DIR="/opt/$SERVICE_NAME"
SERVICE_USER="${USER}"
SERVICE_PORT="8000"

echo ""
echo "📋 Configuration:"
echo "   Install Directory: $INSTALL_DIR"
echo "   Service User: $SERVICE_USER"
echo "   Port: $SERVICE_PORT"
echo ""

read -p "Continue with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Installation cancelled"
    exit 1
fi

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Don't run this script as root. Run as your regular user."
    exit 1
fi

echo ""
echo "📦 Step 1: Creating installation directory..."
sudo mkdir -p $INSTALL_DIR
sudo chown $SERVICE_USER:$(id -gn) $INSTALL_DIR

echo ""
echo "📂 Step 2: Copying files..."
cp -r . $INSTALL_DIR/
cd $INSTALL_DIR

echo ""
echo "🐍 Step 3: Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "🔐 Step 4: Setting up environment..."
if [[ ! -f .env ]]; then
    echo "⚠️  .env file not found!"
    echo "Please create .env file with your Jira credentials:"
    echo "  JIRA_BASE_URL=https://jira.ngage.netapp.com"
    echo "  JIRA_EMAIL=your-email@netapp.com"
    echo "  JIRA_API_TOKEN=your-token"
    echo "  JIRA_USE_BEARER_AUTH=true"
    exit 1
fi

# Secure the .env file
chmod 600 .env

echo ""
echo "👥 Step 5: Loading team members..."
if [[ -f team_members.txt ]]; then
    PYTHONPATH=$INSTALL_DIR venv/bin/python3 scripts/load_team.py
else
    echo "⚠️  team_members.txt not found. Please create it before starting the service."
fi

echo ""
echo "📝 Step 6: Setting up systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Jira Auto-Assignment Service for Team Himalaya
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$(id -gn)
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"
ExecStart=$INSTALL_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "🔄 Step 7: Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo ""
echo "⏳ Waiting for service to start..."
sleep 5

echo ""
echo "🏥 Step 8: Checking service health..."
sudo systemctl status $SERVICE_NAME --no-pager

echo ""
echo "✅ Installation complete!"
echo ""
echo "📊 Service Information:"
echo "   Status: sudo systemctl status $SERVICE_NAME"
echo "   Logs:   sudo journalctl -u $SERVICE_NAME -f"
echo "   Stop:   sudo systemctl stop $SERVICE_NAME"
echo "   Start:  sudo systemctl start $SERVICE_NAME"
echo ""
echo "🌐 Service URL: http://$(hostname):$SERVICE_PORT"
echo "🏥 Health Check: curl http://localhost:$SERVICE_PORT/health"
echo "📈 Stats: curl http://localhost:$SERVICE_PORT/stats"
echo ""
echo "📝 Next Steps:"
echo "1. Test the service: curl http://localhost:$SERVICE_PORT/health"
echo "2. Configure Jira webhook to: http://$(hostname):$SERVICE_PORT/webhook"
echo "3. Monitor logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
