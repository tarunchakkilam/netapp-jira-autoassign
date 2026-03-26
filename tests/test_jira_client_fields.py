import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.jira_client import JiraClient


def test_fetch_ticket_field_aliases_from_custom_ids(monkeypatch):
    monkeypatch.setenv("TECHNICAL_OWNER_FIELD", "customfield_15906")
    monkeypatch.setenv("TECHNICAL_OWNER_FALLBACK_FIELD", "customfield_10050")
    monkeypatch.setenv("HYPERSCALER_FIELD", "customfield_16202")

    client = JiraClient(base_url="https://jira.example.com", email="a@b.com", api_token="token")
    payload = {
        "fields": {
            "summary": "sample",
            "description": "desc",
            "project": {"key": "NFSAAS"},
            "issuetype": {"name": "Bug"},
            "customfield_10050": {"value": "Team Nandi"},
            "customfield_16202": [{"value": "Azure"}],
        }
    }

    fields = payload["fields"]
    technical_owner = fields.get(client.technical_owner_field) or fields.get(client.technical_owner_fallback_field)
    hyperscaler = fields.get(client.hyperscaler_field)

    assert technical_owner == {"value": "Team Nandi"}
    assert hyperscaler == [{"value": "Azure"}]


def test_owner_prefers_primary_field(monkeypatch):
    monkeypatch.setenv("TECHNICAL_OWNER_FIELD", "customfield_primary")
    monkeypatch.setenv("TECHNICAL_OWNER_FALLBACK_FIELD", "customfield_fallback")

    client = JiraClient(base_url="https://jira.example.com", email="a@b.com", api_token="token")
    fields = {
        "customfield_primary": {"value": "Team Primary"},
        "customfield_fallback": {"value": "Team Fallback"},
    }
    technical_owner = fields.get(client.technical_owner_field) or fields.get(client.technical_owner_fallback_field)
    assert technical_owner == {"value": "Team Primary"}
