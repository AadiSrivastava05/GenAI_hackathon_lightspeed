from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import re

app = Flask(__name__)
genai.configure(api_key="ENTER_API_KEY")
model = genai.GenerativeModel("gemini-2.0-flash")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate_report', methods=['POST'])
def generate_report():
    updates = request.json.get('updates', [])
    if not updates:
        return jsonify({'error': 'No updates provided'}), 400

    raw_text = "\n".join(updates)

    prompt = (
        "Analyze the following employee work updates:\n"
        f"{raw_text}\n\n"
        "1. Provide a brief summary.\n"
        "2. Identify all possible visualizations (bar, pie, line, etc.) based on numerical and temporal data.\n"
        "3. Create as many graphs as you can.\n"
        "4. Every graph must have more than one component; if there are graphs with only one component, merge them.\n"
        "5. You should always include a pie chart which shows the total distribution of effort into various fields.\n"
        "6. Output a JSON in this format ONLY (using double quotes):\n\n"
        '{\n'
        '  "summary": "...",\n'
        '  "charts": [\n'
        '    {\n'
        '      "title": "...",\n'
        '      "type": "bar" | "pie" | "line",\n'
        '      "labels": [...],\n'
        '      "data": [...]\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "Only return the JSON object. Do not add explanations or markdown. Use 'line' chart if updates span over dates, days, or show a trend."
    )

    prompt2 = '''
        Extract numerical metrics as key-value pairs such as 'Tasks Completed': 12, 'Meetings Attended': 4, etc.
        Output a JSON in this format ONLY (using double quotes):\n\n"
        '{\n'
        "  'metrics': {\n"
        "     '...': ...,\n"
        "     ...\n"
        "  },\n"    
        '}\n\n'
        "Only return the JSON object. Do not add explanations or markdown.
    '''
    while True:
        try:
            response_text = model.generate_content(prompt).text.strip()

            import re, json

            match = re.search(r'\{[\s\S]+\}', response_text)
            if not match:
                return jsonify({'error': 'Failed to parse Gemini response', 'raw': response_text}), 500

            json_str = match.group()

            json_str = json_str.replace("'", '"')

            parsed = json.loads(json_str)
            return jsonify(parsed)

        except Exception as e:
            pass


if __name__ == '__main__':
    app.run(debug=True)
