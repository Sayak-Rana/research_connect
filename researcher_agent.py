import os
import re
import json
import getpass
import fitz  # PyMuPDF for PDF reading
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
    """
    Searches Google Scholar using SerpAPI for the given topic and returns
    a Markdown table of the top researchers with full names and profile links.
    """
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

            # Skip overly short names
            if len(name) <= 2:
                continue

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

    # Rank by frequency
    ranked = sorted(authors_data.items(), key=lambda kv: kv[1]["count"], reverse=True)[:top_k]

    # -------------------------------
    # REMOVED UNRELIABLE NAME EXPANSION
    # We'll use the names as returned by Google Scholar
    # -------------------------------

    # -------------------------------
    # Create final Markdown table
    # -------------------------------
    markdown_table = "| Rank | Name | Emails (found) | Profile Link |\n"
    markdown_table += "|------|------|----------------|--------------|\n"

    for i, (name, info) in enumerate(ranked, start=1):
        emails_list = ", ".join(sorted(info["emails"])) if info["emails"] else "(not found)"
        profile = info["profile"]
        markdown_table += f"| {i} | {name} | {emails_list} | {profile} |\n"

    return markdown_table


# ---------------------------------------------------
# TOOL 2: Send Email (with dynamic receiver list)
# ---------------------------------------------------
def send_mail(ans: str, subject: str = "Top Researchers - Auto Update", receivers: list[str] = None) -> str:
    """
    Sends an email to the given receivers.

    Parameters:
    - ans: str → The full email body text (customized by user or default)
    - subject: str → The email subject
    - receivers: list[str] → List of recipient email addresses
    """
    app_pass = os.environ.get("MAIL_APP_PASS")
    if not app_pass:
        app_pass = getpass.getpass("Enter Gmail App Password (won't echo): ")

    sender = "rana.sayak.2001@gmail.com"

    if not receivers:
        receivers = [
            "sayakrana108@gmail.com",
            "sayak.rana2001@gmail.com",
            "rana.sayak.2001@gmail.com"
        ]

    # If user left body empty, fall back to default message
    if not ans or ans.strip() == "":
        ans = """
Hi,

This is an automated message from the Research Connect app.

We found the top researchers for your requested topic.
Please find their details in the attached summary.

Best regards,
Sayak Rana
"""

    yag = yagmail.SMTP(sender, app_pass)

    for r in receivers:
        yag.send(to=r, subject=subject, contents=ans)
        print(f"[MAIL SENT] → {r}")

    return f"Emails sent successfully to: {', '.join(receivers)}"


# ---------------------------------------------------
# AGENTS (Gemini + SerpAPI + Email)
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

# # ---------------------------------------------------
# # TOOL 3: Analyze Uploaded Research Paper → Extract Topic + Keywords
# # ---------------------------------------------------
# def extract_text_from_pdf(file_path: str) -> str:
#     """Extracts and returns all text from a PDF file."""
#     text = ""
#     with fitz.open(file_path) as pdf:
#         for page in pdf:
#             text += page.get_text()
#     return text.strip()


# def analyze_paper(file_path: str) -> str:
#     """
#     Extracts the main research topic or keywords from an uploaded paper using Gemini (JSON format).
#     """
#     paper_text = extract_text_from_pdf(file_path)
#     if not paper_text:
#         return "No readable text found in the uploaded paper."

#     print("[DEBUG] Sending paper text to Gemini for analysis...")

#     # Use more text for better analysis (increased from 2000 to 4000 characters)
#     text_sample = paper_text[:4000] if len(paper_text) > 4000 else paper_text

#     prompt = f"""
# You are a research assistant. Analyze the following research paper text.

# Your task:
# - Identify the **main research topic** (1 short phrase, no explanation)
# - Identify 3–5 **keywords**

# Return the result ONLY in **JSON format**:
# {{
#   "topic": "Main topic name",
#   "keywords": ["keyword1", "keyword2", "keyword3"]
# }}

# Paper text (truncated):
# {text_sample}

# IMPORTANT: Return ONLY valid JSON, no other text.
# """

#     gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
#     if not gemini_api_key:
#         return "Error: GEMINI_API_KEY missing."

#     analysis_agent = Agent(
#         model=Gemini(id="gemini-2.5-flash", api_key=gemini_api_key),
#         description="Analyze uploaded paper text and identify its main research topic and keywords.",
#         markdown=False
#     )

#     try:
#         response = analysis_agent.run(prompt)
#         topic_summary = response.content.strip()
        
#         # Clean the response to extract JSON
#         if topic_summary.startswith("```json"):
#             topic_summary = topic_summary[7:]
#         if topic_summary.endswith("```"):
#             topic_summary = topic_summary[:-3]
        
#         # Parse JSON output safely
#         result_json = json.loads(topic_summary)
#         main_topic = result_json.get("topic", "").strip()
#         keywords = result_json.get("keywords", [])
        
#         if not main_topic:
#             return "Could not extract a clear topic from the paper."

#         keywords_text = ", ".join(keywords) if keywords else "Not found"
#         return f"**Main Research Topic:** {main_topic}\n\n**Keywords:** {keywords_text}"
        
#     except json.JSONDecodeError as e:
#         print(f"[ERROR] Failed to parse JSON from Gemini: {e}")
#         print(f"[DEBUG] Raw response: {topic_summary}")
#         return "Could not extract a clear topic from the paper. The analysis failed to return proper format."
#     except Exception as e:
#         print(f"[ERROR] Analysis failed: {e}")
#         return f"Error analyzing paper: {str(e)}"

import fitz  # PyMuPDF for PDF reading

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts and returns all text from a PDF file."""
    text = ""
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text.strip()

def analyze_paper(file_path: str) -> str:
    """
    Advanced version: Analyzes the uploaded research paper, identifies its main topic,
    and finds top researchers associated with that domain.
    """
    paper_text = extract_text_from_pdf(file_path)
    if not paper_text:
        return "No readable text found in the uploaded paper."

    # Clean text: remove noise, LaTeX junk
    clean_text = re.sub(r"\s+", " ", paper_text)
    clean_text = re.sub(r"[^a-zA-Z0-9\s.,;:!?-]", " ", clean_text)
    clean_text = clean_text.strip()

    # Extract candidate title (first few lines are often the title)
    lines = clean_text.split("\n")
    candidate_title = " ".join(lines[:3]).strip()[:200]

    print(f"[DEBUG] Extracted possible title: {candidate_title}")

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_api_key:
        return "Error: GEMINI_API_KEY missing."

    # Step 1: Ask Gemini to infer the research domain and top researchers
    prompt = f"""
You are a research analysis expert.

Given the following research paper content (title + abstract/introduction),
1. Identify the **main field of study** (concise, e.g. "Transformer Neural Networks", "Computer Vision").
2. List **3–5 most influential researchers** currently known for work in this field (well-known names).
3. Return results ONLY in JSON format:
{{
  "field": "Main field of study",
  "researchers": [
    {{"name": "Researcher Full Name", "affiliation": "Known organization or lab"}}
  ]
}}

Paper content (truncated):
Title: {candidate_title}

Text excerpt:
{clean_text[:4000]}
"""

    analysis_agent = Agent(
        model=Gemini(id="gemini-2.5-flash", api_key=gemini_api_key),
        description="Analyze research paper text to find related domain and top researchers.",
        markdown=False
    )

    response = analysis_agent.run(prompt)
    summary_text = response.content.strip()

    # Parse Gemini JSON response
    try:
        result_json = json.loads(summary_text)
        field = result_json.get("field", "").strip()
        researcher_list = result_json.get("researchers", [])
    except json.JSONDecodeError:
        print("[WARN] Gemini failed to return JSON; fallback to plain summary.")
        return summary_text

    if not researcher_list:
        return f"Could not identify researchers from this paper.\n\n**Field:** {field or 'Unknown'}"

    # Step 2: Validate with Google Scholar (SERPAPI)
    serp_api_key = os.environ.get("SERPAPI_KEY")
    if not serp_api_key:
        return "Error: SERPAPI_KEY missing."

    markdown_table = "| Rank | Researcher | Affiliation | Profile Link |\n"
    markdown_table += "|------|-------------|-------------|---------------|\n"

    for i, r in enumerate(researcher_list[:3], start=1):
        name = r.get("name", "")
        affiliation = r.get("affiliation", "")

        params = {
            "engine": "google_scholar_profiles",
            "mauthors": name,
            "api_key": serp_api_key
        }

        search = GoogleSearch(params)
        results = search.get_dict().get("profiles", [])
        if results:
            profile_link = results[0].get("link", "(not found)")
        else:
            profile_link = "(not found)"

        markdown_table += f"| {i} | {name} | {affiliation or '(not found)'} | {profile_link} |\n"

    return f"**Main Field:** {field}\n\n{markdown_table}"


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


def run_agent3(file_path: str):
    """Analyze a research paper and return topic summary."""
    return analyze_paper(file_path)
