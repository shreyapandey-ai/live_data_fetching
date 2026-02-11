import streamlit as st
import os
import json
import re
import wikipediaapi
from google import genai
from dotenv import load_dotenv

# ---------------- SETUP ----------------
load_dotenv()
DATA_FILE = "research_data.json"

wiki_api = wikipediaapi.Wikipedia(language="en", user_agent="KnowledgeBot/2.0")

def get_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        return genai.Client(api_key=api_key)
    except Exception: return None

client = get_client()

# ---------------- CORE FUNCTIONS ----------------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def scrape_new_topic(topic_name):
    page = wiki_api.page(topic_name)
    if not page.exists(): return False, "Topic not found on Wikipedia."
    
    words = page.text.split()
    chunks = [{"text": " ".join(words[i:i+400])} for i in range(0, len(words), 400)]
    
    data = load_data()
    # Check for duplicates
    if any(e["entity"].lower() == topic_name.lower() for e in data):
        return False, "Topic already exists."
            
    data.append({
        "entity": page.title,
        "documents": [{"source": "Wikipedia", "url": page.fullurl, "chunks": chunks}]
    })
    save_data(data)
    return True, f"Added {page.title}!"

def get_ai_response(entity_data, question):
    all_sentences = []
    for doc in entity_data.get("documents", []):
        for chunk in doc.get("chunks", []):
            sentences = re.split(r'(?<=[.!?])\s+', chunk["text"])
            all_sentences.extend([s.strip() for s in sentences if s.strip()])
    
    # 1. Try AI First
    if client:
        try:
            context = "\n".join(all_sentences[:40])
            prompt = f"Using this data: {context}\n\nQuestion: {question}\n\nAnswer concisely:"
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return response.text, "AI"
        except Exception: pass

    # 2. SMART LOCAL SEARCH (Fallback)
    query_lower = question.lower()
    query_terms = [w.lower() for w in re.findall(r'\w+', query_lower) if len(w) > 2]
    
    # Define Category Triggers
    category_triggers = {
        "spouse": ["wife", "married", "spouse", "nita", "anushka", "wedding", "marriage", "partner"],
        "wealth": ["net worth", "networth", "billion", "wealth", "crore", "money", "rich", "earnings", "$"],
        "career": ["cricketer", "captain", "chairman", "director", "business", "occupation", "profession"]
    }
    active_cats = [cat for cat, words in category_triggers.items() if any(w in query_lower for w in words)]

    scored_sentences = []
    for sentence in all_sentences:
        score = 0
        sent_lower = sentence.lower()
        for term in query_terms:
            if term in sent_lower:
                score += 5
                if re.search(rf'\b{term}\b', sent_lower): score += 10
        
        # Priority Boosts for Wife/Net-worth
        if "spouse" in active_cats and any(w in sent_lower for w in ["married to", "wife", "spouse"]):
            score += 200
        if "wealth" in active_cats and any(w in sent_lower for w in ["net worth", "billion", "crore", "$"]):
            score += 200

        if score > 0: scored_sentences.append((score, sentence))
    
    if not scored_sentences: return "No details found in local data.", "Local"

    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    top_results = list(dict.fromkeys([s[1] for s in scored_sentences]))[:2]
    return " ".join(top_results), "Local"

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="AI Research Bot", layout="centered", page_icon="🤖")
st.title("🤖 Knowledge Bot")

data = load_data()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    if data:
        entity_names = [e["entity"] for e in data]
        selected_topic = st.selectbox("Current Topic", entity_names)
        entity = next(e for e in data if e["entity"] == selected_topic)
    else:
        st.warning("No data found.")
        entity = None

    st.divider()
    st.subheader("➕ Add Topic")
    new_topic = st.text_input("Wiki Topic Name")
    if st.button("Scrape & Add"):
        if new_topic:
            with st.spinner("Scraping..."):
                success, msg = scrape_new_topic(new_topic)
                if success: st.success(msg); st.rerun()
                else: st.error(msg)
    
    status_container = st.empty()

# --- MAIN CHAT ---
if not entity:
    st.info("👈 Add a topic in the sidebar to begin!")
else:
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input(f"Ask about {selected_topic}..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            res, src = get_ai_response(entity, prompt)
            if src == "AI": status_container.success("🌐 Status: AI Brain Online")
            else: status_container.warning("📁 Status: Local Search Mode")
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})