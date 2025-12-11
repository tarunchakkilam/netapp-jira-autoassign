# JIRA Team Auto-Assignment System

An intelligent team assignment system using embeddings and vector similarity to automatically route JIRA tickets to the appropriate team based on historical patterns.

## 🎯 Overview

This system uses OpenAI embeddings and ChromaDB to learn from historical JIRA ticket assignments and predict the best team for new tickets. It achieves 60-75% confidence on clear matches by finding similar historical tickets and using majority voting.

**Key Features:**
- 🤖 Automated webhook-based ticket assignment for NFSAAS Bug tickets (ANF cloud provider only)
- 🧠 LLM-enhanced predictions using GPT-4 for intelligent team matching
- 📧 Email notifications with detailed prediction analysis and LLM reasoning
- 🎯 Embedding-based similarity matching using ChromaDB
- 📊 5,273 tickets from 11 teams (90-day training window)
- 🔍 Smart filtering: NFSAAS + Bug + ANF (Azure NetApp Files) + No owner

## 🏗️ Architecture

- **Embedding Model**: OpenAI text-embedding-ada-002 (1536 dimensions)
- **Vector Database**: ChromaDB for similarity search
- **Training Data**: 5,273 tickets from 11 teams (90-day window)
- **Prediction Method**: K-nearest neighbors (k=20) with majority voting
- **Webhook Server**: Flask-based webhook receiver
- **Email System**: SMTP-based HTML notifications

## 📋 Prerequisites

- Python 3.9+
- ChromaDB server running on localhost:8000
- JIRA API access with Bearer token authentication
- Access to NetApp LLM proxy for OpenAI embeddings
- SMTP server for email notifications

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/tarunchakkilam/netapp-jira-autoassign.git
cd netapp-jira-autoassign

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file with your credentials:

```bash
# JIRA Configuration
JIRA_URL=https://your-jira-instance.atlassian.net
JIRA_TOKEN=your_jira_bearer_token

# OpenAI Configuration (via NetApp LLM Proxy)
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=https://llm-proxy-api.ai.openeng.netapp.com/v1

# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Email/SMTP Configuration
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_smtp_password
NOTIFICATION_EMAIL=tc12411@netapp.com

# Webhook Server Configuration
WEBHOOK_PORT=5000
WEBHOOK_HOST=0.0.0.0
```

### 3. Start ChromaDB

```bash
# Install ChromaDB if not already installed
pip install chromadb

# Start ChromaDB server
chroma run --host localhost --port 8000
```

### 4. Train the Model

Fetch tickets from JIRA and train embeddings for all teams:

```bash
PYTHONPATH=$PWD venv/bin/python3 scripts/fetch_and_train_by_team.py
```

This will:
- Fetch tickets from the last 90 days for each team
- Generate embeddings using OpenAI
- Store in ChromaDB for similarity search
- Cache data in `data/team_assigned_tickets_90days.json`

### 5. Test Predictions (Optional)

```bash
# Predict team for a specific ticket
PYTHONPATH=$PWD venv/bin/python3 scripts/simple_predict.py NFSAAS-148584

# Output example:
# 🎯 Predicted Team: TEAM-SUPERNOVA
# 📈 Confidence: 60.0% (12/20 votes)
```

### 6. Start Webhook Server

```bash
# Start the Flask webhook server
PYTHONPATH=$PWD python scripts/webhook_server.py
```

The server will start on `http://0.0.0.0:5000` (or your configured port).

## 📁 Project Structure

```
netapp-jira-autoassign/
├── app/
│   ├── enhanced_chroma_client.py  # Main ChromaDB + embeddings client (with webhook & email methods)
│   └── jira_client.py            # JIRA API client
├── scripts/
│   ├── fetch_and_train_by_team.py # Training script
│   ├── simple_predict.py         # Prediction script
│   ├── webhook_server.py         # Flask webhook server
│   ├── check_chromadb_status.py  # Check DB status

│   ├── show_trained_teams.py     # View trained teams
│   └── find_unassigned_tickets.py # Find tickets to assign
├── data/                         # Training data cache
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
└── README.md                     # This file
```

## 🔧 Utility Scripts

### Check ChromaDB Status

```bash
PYTHONPATH=$PWD venv/bin/python3 scripts/check_chromadb_status.py

```

```bash

Shows collection stats, sample tickets, and tests the assignment system.# Auto-discover all developers from your team

curl -X POST http://localhost:8000/admin/auto-discover

### Show Trained Teams```



```bashThis will:

PYTHONPATH=$PWD venv/bin/python3 scripts/show_trained_teams.py- Find all developers from your team's recent tickets

```- Fetch their ticket history automatically

- Build profiles from their actual work

Displays which teams have training data and ticket counts.- Count their current workload

- Add them to the database

### Find Unassigned Tickets

See [AUTOMATIC_PROFILES.md](AUTOMATIC_PROFILES.md) for details.

```bash

PYTHONPATH=$PWD venv/bin/python3 scripts/find_unassigned_tickets.py**📝 MANUAL METHOD (Optional):**

```

If you prefer manual setup, edit `dev_profiles.csv`:

Lists recent JIRA tickets without a Technical Owner.

```csv

## 🎓 How It Worksname,accountId,capacity,open_count,history_text

Alice Johnson,5f8a9b1c2d3e4f5g6h7i8j9k,10,3,"Backend API development REST services..."

1. **Training Phase**:Bob Smith,6g9h0i1j2k3l4m5n6o7p8q9r,8,5,"Frontend development React TypeScript..."

   - Fetch historical tickets from JIRA (last 90 days)```

   - Extract summary + description for each ticket

   - Generate 1536-dimensional embeddings using OpenAIFind account IDs: Go to Jira user profile → URL shows `{accountId}`

   - Store embeddings in ChromaDB with team labels

### 5. Run the Service

2. **Prediction Phase**:

   - Fetch new ticket from JIRA```bash

   - Generate embedding for ticket content# Run with uvicorn

   - Query ChromaDB for 20 most similar ticketsuvicorn app.main:app --reload --host 0.0.0.0 --port 8000

   - Count team votes from similar tickets

   - Return team with most votes + confidence score# Or run directly

python -m app.main

## 📊 Current Training Data```



- **Total Tickets**: 5,273The service will start on `http://localhost:8000`

- **Teams**: 11 (team-sirius, team-vega, team-nandi, team-himalaya, etc.)

- **Time Window**: Last 90 days### 6. Verify Installation

- **Data Source**: JIRA "Technical Owner" field

Check the health endpoint:

## 🔐 Security Notes

```bash

- Never commit `.env` file with credentialscurl http://localhost:8000/health

- API tokens should be rotated regularly```

- Use environment variables for all sensitive data

Expected response:

## 🐳 Docker Deployment```json

{

```bash  "status": "healthy",

# Build the Docker image  "database": "connected",

docker build -t jira-autoassign .  "developers_loaded": 6

}

# Run with docker-compose```

docker-compose up -d

```## 🔗 Jira Webhook Setup



## 📈 Performance### 1. Create Webhook in Jira



- **High Confidence Matches** (>70%): Tickets with nearly identical historical examples1. Go to Jira Settings → System → WebHooks

- **Medium Confidence** (50-70%): Clear patterns with some variation2. Click "Create a WebHook"

- **Low Confidence** (<50%): Novel issues or unclear patterns3. Configure:

   - **Name**: Auto-Assignment Service

Example Results:   - **Status**: Enabled

- NFSAAS-148591 (CVT pipeline): 75% → team-mercury   - **URL**: `http://your-server:8000/webhook`

- NFSAAS-148584 (Cool tier): 60% → team-supernova   - **Events**: Select "Issue → created"

- NFSAAS-148579 (CRR/SnapMirror): 60% → team-tunnel-snakes4. Save



## 🛠️ Troubleshooting### 2. Configure Technical Owner Field



### ChromaDB Connection Failed**Option A: Using Custom Field**

```bash

# Make sure ChromaDB is runningUpdate `app/main.py` line ~150 to use your custom field:

chroma run --host localhost --port 8000

``````python

# Replace customfield_10001 with your actual field ID

### OpenAI API Errorstechnical_owner = fields.customfield_10001 or ""

- Check OPENAI_API_KEY in .env```

- Verify access to NetApp LLM proxy

- Check JIRA_EMAIL format (used for authentication)Find your custom field ID:

```bash

### No Training Datacurl -u email@company.com:api_token \

```bash  https://your-company.atlassian.net/rest/api/3/field | jq '.[] | select(.name=="Technical Owner")'

# Re-run training script```

PYTHONPATH=$PWD venv/bin/python3 scripts/fetch_and_train_by_team.py

```**Option B: Using Labels**



## 🤝 ContributingIf you use labels like `team-OurTeamName`, the service will automatically detect it.



1. Keep the codebase clean and minimal**Option C: Using Standard Team Field**

2. Test predictions after making changes

3. Update documentation for new featuresIf using Jira's native team field:

4. Follow existing code style```python

technical_owner = fields.team.get("name", "") if hasattr(fields, "team") else ""

## 📝 License```



Internal NetApp project - not for external distribution.## 🧪 Testing



## 👥 Configured Teams### Test the Assignment Logic



1. team-siriusWithout setting up webhooks, you can test assignment:

2. team-vega

3. team-nandi```bash

4. team-himalayacurl -X POST "http://localhost:8000/test-assignment" \

5. team-mercury  -H "Content-Type: application/json" \

6. team-tunnel-snakes  -d '{

7. team-supernova    "issue_key": "TEST-123",

8. team-omega    "summary": "Fix authentication bug in login API",

9. team-meteor    "description": "Users cannot login using OAuth. Backend service returns 401 error.",

10. team-cit (not found in JIRA)    "issue_type": "Bug"

  }'

## 📞 Support```



For issues or questions, contact the development team.### Simulate a Webhook Call


```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "issue": {
      "key": "PROJ-123",
      "fields": {
        "summary": "Implement user authentication with JWT tokens",
        "description": "Need to add JWT token-based authentication to our REST API endpoints. Should support refresh tokens and role-based access control.",
        "issuetype": {
          "name": "Story"
        },
        "labels": ["backend", "security", "api"],
        "components": [
          {"name": "API"},
          {"name": "Security"}
        ],
        "customfield_10001": "OurTeamName"
      }
    }
  }'
```

### View Statistics

```bash
curl http://localhost:8000/stats
```

Response:
```json
{
  "overall": {
    "total_processed": 15,
    "successful_assignments": 12,
    "triage_needed": 2,
    "failed": 1,
    "success_rate": "80.0%"
  },
  "developers": [
    {
      "name": "Alice Johnson",
      "capacity": 10,
      "open_count": 3,
      "load_factor": "0.30",
      "total_assigned": 5
    }
  ]
}
```

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and health check |
| `/health` | GET | Detailed health status with DB check |
| `/webhook` | POST | Main webhook endpoint for Jira events |
| `/test-assignment` | POST | Test assignment without Jira webhook |
| `/stats` | GET | View assignment statistics and developer workload |

## 🔧 Customization

### Adjust Scoring Weights

Edit `.env` or modify these in `app/main.py`:

```python
SIMILARITY_WEIGHT = 0.6  # Skill match importance
RECENCY_WEIGHT = 0.2     # Fair distribution
WORKLOAD_WEIGHT = 0.2    # Capacity balancing
```

Weights must sum to 1.0.

### Change Assignment Threshold

```python
ASSIGNMENT_THRESHOLD = 0.5  # Lower = more auto-assignments
                            # Higher = more manual triage
```

### Update Developer Profiles

Developers are loaded from `dev_profiles.csv` on startup. To update:

1. Edit the CSV file
2. Restart the service, or
3. Update the database directly:

```python
from app.db import db
from app.models import Developer

with db.get_session() as session:
    dev = session.query(Developer).filter_by(name="Alice Johnson").first()
    dev.capacity = 15
    dev.history_text += " new skills and keywords"
    session.commit()
```

### Extend Recency Calculation

Edit `app/assigner.py`, method `calculate_recency_score()`:

```python
max_hours = 24 * 7  # Change decay window (currently 7 days)
```

## 🐛 Troubleshooting

### Issue: No developers loaded

**Solution**: Check that `dev_profiles.csv` exists and has valid data:
```bash
cat dev_profiles.csv
```

### Issue: Webhook not receiving events

**Solution**: 
1. Verify webhook URL is accessible from Jira
2. If local, use ngrok: `ngrok http 8000`
3. Update Jira webhook URL to ngrok URL

### Issue: Assignment fails with 404

**Solution**: Verify account IDs are correct. Test with:
```bash
curl -u email@company.com:api_token \
  https://your-company.atlassian.net/rest/api/3/user?accountId=ACCOUNT_ID_HERE
```

### Issue: All tickets go to triage

**Solution**: 
- Lower `ASSIGNMENT_THRESHOLD` in `.env`
- Add more descriptive `history_text` for developers
- Check that ticket descriptions have enough content

### Issue: Import errors

**Solution**: Ensure virtual environment is activated and dependencies installed:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 📊 Database Schema

### Developers Table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| name | String | Developer name |
| account_id | String | Jira account ID (unique) |
| capacity | Integer | Max tickets they can handle |
| open_count | Integer | Current open tickets |
| history_text | Text | Past ticket keywords for similarity |
| created_at | DateTime | Profile creation time |
| updated_at | DateTime | Last update time |

### Assignment Logs Table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| issue_key | String | Jira ticket key |
| issue_type | String | Bug, Story, Task, etc. |
| summary | String | Ticket title |
| description | Text | Ticket description |
| assigned_to | String | Developer account ID |
| assigned_to_name | String | Developer name |
| similarity_score | Float | TF-IDF similarity |
| recency_score | Float | Recency component |
| workload_score | Float | Workload component |
| final_score | Float | Combined score |
| assignment_status | String | assigned/triage_needed/failed |
| created_at | DateTime | Assignment timestamp |

## 🚀 Production Deployment

### Using Docker (recommended)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t jira-autoassign .
docker run -p 8000:8000 --env-file .env jira-autoassign
```

### Using systemd (Linux)

Create `/etc/systemd/system/jira-autoassign.service`:

```ini
[Unit]
Description=Jira Auto-Assignment Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/jira-autoassign
Environment="PATH=/opt/jira-autoassign/venv/bin"
ExecStart=/opt/jira-autoassign/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable jira-autoassign
sudo systemctl start jira-autoassign
```

### Environment Variables for Production

- Set `reload=False` in uvicorn
- Use PostgreSQL instead of SQLite for better concurrency
- Set up proper logging with rotation
- Use a reverse proxy (nginx) for SSL termination

## 🔐 Security Considerations

1. **API Token Protection**: Never commit `.env` file. Use secrets management in production.
2. **Webhook Authentication**: Add signature verification for Jira webhooks (see Jira docs).
3. **HTTPS**: Always use HTTPS in production with valid certificates.
4. **Rate Limiting**: Add rate limiting to prevent abuse.
5. **Input Validation**: All inputs are validated via Pydantic models.

## 📈 Future Enhancements

- [ ] Support for ticket updates and reassignments
- [ ] Machine learning model for better predictions
- [ ] Time-based assignment rules (timezone aware)
- [ ] Integration with Slack for notifications
- [ ] Dashboard UI for visualization
- [ ] A/B testing for different scoring algorithms
- [ ] Support for ticket priority in scoring
- [ ] Developer availability calendar integration

## 📄 License

This project is provided as-is for internal use. Modify as needed for your team.

## 🤝 Contributing

Feel free to extend this service with additional features:
1. Fork the codebase
2. Create a feature branch
3. Test thoroughly
4. Submit for review

## 📞 Support

For issues or questions:
- Check the troubleshooting section
- Review application logs: `tail -f app.log`
- Inspect the database: `sqlite3 jira_assignments.db`

---

**Built with FastAPI, SQLAlchemy, scikit-learn, and ❤️**
