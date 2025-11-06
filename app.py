import streamlit as st
from researcher_agent import run_agent1, run_agent2
import re

st.set_page_config(page_title="Research Connect", page_icon="🔬", layout="centered")

st.title("🔍 Research Connect — Find & Mail Researchers")

st.markdown("""
This app uses **Gemini + SERPAPI** to find top researchers on Google Scholar,  
and allows you to **customize and send the results** to your chosen email addresses.
""")

# -----------------------------
# 1️⃣ Get Research Topic
# -----------------------------
topic = st.text_input("Enter a Research Topic (e.g. Graph Neural Networks):")

if st.button("🔎 Find Top Researchers"):
    if not topic.strip():
        st.warning("Please enter a topic before searching.")
    else:
        with st.spinner("Running Gemini agent to fetch researchers..."):
            try:
                result = run_agent1(f"Find top 3 researchers in {topic} and return names, emails, and profile links.")
                st.session_state["agent_result"] = result
                st.success("Fetched top researchers successfully!")
                st.markdown(result)
            except Exception as e:
                st.error(f"Error fetching researchers: {e}")

# -----------------------------
# 2️⃣ Send Email Section
# -----------------------------
if "agent_result" in st.session_state:
    st.markdown("---")
    st.subheader("✉️ Send Customized Email")

    # Subject input
    subject = st.text_input("Email Subject", f"Top 3 Researchers in {topic}")

    # Receiver emails
    receiver_input = st.text_area(
        "Enter Receiver Email IDs (comma-separated):",
        placeholder="e.g. alice@gmail.com, bob@iitk.ac.in"
    )

    # Email body (customizable)
    default_body = f"""Hi,

Below are the top researchers found for your requested topic "{topic}":

{st.session_state["agent_result"]}

Best regards,
Sayak Rana
"""
    email_body = st.text_area("Customize Email Body", default_body, height=300)

    # Send button
    if st.button("🚀 Send Email"):
        if not receiver_input.strip():
            st.error("Please enter at least one receiver email address.")
        else:
            receivers = [e.strip() for e in re.split(r"[,\s]+", receiver_input) if e.strip()]
            ans = email_body  # use customized email body

            with st.spinner("Sending email via Gemini agent..."):
                try:
                    # Pass everything (including custom message)
                    res = run_agent2(
                        f"send_mail(ans={ans!r}, subject={subject!r}, receivers={receivers!r})"
                    )
                    st.success("✅ Emails sent successfully!")
                    st.text(res)
                except Exception as e:
                    st.error(f"Error sending email: {e}")
