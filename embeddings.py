import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# -----------------------------
# LOAD DATA
# -----------------------------
df = pd.read_csv("Data/Travel_Dataset_Custom.csv")

# -----------------------------
# MODEL
# -----------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------------
# CREATE TEXT
# -----------------------------
df["combined_text"] = (
    df["Destination Name"] + " " +
    df["State"] + " " +
    df["Category"] + " " +
    df["Activities"] + " " +
    df["Description"]
)

# -----------------------------
# EMBEDDINGS
# -----------------------------
embeddings = model.encode(df["combined_text"].tolist()).astype("float32")

# -----------------------------
# FAISS INDEX
# -----------------------------
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)

# -----------------------------
# SEARCH FUNCTION
# -----------------------------
def search_destinations(query, top_k=5):
    q_emb = model.encode([query]).astype("float32")
    _, idx = index.search(q_emb, top_k)

    return df.iloc[idx[0]][[
        "Destination Name",
        "State",
        "Category",
        "Budget",
        "Best_Time",
        "Activities"
    ]]