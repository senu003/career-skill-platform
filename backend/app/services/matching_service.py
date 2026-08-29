import re
from typing import List, Dict, Tuple, Set

# Comprehensive alias groups for technical skills.
# Each group contains equivalent forms of a skill (all lowercase).
ALIAS_GROUPS: List[Set[str]] = [
    {"javascript", "js", "ecmascript"},
    {"typescript", "ts"},
    {"react", "react.js", "reactjs", "react js"},
    {"vue", "vue.js", "vuejs", "vue js"},
    {"angular", "angularjs", "angular.js"},
    {"node", "node.js", "nodejs", "node js"},
    {"next", "next.js", "nextjs", "next js"},
    {"express", "express.js", "expressjs"},
    {"postgres", "postgresql", "postgre"},
    {"mongo", "mongodb"},
    {"kubernetes", "k8s"},
    {"docker"},
    {"aws", "amazon web services"},
    {"gcp", "google cloud", "google cloud platform"},
    {"azure", "microsoft azure"},
    {"c++", "cpp"},
    {"c#", "csharp", "c sharp"},
    {".net", "dotnet", ".net core"},
    {"golang", "go"},
    {"python", "py"},
    {"rest", "rest api", "restful", "rest apis"},
    {"ci/cd", "cicd", "continuous integration"},
    {"ml", "machine learning"},
    {"ai", "artificial intelligence"},
    {"nlp", "natural language processing"},
    {"sql server", "mssql"},
]

# Build a lookup map from each alias/name (lowercase) to its set of equivalent variants
ALIAS_MAP: Dict[str, Set[str]] = {}
for group in ALIAS_GROUPS:
    for item in group:
        ALIAS_MAP[item.lower()] = group


def build_skill_regex(variant: str) -> re.Pattern:
    """
    Builds a case-insensitive, word-boundary-aware regex pattern for a skill variant.
    Handles special characters like '+', '#', '.', '/' correctly without failing standard regex \\b checks.
    """
    escaped = re.escape(variant)

    # Determine left boundary guard
    if variant[0].isalnum():
        left_guard = r"(?<![a-zA-Z0-9_])"
    else:
        left_guard = r"(?<![a-zA-Z0-9])"

    # Determine right boundary guard
    last_char = variant[-1]
    if last_char.isalnum():
        if variant.lower() == "c":
            right_guard = r"(?![a-zA-Z0-9_+#])"
        else:
            right_guard = r"(?![a-zA-Z0-9_])"
    elif last_char == "+":
        right_guard = r"(?![a-zA-Z0-9_+#])"
    elif last_char == "#":
        right_guard = r"(?![a-zA-Z0-9_#])"
    else:
        right_guard = r"(?![a-zA-Z0-9_])"

    pattern_str = f"{left_guard}{escaped}{right_guard}"
    return re.compile(pattern_str, re.IGNORECASE)


def extract_snippet(text: str, start: int, end: int, window: int = 50) -> str:
    """
    Extracts a contextual snippet around the match indices [start, end].
    Normalizes whitespace and adds truncation indicators.
    """
    left = max(0, start - window)
    right = min(len(text), end + window)

    raw_snippet = text[left:right]

    # Normalize newlines and spaces
    clean_snippet = re.sub(r'[\r\n\t]+', ' ', raw_snippet)
    clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()

    if left > 0:
        clean_snippet = "..." + clean_snippet
    if right < len(text):
        clean_snippet = clean_snippet + "..."

    return clean_snippet


def get_skill_variants(raw_skill_name: str) -> List[str]:
    """
    Returns a deduplicated list of search variant strings for a given skill name.
    Incorporates standard alias mapping and common variations.
    """
    norm = raw_skill_name.strip().lower()
    variants: List[str] = [raw_skill_name.strip()]

    # Add aliases if found in map
    if norm in ALIAS_MAP:
        for alias in ALIAS_MAP[norm]:
            if alias not in [v.lower() for v in variants]:
                variants.append(alias)
    else:
        # Fallback heuristic variants for unmapped skills
        if norm.endswith(".js"):
            base = norm[:-3]
            variants.extend([base, f"{base}js", f"{base} js"])
        elif norm.endswith("js") and len(norm) > 2:
            base = norm[:-2]
            variants.extend([base, f"{base}.js"])

    # Deduplicate while keeping order
    unique_variants: List[str] = []
    seen = set()
    for v in variants:
        v_clean = v.strip()
        if v_clean and v_clean.lower() not in seen:
            seen.add(v_clean.lower())
            unique_variants.append(v_clean)

    return unique_variants


def match_skills_in_text(
    cv_text: str,
    required_skills: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Matches structured required skills against extracted CV text.

    Args:
        cv_text: The plain text extracted from a CV.
        required_skills: List of required skill dicts, e.g.:
            [{"skill": "Python", "level": "advanced", "importance": "required"}]

    Returns:
        (matched_skills, missing_skills):
            matched_skills: required skill dicts with an added 'evidence' field snippet.
            missing_skills: required skill dicts that were not found in the CV text.
    """
    matched_skills: List[Dict] = []
    missing_skills: List[Dict] = []

    if not cv_text or not cv_text.strip():
        # If CV text is empty, all required skills are missing
        for req in required_skills:
            missing_skills.append(dict(req))
        return matched_skills, missing_skills

    for req in required_skills:
        skill_name = req.get("skill", "")
        if not skill_name or not skill_name.strip():
            continue

        variants = get_skill_variants(skill_name)
        matched_match = None

        # Search across all variants in order
        for variant in variants:
            pattern = build_skill_regex(variant)
            match = pattern.search(cv_text)
            if match:
                matched_match = match
                break

        if matched_match:
            evidence = extract_snippet(
                cv_text,
                matched_match.start(),
                matched_match.end()
            )
            matched_entry = dict(req)
            matched_entry["evidence"] = evidence
            matched_skills.append(matched_entry)
        else:
            missing_entry = dict(req)
            missing_skills.append(missing_entry)

    return matched_skills, missing_skills
