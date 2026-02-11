import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import wikipedia
import wikipediaapi
from google import genai

# ---------------- SETUP ----------------
load_dotenv()
DATA_FILE = "research_data.json"

wiki_api = wikipediaapi.Wikipedia(
    language="en",
    user_agent="ResearchBot/2.0"
)

client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

# ---------------- UTILITIES ----------------

def chunk_text(text, chunk_size=400):
    words = text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_document(entity_name, document):
    data = load_data()
    for entity in data:
        if entity["entity"] == entity_name:
            entity["documents"].append(document)
            save_data(data)
            return
    data.append({"entity": entity_name, "documents": [document]})
    save_data(data)

# ---------------- WIKIPEDIA SCRAPER ----------------

def scrape_wikipedia(query):
    results = wikipedia.search(query, results=1)
    if not results:
        print("❌ Not found")
        return

    title = results[0]
    page = wiki_api.page(title)
    if not page.exists():
        print("❌ Page does not exist")
        return

    full_text = page.summary + "\n"

    def collect_sections(sections):
        text = ""
        for s in sections:
            if s.text.strip():
                text += f"\n{s.title}\n{s.text}\n"
            text += collect_sections(s.sections)
        return text

    full_text += collect_sections(page.sections)
    chunks = chunk_text(full_text)
    if not chunks:
        print("❌ No content extracted")
        return

    document = {
        "source": "Wikipedia",
        "url": page.fullurl,
        "chunks": [{"text": c} for c in chunks]
    }

    save_document(page.title, document)
    print(f"✅ Wikipedia data saved for {page.title}")

# ---------------- GENERIC URL SCRAPER ----------------

def scrape_from_url(url):
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "Unknown"
        paragraphs = " ".join([p.get_text() for p in soup.find_all("p")])
        if not paragraphs.strip():
            print("❌ No readable content found")
            return
        chunks = chunk_text(paragraphs)
        document = {
            "source": "Web",
            "url": url,
            "chunks": [{"text": c} for c in chunks]
        }
        save_document(title, document)
        print(f"✅ Web data saved for {title}")
    except Exception as e:
        print("❌ Failed to scrape URL:", e)

# ---------------- RETRIEVAL & QA ----------------

def score_chunk(chunk, question):
    score = 0
    question_words = question.lower().split()
    for word in question_words:
        if len(word) > 3 and word in chunk.lower():
            score += 2
        elif word in chunk.lower():
            score += 1
    return score

def retrieve_chunks(entity, question, top_k=3):
    scored = []
    for doc in entity["documents"]:
        for chunk in doc["chunks"]:
            score = score_chunk(chunk["text"], question)
            if score > 0:
                scored.append({
                    "score": score,
                    "text": chunk["text"],
                    "source": doc["source"],
                    "url": doc["url"]
                })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def answer_question(entity, question):
    relevant_chunks = retrieve_chunks(entity, question)
    if not relevant_chunks:
        return "Data not found."

    context = ""
    for chunk in relevant_chunks:
        context += f"\n[Source: {chunk['source']} | URL: {chunk['url']}]\n"
        context += chunk["text"] + "\n"

    prompt = f"""
Answer using ONLY the provided data.
Cite source names in brackets like [Wikipedia] after each fact.
If answer not found, reply exactly: Data not found.

DATA:
{context}

QUESTION:
{question}
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        answer = response.text.strip()
    except Exception:
        # fallback if Gemini quota fails
        best = relevant_chunks[0]
        return f"{best['text'][:500]}...\n\nSource: {best['source']} - {best['url']}"

    sources = set((c["source"], c["url"]) for c in relevant_chunks)
    source_text = "\n\nSources:\n"
    for i, (s, u) in enumerate(sources, 1):
        source_text += f"{i}. {s} - {u}\n"

    return answer + source_text

# ---------------- LIBRARY SUMMARY ----------------

def show_library_summary():
    data = load_data()
    if not data:
        print("❌ No data stored")
        return

    print("\n===== LIBRARY SUMMARY =====\n")
    for i, entity in enumerate(data, 1):
        print(f"{i}. {entity['entity']}")
        if "documents" in entity:
            for doc in entity["documents"]:
                source = doc.get("source", "Unknown")
                url = doc.get("url", "No URL")
                chunk_preview = doc.get("chunks", [])
                preview_text = chunk_preview[0]["text"][:80] + "..." if chunk_preview else "No text"
                print(f"   - Source: {source}, URL: {url}, Preview: {preview_text}")
        print()

# ---------------- CLI ----------------

def start():
    print("\n===== MULTI-SOURCE RESEARCH BOT =====")
    while True:
        print("\n1. Scrape Wikipedia")
        print("2. Scrape From URL")
        print("3. Library Summary")
        print("4. Ask Question")
        print("5. Exit")

        choice = input("> ").strip()

        if choice == "1":
            topic = input("Enter topic: ").strip()
            scrape_wikipedia(topic)

        elif choice == "2":
            url = input("Enter URL: ").strip()
            scrape_from_url(url)

        elif choice == "3":
            show_library_summary()

        elif choice == "4":
            data = load_data()
            if not data:
                print("❌ No data stored")
                continue
            for i, e in enumerate(data, 1):
                print(f"{i}. {e['entity']}")
            try:
                pick = int(input("Pick entity number: ")) - 1
                entity = data[pick]
            except:
                print("Invalid selection")
                continue
            print("\nAsk question (type 'exit' to leave)")
            while True:
                q = input("> ").strip()
                if q.lower() == "exit":
                    break
                print(answer_question(entity, q))

        elif choice == "5":
            break

if __name__ == "__main__":
    start()
