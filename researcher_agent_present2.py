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
        "num": "50",
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

# def get_top_researchers(topic: str, top_k: int = 3) -> str:
#     """
#     Searches Google Scholar using SerpAPI for the given topic and returns
#     only researchers with valid Google Scholar profiles and full names.
#     """
#     print(f"[DEBUG] Searching Google Scholar for: {topic!r}")

#     serp_api_key = os.environ.get("SERPAPI_KEY")
#     if not serp_api_key:
#         return "ERROR: SERPAPI_KEY not found in environment variables."

#     params = {
#         "engine": "google_scholar",
#         "q": topic,
#         "num": "50",  # Get more results to filter better
#         "api_key": serp_api_key
#     }

#     search = GoogleSearch(params)
#     results = search.get_dict().get("organic_results", [])
#     if not results:
#         return "No results found."

#     authors_data = {}

#     for paper in results:
#         snippet = paper.get("snippet", "") or ""
#         emails_found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", snippet)

#         authors = paper.get("publication_info", {}).get("authors", [])
#         for author in authors:
#             name = author.get("name")
#             profile_link = author.get("link") or author.get("profile") or None

#             if not name:
#                 continue

#             name = name.strip()

#             # Skip if no valid Google Scholar profile
#             if not profile_link or "scholar.google.com" not in profile_link:
#                 continue

#             # Skip if name is too short or doesn't look like full name
#             if len(name) <= 2 or len(name.split()) < 2:
#                 continue

#             # Skip names that are clearly abbreviated (contain single letters with dots)
#             if re.search(r'\b[A-Z]\.', name):
#                 continue

#             # Skip names that are too short (less than 5 characters total)
#             if len(name.replace(' ', '')) < 5:
#                 continue

#             if name not in authors_data:
#                 authors_data[name] = {
#                     "count": 0,
#                     "profile": profile_link,
#                     "emails": set(),
#                     "papers_count": 0
#                 }

#             authors_data[name]["count"] += 1
#             for e in emails_found:
#                 authors_data[name]["emails"].add(e)

#             for v in author.values():
#                 if isinstance(v, str):
#                     found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v)
#                     for f in found:
#                         authors_data[name]["emails"].add(f)

#     if not authors_data:
#         return "No researchers with valid Google Scholar profiles found."

#     # Rank by frequency and filter for quality
#     ranked = []
#     for name, info in authors_data.items():
#         # Only include researchers that appear multiple times (more established)
#         if info["count"] >= 2:  # At least 2 papers in this topic
#             ranked.append((name, info))

#     if not ranked:
#         return "No established researchers found with multiple publications in this topic."

#     # Sort by frequency (number of papers)
#     ranked.sort(key=lambda kv: kv[1]["count"], reverse=True)
    
#     # Take top K
#     ranked = ranked[:top_k]

#     # -------------------------------
#     # Create final Markdown table
#     # -------------------------------
#     markdown_table = "| Rank | Name | Email | Google Scholar Profile | Papers Found |\n"
#     markdown_table += "|------|------|-------|----------------------|-------------|\n"

#     for i, (name, info) in enumerate(ranked, start=1):
#         emails_list = ", ".join(sorted(info["emails"])) if info["emails"] else "Not available"
#         profile = info["profile"]
#         papers_count = info["count"]
        
#         markdown_table += f"| {i} | **{name}** | {emails_list} | [View Profile]({profile}) | {papers_count} |\n"

#     return markdown_table

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
    Extracts the main research topic from an uploaded paper using Gemini.
    """
    paper_text = extract_text_from_pdf(file_path)
    if not paper_text:
        return "No readable text found in the uploaded paper."

    # Use first 3000 characters for analysis
    text_sample = paper_text[:3000]

    prompt = f"""
Analyze this research paper text and extract ONLY the main research topic.
Return just the topic as a short phrase (2-5 words maximum).

Paper text:
{text_sample}

Return ONLY the topic phrase, nothing else.
"""

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_api_key:
        return "Error: GEMINI_API_KEY missing."

    try:
        analysis_agent = Agent(
            model=Gemini(id="gemini-2.5-flash", api_key=gemini_api_key),
            description="Extract main research topic from paper text",
            markdown=False
        )
        
        response = analysis_agent.run(prompt)
        main_topic = response.content.strip()
        
        # Clean the response
        main_topic = re.sub(r'["\']', '', main_topic)  # Remove quotes
        main_topic = main_topic.split('\n')[0]  # Take only first line
        main_topic = main_topic.strip()
        
        if main_topic and len(main_topic) > 3 and len(main_topic.split()) <= 5:
            return f"**Main Research Topic:** {main_topic}"
        else:
            return "Could not extract a clear topic from the paper."
            
    except Exception as e:
        return f"Error analyzing paper: {str(e)}"



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
