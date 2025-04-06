import google.generativeai as genai
import os
import json

genai.configure(api_key="")

model = genai.GenerativeModel("gemini-2.0-flash")


def analyze_update_texts(updates):
    all_updates = "\n".join([f"{u['Name']} ({u['Project']}): {u['Update']}" for u in updates])
    prompt = f"Analyze the following updates and summarize key themes, progress sentiment, and any blockers:\n\n{all_updates}"
    
    response = model.generate_content(prompt)
    return response.text


def parse_update(text):
    prompt = f"""
    You will be given an update text. Extract the following fields:
    - Name: The person's name.
    - Project: The name of the project, if mentioned.
    - Update: The rest of the update or status content.

    Return only a valid JSON object with the keys: "Name", "Project", and "Update".
    If no project is mentioned, set "Project" to null.

    Text: "{text}"
    """

    response = model.generate_content(prompt)
    
    try:
        result_dict = json.loads((response.text[7:-3]))  # Converts JSON string to Python dict
    except json.JSONDecodeError:
        print("Failed to parse JSON. Raw response:")
        print(response.text)
        return None

    return result_dict

# Example usage
text_update = "Hey, this is Aadi. I'm finalizing the UI for the story generator today."
t2 = "Hey, aadi here, i finished the UI on figma, also collaborated with sawant fort the user benchmarking of the project"
parsed_dict = parse_update(text_update)
p2 = parse_update(t2)
# print(parsed_dict)  # This is a Python dictionary

print(analyze_update_texts([parsed_dict, p2]))
