import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import time

# 1. Page Config must be the first Streamlit command
st.set_page_config(page_title="BizHealth Pro", page_icon="🩺", layout="wide")

st.title("🩺 BizHealth Pro – Global Location-Aware Diagnostic System")
st.caption("Google Form → Auto scoring → Grok AI with location-specific recommendations")

# ====================== SECRETS & CONNECTIONS ======================
client = None
# Ensure secrets are accessed correctly
if "XAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["XAI_API_KEY"], base_url="https://api.x.ai/v1")
else:
    st.sidebar.header("🔑 API Keys")
    xai_key = st.sidebar.text_input("Grok (xAI) API Key", type="password")
    if xai_key:
        client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")

# Initialize Connection
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# ====================== LOAD GOOGLE SHEET ======================
sheet_url = st.sidebar.text_input("Google Sheet URL", 
    value="https://docs.google.com/spreadsheets/d/1z9JpEypqWFVdatk_Wc-XyTGOEUv1gL7b9t9OmlI1fb4/edit")

if sheet_url:
    try:
        # Use a more robust read method
        df = conn.read(spreadsheet=sheet_url, ttl=5)
        st.success(f"✅ Loaded {len(df)} responses")
    except Exception as e:
        st.error(f"Could not connect to sheet. Error: {e}")
        st.stop()
else:
    st.info("Please enter a Google Sheet URL in the sidebar.")
    st.stop()

# ====================== ANALYSIS LOGIC ======================
if len(df) > 0:
    st.subheader("Single Response Analysis")
    # Clean column names to avoid key errors
    df.columns = [str(c).strip() for c in df.columns]
    
    row_idx = st.selectbox("Choose response", range(len(df)), 
                          format_func=lambda i: f"Response {i+1} - {df.iloc[i].get('Timestamp','')}")
    row = df.iloc[row_idx]

    # Scoring Logic
    score_cols = [col for col in df.columns if any(word in col.lower() for word in ["q", "track", "profit", "satisfaction"])]
    
    # Ensure numeric conversion for scoring
    numeric_answers = pd.to_numeric(row[score_cols], errors='coerce').dropna()
    
    if not numeric_answers.empty:
        avg = numeric_answers.mean() * 20 # Assuming 1-5 scale to get to 100
        st.metric("Quick Health Score", f"{avg:.1f}/100")

        fig = go.Figure(data=go.Scatterpolar(
            r=[avg]*8, 
            theta=["Fin","Strat","Ops","Cust","People","Risk","Inno","Context"], 
            fill='toself'
        ))
        st.plotly_chart(fig)

# ====================== BATCH GROK ANALYSIS ======================
st.divider()
st.subheader("🚀 Batch Analysis with Grok (Location-Aware)")

if not client:
    st.warning("Please provide an xAI API Key to run the AI Analysis.")
else:
    analyze_all = st.button("Analyze ALL responses with Grok", type="primary")

    if analyze_all:
        progress = st.progress(0)
        status = st.empty()
        results = []

        for idx, row in df.iterrows():
            loc_val = row.get("Business Location", "Global")
            status.text(f"Analyzing {idx+1}/{len(df)} → {loc_val}")

            # Prepare data for AI
            answers_text = ""
            for col in df.columns:
                if col not in ["Timestamp", "Business Location", "Additional Context"]:
                    answers_text += f"- {col}: {row[col]}\n"

            prompt = f"""You are a business consultant. 
            Location: {loc_val}
            Context: {row.get('Additional Context', 'None')}
            Data: {answers_text}
            
            Provide: 1. Executive Summary, 2. Strengths/Weaknesses, 3. 8-10 Actionable recommendations tailored to {loc_val} laws and economy."""

            try:
                # NOTE: Check your model name. 'grok-beta' is the standard currently.
                # 'grok-4-1-fast-reasoning' might be a typo causing errors.
                response = client.chat.completions.create(
                    model="grok-beta", 
                    messages=[{"role": "user", "content": prompt}]
                )
                report = response.choices[0].message.content
            except Exception as e:
                report = f"AI Error: {str(e)}"

            results.append({
                "ID": idx + 1,
                "Location": loc_val,
                "AI_Report": report
            })

            progress.progress((idx + 1) / len(df))
            time.sleep(0.5)

        st.success("Analysis Complete!")
        for r in results:
            with st.expander(f"Report for {r['Location']} (ID: {r['ID']})"):
                st.markdown(r['AI_Report'])
