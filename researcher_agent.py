import os
import re
import getpass
from collections import Counter
from serpapi import GoogleSearch
import yagmail
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv

# Load environment variables from .env (for local testing)
load_dotenv()

# ---------------------------------------------------
# TOOL 1: Fetch Top Researchers from Google Scholar
# ---------------------------------------------------
def get_top_researchers(topic: str, top_k: int = 3) -> str:
    print(f"[DEBUG] Searching Google Scholar for: {topic!r}")

    serp_api_key = os.environ.get("SERPAPI_KEY")
    if not serp_api_key:
        return "ERROR: SERPAPI_KEY not found in environment variables."

    params = {
        "engine": "google_scholar",
        "q": topic,
        "num": "30",
        "api_key": serp_api_key
    }

    search = GoogleSearch(params)
    results = search.get_dict().get("organic_results", [])
    if not results:
        return "No results found."

    authors_data = {}

    for paper in results:
        snippet = paper.get("snippet", "") or ""
        emails_found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", snippet)

        authors = paper.get("publication_info", {}).get("authors", [])
        for author in authors:
            name = author.get("name")
            profile_link = author.get("link") or author.get("profile") or None

            if not name:
                continue

            name = name.strip()

            if name not in authors_data:
                authors_data[name] = {
                    "count": 0,
                    "profile": profile_link or "(profile not available)",
                    "emails": set()
                }

            authors_data[name]["count"] += 1
            for e in emails_found:
                authors_data[name]["emails"].add(e)

            for v in author.values():
                if isinstance(v, str):
                    found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v)
                    for f in found:
                        authors_data[name]["emails"].add(f)

    if not authors_data:
        return "No authors found."

    ranked = sorted(authors_data.items(), key=lambda kv: kv[1]["count"], reverse=True)[:top_k]

    markdown_table = "| Rank | Full Name | Emails (found) | Profile Link |\n"
    markdown_table += "|------|-----------|----------------|--------------|\n"

    for i, (name, info) in enumerate(ranked, start=1):
        emails_list = ", ".join(sorted(info["emails"])) if info["emails"] else "(not found)"
        profile = info["profile"]
        markdown_table += f"| {i} | {name} | {emails_list} | {profile} |\n"

    return markdown_table


# ---------------------------------------------------
# TOOL 2: Send Email (with dynamic receiver list)
# ---------------------------------------------------
def send_mail(ans: str, subject: str = "Top Researchers - Auto Update", receivers: list[str] = None) -> str:
    app_pass = os.environ.get("MAIL_APP_PASS")
    if not app_pass:
        app_pass = getpass.getpass("Enter Gmail App Password (won't echo): ")

    sender = "rana.sayak.2001@gmail.com"

    # Allow dynamic receivers from frontend
    if not receivers:
        receivers = [
            "sayakrana108@gmail.com",
            "sayak.rana2001@gmail.com",
            "rana.sayak.2001@gmail.com"
        ]

    yag = yagmail.SMTP(sender, app_pass)

    for r in receivers:
        body = f"""
Hi,

This is an automated message from the Research Connect app.
Below are the top researchers found for your requested topic:

{ans}

Best regards,
Sayak Rana
"""
        yag.send(to=r, subject=subject, contents=body)
        print(f"[MAIL SENT] → {r}")

    return f"Emails sent successfully to: {', '.join(receivers)}"


# ---------------------------------------------------
# AGENTS
# ---------------------------------------------------
agent1 = Agent(
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    description="Extract top researchers (name, email, profile) for a topic using Google Scholar.",
    tools=[get_top_researchers],
    instructions=[
        "Always use get_top_researchers(topic, top_k) to find top researchers and return a Markdown table."
    ],
    markdown=True
)

agent2 = Agent(
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    description="Send research results via email. Tool: send_mail(ans).",
    tools=[send_mail],
    instructions=[
        "Use send_mail(ans=<string>, subject=<optional>, receivers=<list>) to send the provided content to the given email list.",
        "Do not attempt to regenerate the research results — just send the provided content."
    ],
    markdown=False
)


# ---------------------------------------------------
# WRAPPER FUNCTIONS (used in Streamlit frontend)
# ---------------------------------------------------
def run_agent1(query: str):
    """Call the first agent to get researcher details."""
    response = agent1.run(query)
    return response.content


def run_agent2(query: str):
    """Call the second agent to send email."""
    response = agent2.run(query)
    return response.content
