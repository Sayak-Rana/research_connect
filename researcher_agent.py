import os
import re
import json
import getpass
import fitz  # PyMuPDF for PDF reading
import requests
from bs4 import BeautifulSoup
from collections import Counter
import yagmail
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv
from textwrap import dedent

# Load environment variables from .env
load_dotenv()

# ---------------------------------------------------
# DUCKDUCKGO SEARCH TOOL
# ---------------------------------------------------
def search_duckduckgo(query: str, max_results: int = 10) -> list:
    """
    Search DuckDuckGo and return results.
    """
    url = "https://html.duckduckgo.com/html/"
    params = {
        'q': query,
        'kl': 'us-en'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.post(url, data=params, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        search_results = soup.find_all('div', class_='result')
        
        for result in search_results[:max_results]:
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')
            
            if title_elem:
                title = title_elem.get_text()
                link = title_elem.get('href')
                snippet = snippet_elem.get_text() if snippet_elem else ""
                
                results.append({
                    'title': title,
                    'link': link,
                    'snippet': snippet
                })
        
        return results
    except Exception as e:
        print(f"[DEBUG] DuckDuckGo search error: {e}")
        return []

# ---------------------------------------------------
# SCIENTIST FINDER AGENT (Your Friend's Approach)
# ---------------------------------------------------
scientist_finder_agent = Agent(
    name="Scientist Name Finder",
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    tools=[search_duckduckgo],
    instructions=dedent("""\
        You find the names of top scientists in a given research field.

        IMPORTANT: Do not list the authors of the paper as the top scientist.
                        
        For any research field provided, search and identify the 3 most influential scientists/researchers.
        Focus on:
        - Foundational contributors
        - Highly cited researchers
        - Award winners in the field
        - Pioneers in the field

        Use the search tool to find information about top researchers in the field.

        Output ONLY a simple numbered list with just the names:
        1. Full Name One
        2. Full Name Two  
        3. Full Name Three

        Do NOT add any other text, explanations, or details.
    """),
    markdown=False,
)

# ---------------------------------------------------
# ENHANCED RESEARCHER FINDER WITH PROFILES
# ---------------------------------------------------
def get_top_researchers(topic: str, top_k: int = 3) -> str:
    """
    Enhanced version that finds top researchers with their Google Scholar profiles.
    """
    print(f"[DEBUG] Finding top researchers for: {topic}")
    
    # First, get the top scientist names using the agent
    try:
        response = scientist_finder_agent.run(f"Find top {top_k} researchers in {topic}")
        names_text = response.content.strip()
        
        # Parse the numbered list
        names = []
        for line in names_text.split('\n'):
            match = re.search(r'^\d+\.\s*(.+)', line.strip())
            if match:
                names.append(match.group(1).strip())
        
        if not names:
            return "No researcher names found. Please try a different topic."
            
        print(f"[DEBUG] Found names: {names}")
        
        # Now get Google Scholar profiles for each name
        researchers_with_profiles = []
        
        for name in names[:top_k]:
            profile = find_google_scholar_profile(name)
            researchers_with_profiles.append({
                'name': name,
                'profile': profile
            })
        
        # Create the final table
        return create_researcher_table(researchers_with_profiles, topic)
        
    except Exception as e:
        return f"Error finding researchers: {str(e)}"

def find_google_scholar_profile(researcher_name: str) -> str:
    """
    Find Google Scholar profile for a researcher.
    """
    serp_api_key = os.environ.get("SERPAPI_KEY")
    
    if serp_api_key:
        # Use SerpAPI for accurate profile finding
        try:
            params = {
                "engine": "google_scholar_profiles",
                "mauthors": researcher_name,
                "api_key": serp_api_key
            }
            search = GoogleSearch(params)
            results = search.get_dict().get("profiles", [])
            
            if results:
                return results[0].get("link", "Profile not found")
        except Exception as e:
            print(f"[DEBUG] SerpAPI profile search failed: {e}")
    
    # Fallback: Search DuckDuckGo for scholar profile
    try:
        results = search_duckduckgo(f"{researcher_name} Google Scholar", max_results=5)
        for result in results:
            if 'scholar.google.com' in result['link']:
                return result['link']
    except Exception as e:
        print(f"[DEBUG] DuckDuckGo profile search failed: {e}")
    
    return "Profile not found"

def create_researcher_table(researchers: list, topic: str) -> str:
    """
    Create a clean markdown table of researchers.
    """
    markdown_table = f"## Top {len(researchers)} Researchers in {topic}\n\n"
    markdown_table += "| Rank | Researcher | Google Scholar Profile |\n"
    markdown_table += "|------|------------|----------------------|\n"
    
    for i, researcher in enumerate(researchers, 1):
        name = researcher['name']
        profile = researcher['profile']
        
        if profile != "Profile not found":
            markdown_table += f"| {i} | **{name}** | [View Profile]({profile}) |\n"
        else:
            markdown_table += f"| {i} | **{name}** | Profile not found |\n"
    
    return markdown_table

# ---------------------------------------------------
# TOOL 2: Send Email (Keep your existing)
# ---------------------------------------------------
def send_mail(ans: str, subject: str = "Top Researchers - Auto Update", receivers: list[str] = None) -> str:
    """
    Sends an email to the given receivers.
    """
    app_pass = os.environ.get("MAIL_APP_PASS")
    if not app_pass:
        app_pass = getpass.getpass("Enter Gmail App Password (won't echo): ")

    sender = "rana.sayak.2001@gmail.com"

    if not receivers:
        receivers = ["rana.sayak.2001@gmail.com"]

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
# TOOL 3: Analyze Uploaded Research Paper (Keep your existing)
# ---------------------------------------------------
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
        main_topic = re.sub(r'["\']', '', main_topic)
        main_topic = main_topic.split('\n')[0]
        main_topic = main_topic.strip()
        
        if main_topic and len(main_topic) > 3 and len(main_topic.split()) <= 5:
            return f"**Main Research Topic:** {main_topic}"
        else:
            return "Could not extract a clear topic from the paper."
            
    except Exception as e:
        return f"Error analyzing paper: {str(e)}"

# ---------------------------------------------------
# AGENTS
# ---------------------------------------------------
agent1 = Agent(
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    description="Find top researchers in any field with their Google Scholar profiles.",
    tools=[get_top_researchers],
    instructions=[
        "Use get_top_researchers(topic, top_k) to find top influential researchers.",
        "Return a clean table with names and Google Scholar profiles."
    ],
    markdown=True
)

agent2 = Agent(
    model=Gemini(id="gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY", "")),
    description="Send research results via email.",
    tools=[send_mail],
    instructions=[
        "Use send_mail(ans=<string>, subject=<optional>, receivers=<list>) to send emails.",
        "Do not attempt to regenerate the research results."
    ],
    markdown=False
)

# ---------------------------------------------------
# WRAPPER FUNCTIONS for Streamlit
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
