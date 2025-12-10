#!/bin/bash
# Helper script to run the training with JIRA credentials

echo "🔐 JIRA Training Script"
echo "======================="
echo ""
echo "This script will fetch actual tickets assigned to each team from JIRA."
echo ""
echo "Please provide your JIRA credentials:"
echo ""
read -p "JIRA Username (email): " JIRA_USER
read -sp "JIRA API Token: " JIRA_TOKEN
echo ""
echo ""

export JIRA_USER="$JIRA_USER"
export JIRA_TOKEN="$JIRA_TOKEN"
export JIRA_URL="${JIRA_URL:-https://jira.eng.netapp.com}"

echo "🚀 Starting training..."
echo ""

PYTHONPATH=$PWD venv/bin/python3 scripts/fetch_and_train_by_team.py
