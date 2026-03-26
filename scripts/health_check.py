#!/usr/bin/env python3
"""
Runtime health check for Jira auto-assignment stack.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.jira_client import JiraClient
from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient


async def main() -> int:
    print("== Jira Auto-Assign Health Check ==")
    checks = []

    required_env = ["JIRA_BASE_URL", "JIRA_API_TOKEN", "NETAPP_LLM_API_KEY"]
    missing = [name for name in required_env if not os.getenv(name)]
    if missing:
        checks.append(("env", False, f"missing: {', '.join(missing)}"))
    else:
        checks.append(("env", True, "required variables present"))

    jira = JiraClient()
    jira_ok = False
    jira_msg = "query failed"
    try:
        result = await jira.search_issues("project = NFSAAS ORDER BY created DESC", max_results=1, fields=["key"])
        jira_ok = "issues" in result
        jira_msg = f"reachable, returned {len(result.get('issues', []))} issue(s)"
    except Exception as exc:
        jira_msg = str(exc)
    checks.append(("jira", jira_ok, jira_msg))

    chroma_ok = False
    chroma_msg = "connection failed"
    llm_ok = False
    llm_msg = "embedding probe failed"
    try:
        client = EnhancedTicketEmbeddingClient()
        chroma_count = client.tickets_collection.count()
        chroma_ok = True
        chroma_msg = f"connected, tickets_collection_count={chroma_count}"
        embedding = await client.generate_embedding("health check embedding probe")
        llm_ok = isinstance(embedding, list) and len(embedding) > 0
        llm_msg = f"embedding dimension={len(embedding)}"
    except Exception as exc:
        if not chroma_ok:
            chroma_msg = str(exc)
        else:
            llm_msg = str(exc)

    checks.append(("chroma", chroma_ok, chroma_msg))
    checks.append(("llm", llm_ok, llm_msg))

    has_failure = False
    for name, ok, msg in checks:
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")
        has_failure = has_failure or (not ok)

    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
