import streamlit as st
import json
import re
import os
from pyvis.network import Network
import streamlit.components.v1 as components

DATA_FILE = "research_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def create_knowledge_graph(data):
    net = Network(height="650px", width="100%", bgcolor="#1a1a1a", font_color="white", notebook=False)
    
    connection_counts = {e["entity"]: 0 for e in data}
    entities = [e["entity"] for e in data]
    edges = []

    # Map mentions
    for entity_obj in data:
        source = entity_obj["entity"]
        full_text = " ".join([c["text"].lower() for d in entity_obj.get("documents", []) for c in d.get("chunks", [])])
        for target in entities:
            if source != target and target.lower() in full_text:
                edges.append((source, target))
                connection_counts[target] += 1

    # Add Nodes with Visual Styles
    for entity_obj in data:
        name = entity_obj["entity"]
        color, shape = "#00ffcc", "dot"
        
        name_l = name.lower()
        if any(x in name_l for x in ["kohli", "musk", "ambani"]):
            color, shape = "#3399ff", "star" # People
        elif any(x in name_l for x in ["india", "mandir", "mumbai"]):
            color, shape = "#ff9933", "diamond" # Locations
            
        node_size = 25 + (connection_counts[name] * 5)
        net.add_node(name, label=name, title=f"Connections: {connection_counts[name]}", 
                     color=color, shape=shape, size=node_size)

    for source, target in edges:
        net.add_edge(source, target, color="#555555", width=2, arrows="to")

    net.save_graph("knowledge_graph.html")
    with open("knowledge_graph.html", 'r', encoding='utf-8') as f:
        return f.read()

st.set_page_config(page_title="Knowledge Map", layout="wide")
st.title("🕸️ Research Knowledge Map")

data = load_data()
if data:
    html_data = create_knowledge_graph(data)
    components.html(html_data, height=700)
else:
    st.error("No data found! Scrape topics in app.py first.")