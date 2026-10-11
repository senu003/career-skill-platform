import os
import json
import hashlib
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load variables from .env
load_dotenv(override=True)

# Create Gemini client
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

class GeminiQuotaError(Exception):
    pass



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


def extract_requirements(text: str, mock: bool = False, refresh: bool = False):

    if os.environ.get("GEMINI_MOCK") == "1": mock = True
    if os.environ.get("GEMINI_REFRESH") == "1": refresh = True

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

    prompt_version = "v1"
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    elif provider == "flash-lite":
        model_name = "gemini-2.5-flash-lite"
    else:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    cache_key = hashlib.sha256(f"{text}_{model_name}_{prompt_version}".encode('utf-8')).hexdigest()
    cache_dir = os.path.join(os.getcwd(), 'eval', 'cache')
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")
    
    if mock:
        return {"requirements": []}
        
    if not refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    data = {"requirements": []}
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if provider == "groq":
                import openai
                import httpx
                transport = httpx.HTTPTransport(retries=3, verify=False)
                http_client = httpx.Client(transport=transport, timeout=30.0)
                groq_client = openai.OpenAI(
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url="https://api.groq.com/openai/v1",
                    http_client=http_client
                )
                from fastapi import HTTPException as _HTTPException
                try:
                    models = groq_client.models.list().data
                    valid_models = [m.id for m in models]
                    if model_name not in valid_models:
                        raise _HTTPException(
                            status_code=502,
                            detail=f"GROQ_MODEL '{model_name}' is not in Groq's available model list. "
                                   f"Available models: {valid_models}. Set a valid GROQ_MODEL in .env."
                        )
                except _HTTPException:
                    raise
                except Exception as e:
                    raise _HTTPException(
                        status_code=502,
                        detail=f"Unable to validate GROQ_MODEL '{model_name}' against Groq's model list: {e}. "
                               f"Set a valid GROQ_MODEL in .env."
                    )
                    
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                text = response.choices[0].message.content
                if not text or not text.strip():
                    raise ValueError("Empty response from LLM")
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON response from LLM")
            else:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                if response.parsed is not None:
                    data = response.parsed
                elif response.text:
                    try:
                        data = json.loads(response.text)
                    except Exception:
                        pass
            break
        except Exception as e:
            from fastapi import HTTPException
            # Re-raise HTTPException directly — they already carry the right status code and message
            if isinstance(e, HTTPException):
                raise
            err_str = str(e)
            if "429" in err_str or "503" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Empty response" in err_str or "Invalid JSON" in err_str or "json_validate_failed" in err_str:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 2
                    import re
                    match = re.search(r"retryDelay':\s*'([0-9]+)s'", err_str)
                    if match:
                        sleep_time = int(match.group(1))
                    print(f"Quota exceeded/Unavailable/JSON Error. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                else:
                    raise HTTPException(status_code=502, detail=f"LLM Provider Error after {max_retries} retries: {e}")
            else:
                raise HTTPException(status_code=502, detail=f"LLM Provider Error: {e}")

    # Normalize the extracted levels
    if isinstance(data, dict) and "requirements" in data and isinstance(data["requirements"], list):
        for req in data["requirements"]:
            if isinstance(req, dict) and "level" in req:
                req["level"] = normalize_requirement_level(req["level"])

    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    return data


def evaluate_cv_with_gemini(cv_text: str, requirements: list, mock: bool = False, refresh: bool = False) -> list:
    """
    Evaluates candidate CV text against extracted job skill requirements using Gemini.
    
    Returns a list of dicts for each required skill:
    - skill (str)
    - required_level (str)
    - importance (str)
    - cv_level ('basic' | 'intermediate' | 'advanced' | 'unspecified' | 'not_found')
    - cv_match_status ('Match' | 'Needs Improvement' | 'Missing')
    - evidence (str or None)
    """
    if os.environ.get("GEMINI_MOCK") == "1": mock = True
    if os.environ.get("GEMINI_REFRESH") == "1": refresh = True

    if not requirements:
        return []

    # Clean inputs
    cleaned_reqs = []
    for r in requirements:
        if isinstance(r, dict) and "skill" in r:
            s_name = r["skill"].strip()
            if s_name:
                cleaned_reqs.append({
                    "skill": s_name,
                    "level": normalize_requirement_level(r.get("level") or r.get("required_level")),
                    "importance": r.get("importance", "required")
                })

    if not cleaned_reqs:
        return []

    if not cv_text or not cv_text.strip():
        # Empty CV -> all skills missing
        return [
            {
                "skill": req["skill"],
                "required_level": req["level"],
                "importance": req["importance"],
                "cv_level": "not_found",
                "cv_match_status": "Missing",
                "evidence": None
            }
            for req in cleaned_reqs
        ]

    prompt = f"""
You are an expert technical CV evaluator system.

Evaluate the candidate's CV text below against the list of required job skills and required proficiency levels.

For EACH required skill in the list, evaluate the candidate's CV text and determine:
1. `cv_level`: The candidate's inferred skill level strictly based on evidence present in the CV text.
   Allowed values:
   - "basic": CV demonstrates beginner/basic usage, coursework, academic exposure, simple projects, or basic familiarity.
   - "intermediate": CV demonstrates practical hands-on application, building complete applications, professional experience using standard features, hooks, routing, state management, complex queries, or intermediate proficiency.
   - "advanced": CV demonstrates deep mastery, architecture design, performance tuning, leading projects, optimization, or extensive production experience.
   - "unspecified": The skill is mentioned in the CV, but there is not enough detail to infer whether it is basic, intermediate, or advanced.
   - "not_found": The skill is not mentioned or supported anywhere in the CV text.

2. `cv_match_status`: The match status comparing candidate CV evidence against the required level.
   Allowed values:
   - "Match": The skill is demonstrated in the CV and the CV evidence appears to satisfy or exceed the required level.
     (Special Rule: If the required level is "unspecified", and the skill is demonstrated in the CV, status MUST be "Match".)
   - "Needs Improvement": The skill is demonstrated in the CV, but the CV evidence appears weaker than the required level.
     (Example: CV says "Familiar with React" [basic level], but required level is "intermediate" or "advanced" -> "Needs Improvement".)
   - "Missing": The skill is NOT demonstrated in the CV text.
     (Special Rule: If required level is "unspecified" and skill is not demonstrated in CV, status MUST be "Missing".)

3. `evidence`: A short, useful CV-grounded explanation or snippet (1-2 sentences max) directly showing why this level was inferred. If skill is not found in CV, return null.

4. `actionable_feedback`: An object with actionable feedback regarding this skill in the CV, or null if no specific feedback applies. If present, it must include:
   - `section`: CV section (e.g., 'Experience', 'Skills', 'Projects'), when identifiable. Null if unknown.
   - `original_text`: Original supporting text from the CV exactly as written, when available. Null if not identifiable.
   - `category`: Must be one of 'safe rewrite', 'clarification needed', or 'requirement not evidenced'.
     - 'safe rewrite': Facts in the CV support a stronger or clearer wording.
     - 'clarification needed': The CV implies the skill but lacks detail.
     - 'requirement not evidenced': The skill is not mentioned in the CV.
   - `priority`: 'high', 'medium', or 'low'.
   - `explanation`: Why the improvement matters.
   - `suggested_wording`: Suggested wording when facts support a rewrite. Null if information is insufficient.
   - `follow_up_questions`: Array of strings containing follow-up questions when clarification is needed. Empty array if none.
   - `next_action`: Concrete next action for the user.

EVALUATION RULES:
- Evaluate ONLY what is explicitly supported by the CV text.
- DO NOT invent experience, projects, years, technologies, achievements, proficiency levels, or numerical results that are not present in the CV.
- “Familiar with React” cannot become “Built React applications” without supporting information.
- “Built multiple React applications” cannot become “Built multiple React applications using hooks and routing” if hooks and routing are not mentioned.
- If a skill is absent, explain that it is not evidenced in the CV. Do not conclude that the candidate lacks the skill.
- For missing details, return clarification questions and leave suggested wording empty.
- Assessment performance can inform learning advice; it cannot prove professional experience.
- Do not invent CV section names when extraction cannot identify them reliably.
- Do not treat a simple keyword mention as automatically proving a required Intermediate or Advanced level.
- Return ONLY valid JSON.

Job Requirements:
{json.dumps(cleaned_reqs, indent=2)}

Candidate CV Text:
{cv_text}

Return JSON with this exact structure:
{{
    "evaluations": [
        {{
            "skill": "React",
            "cv_level": "basic",
            "cv_match_status": "Needs Improvement",
            "evidence": "CV mentions being familiar with React, indicating basic exposure rather than the required Intermediate level.",
            "actionable_feedback": {{
                "section": "Skills",
                "original_text": "Familiar with React",
                "category": "clarification needed",
                "priority": "high",
                "explanation": "React is a required intermediate skill. Basic familiarity does not meet the requirement.",
                "suggested_wording": null,
                "follow_up_questions": ["What specific components or applications have you built with React?", "Have you used state management like Redux or Context API?"],
                "next_action": "Add details about specific React features you have used and projects you contributed to."
            }}
        }}
    ]
}}
"""

    prompt_version = "v1"
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    elif provider == "flash-lite":
        model_name = "gemini-2.5-flash-lite"
    else:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    cache_key = hashlib.sha256(f"{cv_text}_{json.dumps(cleaned_reqs)}_{model_name}_{prompt_version}".encode('utf-8')).hexdigest()
    cache_dir = os.path.join(os.getcwd(), 'eval', 'cache')
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")
    
    eval_data = None
    if mock:
        eval_data = {"evaluations": []}
    elif not refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                eval_data = json.load(f)
        except Exception:
            pass

    if eval_data is None:
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if provider == "groq":
                    import openai
                    import httpx
                    transport = httpx.HTTPTransport(retries=3, verify=False)
                    http_client = httpx.Client(transport=transport, timeout=30.0)
                    groq_client = openai.OpenAI(
                        api_key=os.getenv("GROQ_API_KEY"),
                        base_url="https://api.groq.com/openai/v1",
                        http_client=http_client
                    )
                    
                    from fastapi import HTTPException as _HTTPException
                    try:
                        # Check models list to ensure validity
                        models = groq_client.models.list().data
                        valid_models = [m.id for m in models]
                        if model_name not in valid_models:
                            raise _HTTPException(
                                status_code=502,
                                detail=f"GROQ_MODEL '{model_name}' is not in Groq's available model list. "
                                       f"Available models: {valid_models}. Set a valid GROQ_MODEL in .env."
                            )
                    except _HTTPException:
                        raise
                    except Exception as e:
                        raise _HTTPException(
                            status_code=502,
                            detail=f"Unable to validate GROQ_MODEL '{model_name}' against Groq's model list: {e}. "
                                   f"Set a valid GROQ_MODEL in .env."
                        )
                        
                    response = groq_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                    text = response.choices[0].message.content
                    if not text or not text.strip():
                        raise ValueError("Empty response from LLM")
                    try:
                        eval_data = json.loads(text)
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON response from LLM")
                else:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0
                        )
                    )
                    if response.parsed is not None:
                        eval_data = response.parsed
                    elif response.text:
                        eval_data = json.loads(response.text)
                
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(eval_data, f, indent=2)
                break
                    
            except Exception as e:
                from fastapi import HTTPException
                # Re-raise HTTPException directly — they already carry the right status code and message
                if isinstance(e, HTTPException):
                    raise
                err_str = str(e)
                if "429" in err_str or "503" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Empty response" in err_str or "Invalid JSON" in err_str or "json_validate_failed" in err_str:
                    if attempt < max_retries - 1:
                        sleep_time = (2 ** attempt) * 2
                        import re
                        match = re.search(r"retryDelay':\s*'([0-9]+)s'", err_str)
                        if match:
                            sleep_time = min(60, int(match.group(1))) # cap at 60s
                        print(f"Quota exceeded/Unavailable/JSON Error. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise HTTPException(status_code=502, detail=f"LLM Provider Error after {max_retries} retries: {e}")
                else:
                    raise HTTPException(status_code=502, detail=f"CV Evaluation Error: {e}")

    # Build evaluation lookup from Gemini output
    gemini_eval_map = {}
    if isinstance(eval_data, dict) and "evaluations" in eval_data and isinstance(eval_data["evaluations"], list):
        for item in eval_data["evaluations"]:
            if isinstance(item, dict) and "skill" in item:
                gemini_eval_map[item["skill"].strip().lower()] = item

    results = []
    from app.services.matching_service import match_skills_in_text

    # Run regex matching for fallback / snippet locator
    matched_regex, missing_regex = match_skills_in_text(cv_text, cleaned_reqs)
    regex_evidence_map = {r["skill"].strip().lower(): r.get("evidence") for r in matched_regex if "skill" in r}

    ALLOWED_CV_LEVELS = {"basic", "intermediate", "advanced", "unspecified", "not_found"}
    ALLOWED_MATCH_STATUSES = {"Match", "Needs Improvement", "Missing"}

    LEVEL_RANK = {"basic": 1, "intermediate": 2, "advanced": 3}

    for req in cleaned_reqs:
        s_name = req["skill"]
        s_clean = s_name.strip().lower()
        req_level = req["level"]
        importance = req["importance"]

        g_item = gemini_eval_map.get(s_clean)

        if g_item:
            cv_level = str(g_item.get("cv_level", "")).strip().lower()
            cv_match_status = str(g_item.get("cv_match_status", "")).strip()
            evidence = g_item.get("evidence")

            if cv_level not in ALLOWED_CV_LEVELS:
                cv_level = "unspecified" if cv_match_status in ["Match", "Needs Improvement"] else "not_found"

            if cv_match_status not in ALLOWED_MATCH_STATUSES:
                # Sanitize status deterministically
                if cv_level == "not_found":
                    cv_match_status = "Missing"
                elif req_level == "unspecified":
                    cv_match_status = "Match" if cv_level != "not_found" else "Missing"
                elif cv_level == "unspecified":
                    cv_match_status = "Match" if req_level == "basic" else "Needs Improvement"
                else:
                    cv_val = LEVEL_RANK.get(cv_level, 0)
                    req_val = LEVEL_RANK.get(req_level, 0)
                    cv_match_status = "Match" if cv_val >= req_val else "Needs Improvement"

            # Check if Gemini output contradicted rules
            if cv_level == "not_found":
                cv_match_status = "Missing"
                evidence = None
            elif cv_match_status == "Match" and req_level in ["intermediate", "advanced"] and cv_level == "basic":
                cv_match_status = "Needs Improvement"

            if not evidence and cv_match_status != "Missing":
                evidence = regex_evidence_map.get(s_clean)

            # Handle actionable_feedback validation
            actionable_feedback = g_item.get("actionable_feedback")
            if actionable_feedback:
                category = actionable_feedback.get("category")
                if category not in ["safe rewrite", "clarification needed", "requirement not evidenced"]:
                    actionable_feedback["category"] = "requirement not evidenced" if cv_level == "not_found" else "clarification needed"
                
                # Verify original text exists in CV
                original_text = actionable_feedback.get("original_text")
                if original_text and original_text.strip() not in cv_text:
                    # Allow harmless whitespace differences
                    import re
                    normalized_original = re.sub(r'\s+', ' ', original_text.strip())
                    normalized_cv = re.sub(r'\s+', ' ', cv_text)
                    if normalized_original not in normalized_cv:
                        actionable_feedback["original_text"] = None
                        actionable_feedback["suggested_wording"] = None
                        actionable_feedback["category"] = "clarification needed"

            results.append({
                "skill": s_name,
                "required_level": req_level,
                "importance": importance,
                "cv_level": cv_level,
                "cv_match_status": cv_match_status,
                "evidence": evidence,
                "actionable_feedback": actionable_feedback
            })
        else:
            # Fallback when Gemini is missing an item or failed
            regex_ev = regex_evidence_map.get(s_clean)
            if regex_ev:
                # Regex found keyword in text
                cv_level = "unspecified"
                if req_level == "unspecified":
                    cv_match_status = "Match"
                elif req_level == "basic":
                    cv_match_status = "Match"
                else:
                    # For Intermediate/Advanced, do NOT falsely claim Match
                    cv_match_status = "Needs Improvement"
                evidence = regex_ev
            else:
                cv_level = "not_found"
                cv_match_status = "Missing"
                evidence = None

            results.append({
                "skill": s_name,
                "required_level": req_level,
                "importance": importance,
                "cv_level": cv_level,
                "cv_match_status": cv_match_status,
                "evidence": evidence,
                "actionable_feedback": None
            })

    return results
