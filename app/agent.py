import openai
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# client = OpenAI(
#     # defaults to os.environ.get("OPENAI_API_KEY")
#     api_key="private",
# )
def generate_code_analysis_prompt(filename, content, patch):
    """
    Generates a prompt for analyzing code.
    """
    return f"""
Analyze the following code file "{filename}" for:
- Code style issues
- Bugs
- Performance improvements
- Best practices

Provide the results in JSON format only, without any additional text or explanations. The JSON format should be:
{{
    "issues": [
        {{"type": "<type>", "line": <line>, "description": "<description>", "suggestion": "<suggestion>"}}
    ]
}}

### Full Code:
{content}

### Patch (Changes):
{patch}
"""


def analyze_code_with_openai(filename, content, patch):
    """
    Sends the code and patch to OpenAI for analysis and parses the response into JSON.
    """
    prompt = generate_code_analysis_prompt(filename, content, patch)
    try:
        # Call OpenAI's API
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # Extract response content
        response_content = response.choices[0].message.content.strip()

        # Attempt to parse the response content as JSON
        if '```json' in response_content:
            # Extract JSON from code block
            json_start = response_content.find('```json') + len('```json')
            json_end = response_content.find('```', json_start)
            json_str = response_content[json_start:json_end].strip()
        else:
            json_str = response_content

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON decoding failed: {e}")
        raise Exception("Failed to decode JSON from OpenAI response")
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        raise Exception(f"OpenAI API call failed: {str(e)}")
