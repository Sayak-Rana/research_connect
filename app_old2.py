import streamlit as st
from researcher_agent import run_agent1, run_agent2, run_agent3
import re
import tempfile
import os

st.set_page_config(page_title="Research Connect", page_icon="🔬", layout="centered")

st.title("Research Connect — Find & Mail Researchers")

st.markdown("""
This app uses **Gemini + SERPAPI** to:
1. Find top researchers on Google Scholar  
2. Analyze uploaded research papers to discover their main topic  
3. Send customized emails with the results
""")

# -----------------------------
# OPTION 1: Manual Topic Input
# -----------------------------
st.header("Option 1: Search by Topic")
topic = st.text_input("Enter a Research Topic (e.g. Graph Neural Networks):")

if st.button("Find Top Researchers"):
    if not topic.strip():
        st.warning("Please enter a topic before searching.")
    else:
        with st.spinner("Running Gemini agent to fetch researchers..."):
            try:
                result = run_agent1(f"Find top 3 researchers in {topic} and return names, emails, and profile links.")
                st.session_state["agent_result"] = result
                st.session_state["topic"] = topic
                st.success("Fetched top researchers successfully!")
                st.markdown(result)
            except Exception as e:
                st.error(f"Error fetching researchers: {e}")

# -----------------------------
# OPTION 2: Upload Research Paper
# -----------------------------
st.markdown("---")
st.header("Option 2: Upload a Research Paper (PDF)")

uploaded_file = st.file_uploader("Upload a research paper (PDF only):", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    with st.spinner("Analyzing paper to identify topic..."):
        try:
            topic_summary = run_agent3(tmp_path)
            st.subheader("Paper Analysis Result:")
            st.markdown(topic_summary)

            # Extract main topic cleanly from the markdown returned by agent3
            match = re.search(r"\*\*Main Research Topic:\*\*\s*(.*)", topic_summary)
            if match:
                extracted_topic = match.group(1).strip()
            else:
                extracted_topic = "Unknown Topic"

            st.session_state["topic"] = extracted_topic
            st.info(f"Detected Topic: **{extracted_topic}**")

            # Automatically fetch top researchers for that topic
            if extracted_topic != "Unknown Topic":
                with st.spinner(f"Finding top researchers related to '{extracted_topic}'..."):
                    result = run_agent1(f"Find top 3 researchers in {extracted_topic} and return names, emails, and profile links.")
                    st.session_state["agent_result"] = result
                    st.success("Fetched top researchers successfully!")
                    st.markdown(result)
            else:
                st.warning("Couldn't clearly detect a topic from the paper.")
        except Exception as e:
            st.error(f"Error analyzing paper: {e}")

# -----------------------------
# EMAIL SECTION
# -----------------------------
if "agent_result" in st.session_state:
    st.markdown("---")
    st.subheader("✉️ Send Customized Email")

    subject = st.text_input("Email Subject", f"Top 3 Researchers in {st.session_state.get('topic', 'this field')}")
    receiver_input = st.text_area("Enter Receiver Email IDs (comma-separated):", placeholder="e.g. alice@gmail.com, bob@iitk.ac.in")

    default_body = f"""Hi,

Below are the top researchers found for your requested topic "{st.session_state.get('topic', 'your field')}":

{st.session_state["agent_result"]}

Best regards,
Sayak Rana
"""
    email_body = st.text_area("Customize Email Body", default_body, height=300)

    if st.button("Send Email"):
        if not receiver_input.strip():
            st.error("Please enter at least one receiver email address.")
        else:
            receivers = [e.strip() for e in re.split(r"[,\s]+", receiver_input) if e.strip()]
            ans = email_body

            with st.spinner("Sending email via Gemini agent..."):
                try:
                    res = run_agent2(f"send_mail(ans={ans!r}, subject={subject!r}, receivers={receivers!r})")
                    st.success("Emails sent successfully!")
                    st.text(res)
                except Exception as e:
                    st.error(f"Error sending email: {e}")
