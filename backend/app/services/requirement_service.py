import os
import json
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

# Create Gemini client
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def normalize_requirement_level(level: Optional[str]) -> str:
    """
    Sanitize extracted requirement levels.
    Maps to canonical basic/intermediate/advanced or defaults to unspecified.
    """
    if level is None:
        return "unspecified"
        
    level = str(level).strip().lower()
    
    if level in ["basic", "intermediate", "advanced"]:
        return level
        
    return "unspecified"


def extract_requirements(text: str):

    prompt = f"""
You are a job requirement extraction system.

Extract technical skills from the company requirements below.

For each skill return:
- skill
- level
- importance

Allowed levels:
basic
intermediate
advanced
unspecified

Allowed importance:
required
preferred

Rules:
1. Extract programming languages, frameworks, libraries,
   databases, cloud platforms, tools, and technical concepts.
2. Do not extract soft skills such as communication,
   teamwork, leadership, motivation, or willingness to learn.
3. If a skill has an explicit level, use that level.
4. If no level is explicitly stated, use "unspecified".
5. If a skill is described as preferred, desirable,
   nice to have, or a plus, mark it as "preferred".
6. Otherwise mark it as "required".
7. Extract every separate skill.
8. Do not invent skills.
9. Return ONLY valid JSON.

Return exactly this structure:
{{
    "requirements": [
        {{
            "skill": "Python",
            "level": "intermediate",
            "importance": "required"
        }}
    ]
}}

Company requirements:
{text}
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    data = {"requirements": []}

    if response.parsed is not None:
        data = response.parsed
    elif response.text:
        try:
            data = json.loads(response.text)
        except Exception:
            pass
            
    # Normalize the extracted levels
    if isinstance(data, dict) and "requirements" in data and isinstance(data["requirements"], list):
        for req in data["requirements"]:
            if isinstance(req, dict) and "level" in req:
                req["level"] = normalize_requirement_level(req["level"])

    return data
