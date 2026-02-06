import json

FILE_PATH = "data/approved_idea.json"

def save_idea(idea_text):
    clean_text = " ".join(idea_text.split())

    data = {
        "business_idea": clean_text
    }

    with open(FILE_PATH, "w") as f:
        json.dump(data, f, indent=2)
