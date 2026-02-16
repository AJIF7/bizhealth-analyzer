import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import time

st.set_page_config(page_title="BizHealth Pro", page_icon="🩺", layout="wide")

st.title("🩺 BizHealth Pro – Global Location-Aware Diagnostic System")
st.caption("Google Form → Auto scoring → Grok AI with location-specific recommendations")

# ====================== SECRETS & CONNECTIONS ======================
client = None
if "XAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["XAI_API_KEY"], base_url="https://api.x.ai/v1")
else:
    st.sidebar.header("🔑 API Keys")
    xai_key = st.sidebar.text_input("Grok (xAI) API Key", type="password", value="")
    if xai_key:
        client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")

conn = st.connection("gsheets", type=GSheetsConnection)

# ====================== LOAD GOOGLE SHEET ======================
sheet_url = st.sidebar.text_input("Google Sheet URL", 
    value="https://docs.google.com/spreadsheets/d/1z9JpEypqWFVdatk_Wc-XyTGOEUv1gL7b9t9OmlI1fb4/edit?resourcekey=&gid=1431651545#gid=1431651545")  # ← CHANGE THIS (your real sheet URL)

if sheet_url:
    try:
        df = conn.read(spreadsheet=sheet_url, ttl=5)
        st.success(f"✅ Loaded {len(df)} responses")
    except:
        st.error("Could not connect to sheet. Check URL and sharing.")
        st.stop()

# ====================== MANUAL SCORING + RADAR (Single) ======================
st.subheader("Single Response Analysis (for testing)")
if len(df) > 0:
    row_idx = st.selectbox("Choose response", range(len(df)), format_func=lambda i: f"Response {i+1} - {df.iloc[i].get('Timestamp','')}")
    row = df.iloc[row_idx]

    # Auto-detect question columns (very robust)
    score_cols = [col for col in df.columns if col.startswith("Q") or "track" in col.lower() or "profitable" in col.lower() or "satisfaction" in col.lower()]
    answers = {col: row[col] for col in score_cols if pd.notna(row[col])}

    if answers:
        avg = sum(answers.values()) / len(answers) * 20
        st.metric("Quick Health Score", f"{avg:.0f}/100")

        # Radar (simplified)
        fig = go.Figure(data=go.Scatterpolar(r=[avg]*8, theta=["Fin","Strat","Ops","Cust","People","Risk","Inno","Context"], fill='toself'))
        st.plotly_chart(fig)

# ====================== BATCH GROK ANALYSIS (MAIN FEATURE) ======================
st.subheader("🚀 Batch Analysis with Grok (Location-Aware)")

analyze_all = st.button("Analyze ALL responses with Grok", type="primary", use_container_width=True)

if analyze_all and client:
    progress = st.progress(0)
    status = st.empty()
    results = []

    for idx, row in df.iterrows():
        status.text(f"Analyzing {idx+1}/{len(df)} → {row.get('Business Location', 'Unknown')}")

        location = str(row.get("Business Location", "Global")).strip()
        extra = str(row.get("Additional Context", ""))

        # Build answers string (all columns except metadata)
        answers_text = "\n".join([f"{col}: {row[col]}" for col in df.columns 
                                  if not col in ["Timestamp", "Business Location", "Additional Context"] 
                                  and pd.notna(row[col])])

        prompt = f"""You are a world-class business consultant. Adapt every recommendation to the **exact location** provided.

**Business Location:** {location}

**Questionnaire Answers:**
{answers_text}

**Additional Context:**
{extra}

Write a full professional report:
1. Executive Summary + Health Status
2. Top 3 Strengths
3. Top 3 Concerns
4. 8–10 Actionable Recommendations (Quick wins, Medium, Long-term) — **heavily tailored to {location}** (local laws, economy, power, taxes, incentives, risks, etc.)
5. Next steps

Be practical, encouraging, and realistic."""

        try:
            resp = client.chat.completions.create(
                model="grok-4-1-fast-reasoning",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2200
            )
            report = resp.choices[0].message.content
        except Exception as e:
            report = f"API Error: {str(e)}"

        results.append({
            "Response_ID": idx + 1,
            "Location": location,
            "Timestamp": row.get("Timestamp", ""),
            "AI_Report": report
        })

        progress.progress((idx + 1) / len(df))
        time.sleep(1.1)   # rate limit friendly

    # Show results
    st.success("✅ All reports generated!")
    for r in results:
        with st.expander(f"📍 {r['Location']} – Response {r['Response_ID']}"):
            st.markdown(r['AI_Report'])

    # Save back to sheet
    if st.button("Save all reports to Google Sheet"):
        results_df = pd.DataFrame(results)
        conn.write(results_df, sheet="AI_Reports")
        st.success("Saved to new sheet 'AI_Reports'!")
