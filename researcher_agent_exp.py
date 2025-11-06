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


import requests
import re
from bs4 import BeautifulSoup
from agno.agent import Agent
from agno.models.google import Gemini
from agno.tool import Tool

class ResearcherSearchTool(Tool):
    name: str = "search_researchers"
    description: str = "Search for top academic researchers in a specific field"
    
    def invoke(self, agent: Agent, topic: str, top_k: int = 3) -> str:
        """
        Find top researchers using DuckDuckGo search
        
        Args:
            topic: Research field or topic
            top_k: Number of top researchers to return (default: 3)
        """
        # Use DuckDuckGo's HTML interface
        url = "https://html.duckduckgo.com/html/"
        params = {
            'q': f'{topic} "Google Scholar"',
            'kl': 'us-en'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.post(url, data=params, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            researchers = []
            
            # Find all search results
            results = soup.find_all('div', class_='result')
            
            for result in results[:10]:
                title_elem = result.find('a', class_='result__a')
                if title_elem:
                    title = title_elem.get_text()
                    link = title_elem.get('href')
                    
                    # Extract name from title
                    name = self.extract_name_from_title(title)
                    
                    if name and name != "Unknown":
                        snippet_elem = result.find('a', class_='result__snippet')
                        snippet = snippet_elem.get_text() if snippet_elem else ""
                        
                        # Extract email if available
                        email = self.extract_email(snippet)
                        
                        researchers.append({
                            'name': name,
                            'email': email,
                            'profile_url': link,
                            'info': snippet
                        })
            
            if not researchers:
                return f"No researchers found for '{topic}'."
            
            # Remove duplicates and get top K
            unique_researchers = []
            seen_names = set()
            for researcher in researchers:
                if researcher['name'] not in seen_names:
                    unique_researchers.append(researcher)
                    seen_names.add(researcher['name'])
            
            researchers_to_display = unique_researchers[:top_k]
            
            return self.create_researcher_table(researchers_to_display, topic)
            
        except Exception as e:
            return f"Search error: {str(e)}"

    def extract_name_from_title(self, title: str) -> str:
        """Extract researcher name from search result title."""
        clean_title = re.sub(r' - Google Scholar| \| Google Scholar', '', title)
        name_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})', clean_title)
        if name_match:
            name = name_match.group(1).strip()
            if name and len(name) > 4:
                return name
        return "Unknown"

    def extract_email(self, text: str) -> str:
        """Extract email address from text if available."""
        email_match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
        return email_match.group(0) if email_match else "Not available"

    def create_researcher_table(self, researchers, topic):
        """Create a clean markdown table."""
        markdown_table = f"## Top Researchers in {topic}\n\n"
        markdown_table += "| Name | Email | Profile Link | Information |\n"
        markdown_table += "|------|-------|-------------|-------------|\n"
        
        for researcher in researchers:
            name = researcher['name']
            email = researcher['email']
            profile_url = researcher['profile_url']
            info = researcher['info'][:100] + "..." if len(researcher['info']) > 100 else researcher['info']
            
            markdown_table += f"| {name} | {email} | [View Profile]({profile_url}) | {info} |\n"
        
        return markdown_table

# Create the Agno agent
researcher_agent = Agent(
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    name="ResearcherFinder",
    description="Find top academic researchers in specific fields",
    tools=[ResearcherSearchTool()],
    instructions=[
        "Find top 3 researchers for any given topic.",
        "Return a clean table with: Name, Email, Profile Link, and Information.",
        "Always return exactly 3 researchers unless specified otherwise.",
        "Keep the output professional and concise."
    ],
    markdown=True
)

# ---------------------------------------------------
# AGENTS (Gemini + SerpAPI + Email)
# ---------------------------------------------------
# agent1 = Agent(
#     model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
#     description="Extract top researchers (name, email, profile) for a topic using Google Scholar.",
#     tools=[get_top_researchers],
#     instructions=[
#         "Always use get_top_researchers(topic, top_k) to find top researchers and return a Markdown table."
#     ],
#     markdown=True
# )
# Update your agent1 to use the new function
# agent1 = Agent(
#     model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
#     description="Find top researchers using web search with accurate names and profiles.",
#     tools=[get_top_researchers_gemini],  # Use the new function
#     instructions=[
#         "Use get_top_researchers_gemini(topic, top_k) to find top researchers with accurate full names and profiles.",
#         "Always return a clean Markdown table with names, affiliations, emails, and scholar profiles."
#     ],
#     markdown=True
# )

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
    SIMPLE AND RELIABLE version for paper analysis.
    """
    paper_text = extract_text_from_pdf(file_path)
    if not paper_text:
        return "No readable text found in the uploaded paper."

    # Use first 5000 characters for analysis
    text_sample = paper_text[:5000]

    prompt = f"""
Based on this research paper text, what is the main research topic? 
Return just the topic name as a short phrase (2-5 words).

Paper excerpt:
{text_sample}

Answer with only the topic, no explanations.
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
        
        print(f"[DEBUG] Extracted topic: {main_topic}")
        
        if main_topic and len(main_topic) > 3:
            return f"**Main Research Topic:** {main_topic}\n\n**Keywords:** (Use topic for search)"
        else:
            return "Could not extract a clear topic from the paper."
            
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        return f"Error analyzing paper: {str(e)}"

# ---------------------------------------------------
# WRAPPER FUNCTIONS (used in Streamlit frontend)
# ---------------------------------------------------
# def run_agent1(query: str):
#     """Call the first agent to get researcher details."""
#     response = agent1.run(query)
#     return response.content

def run_agent1(query: str) -> str:
    """Run the researcher agent"""
    try:
        response = researcher_agent.run(query)
        return response.content
    except Exception as e:
        return f"Error: {str(e)}"

def run_agent2(query: str):
    """Call the second agent to send email."""
    response = agent2.run(query)
    return response.content


def run_agent3(file_path: str):
    """Analyze a research paper and return topic summary."""
    return analyze_paper(file_path)
