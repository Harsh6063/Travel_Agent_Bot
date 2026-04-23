import kagglehub

# Download latest version
path = kagglehub.dataset_download("kumarperiya/explore-india-a-tourist-destination-dataset")

print("Path to dataset files:", path)

import pandas as pd

df_new = pd.read_json("india_destinations.json")

print(df_new.head())

df_new.to_csv("generated_data.csv", index=False)

# Remove duplicates within new data
df_new.drop_duplicates(subset=["Destination Name"], inplace=True)

# Standardize text
df_new["Destination Name"] = df_new["Destination Name"].str.strip()
df_new["State"] = df_new["State"].str.strip()

# Optional: capitalize properly
df_new["Category"] = df_new["Category"].str.title()df_old = pd.read_csv("Expanded_Indian_Travel_Dataset.csv")

existing_places = set(df_old["Destination Name"].str.lower())

df_new = df_new[~df_new["Destination Name"].str.lower().isin(existing_places)]

df_final = pd.concat([df_old, df_new], ignore_index=True)df_final.drop_duplicates(subset=["Destination Name"], inplace=True)
df_final.reset_index(drop=True, inplace=True)
print(df_final)
df_final.to_csv("Final_datset.csv", index=False)
import pandas as pd
from transformers import pipeline

# -----------------------------
# LOAD DATA
# -----------------------------
df = pd.read_csv("Final_datset.csv")

# -----------------------------
# CLEAN DATA
# -----------------------------
df.drop_duplicates(subset=["Destination Name"], inplace=True)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# -----------------------------
# STANDARDIZE STATE NAMES
# -----------------------------
state_mapping = {
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "Andaman & Nicobar": "Andaman and Nicobar Islands",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu"
}

df["State"] = df["State"].replace(state_mapping)

# -----------------------------
# NORMALIZE CATEGORY
# -----------------------------
def normalize_category(cat):
    cat = str(cat).lower()

    if "hill" in cat or "mountain" in cat:
        return "Mountains"
    elif "beach" in cat:
        return "Beach"
    elif "heritage" in cat:
        return "Heritage"
    elif "religious" in cat:
        return "Religious"
    elif "adventure" in cat:
        return "Adventure"
    else:
        return "Nature"

df["Category"] = df["Category"].apply(normalize_category)

# -----------------------------
# LOAD HUGGING FACE MODEL
# -----------------------------
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-base",
    max_length=80
)

# -----------------------------
# BATCH DESCRIPTION GENERATION
# -----------------------------
def generate_descriptions_batch(df, batch_size=16):
    descriptions = []

    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]

        prompts = [
            f"Write a short travel description for {row['Destination Name']} in {row['State']} known for {row['Popular Attraction']}."
            for _, row in batch.iterrows()
        ]

        try:
            outputs = generator(prompts)
            descriptions.extend([o['generated_text'] for o in outputs])
        except:
            descriptions.extend(["Travel destination"] * len(batch))

    return descriptions

df["Description"] = generate_descriptions_batch(df)

# -----------------------------
# ACTIVITIES
# -----------------------------
def get_activities(category):
    category = str(category).lower()

    if "beach" in category:
        return "swimming, sunbathing, water sports, nightlife"
    elif "mountain" in category:
        return "trekking, hiking, camping, snow activities"
    elif "nature" in category:
        return "sightseeing, photography, relaxation"
    elif "heritage" in category:
        return "monument visits, cultural tours"
    elif "religious" in category:
        return "temple visits, spiritual activities"
    elif "adventure" in category:
        return "rafting, trekking, camping, skiing"
    else:
        return "exploration"

df["Activities"] = df["Category"].apply(get_activities)

# -----------------------------
# BUDGET
# -----------------------------
def get_budget(state):
    state = str(state).lower()

    high = ["goa", "kerala", "andaman and nicobar islands", "lakshadweep"]
    medium = [
        "himachal pradesh", "uttarakhand", "rajasthan",
        "karnataka", "maharashtra", "tamil nadu"
    ]

    if state in high:
        return "high"
    elif state in medium:
        return "medium"
    else:
        return "low"

df["Budget"] = df["State"].apply(get_budget)

# -----------------------------
# BEST TIME
# -----------------------------
def get_best_time(category):
    category = str(category).lower()

    if "beach" in category:
        return "November to February"
    elif "mountain" in category:
        return "March to June"
    elif "nature" in category:
        return "October to March"
    elif "heritage" in category:
        return "October to March"
    elif "religious" in category:
        return "All year"
    elif "adventure" in category:
        return "March to June"
    else:
        return "All year"

df["Best_Time"] = df["Category"].apply(get_best_time)

# -----------------------------
# FINAL CLEANUP
# -----------------------------
df.drop_duplicates(subset=["Destination Name"], inplace=True)
df.reset_index(drop=True, inplace=True)

# -----------------------------
# SAVE FINAL DATASET
# -----------------------------

df.to_csv("Travel_Dataset_Custom.csv")
print("✅ FINAL DATASET READY 🚀")
print("Shape:", df.shape)
print(df.head())