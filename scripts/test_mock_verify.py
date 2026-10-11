"""
Verification script: tests /cv/analyze with GEMINI_MOCK=1 or real Groq LLM.
Expects Python and SQL to Match, Docker and Kubernetes to be Missing (or Match for Docker if evidenced).
"""
import os
import sys
import json
import requests

# Fix UnicodeEncodeError on Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

REQUIREMENTS = [
    {"skill": "Python", "level": "intermediate", "importance": "required"},
    {"skill": "SQL", "level": "basic", "importance": "required"},
    {"skill": "Docker", "level": "intermediate", "importance": "required"},
    {"skill": "Kubernetes", "level": "advanced", "importance": "required"},
]

# Robust resolution for minimal sample PDF
CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "backend", "uploads", "0e3b06aa-9674-409a-a426-d730f55ecc85.pdf"),
    os.path.join(os.path.dirname(__file__), "..", "uploads", "0e3b06aa-9674-409a-a426-d730f55ecc85.pdf"),
    os.path.join(os.path.dirname(__file__), "uploads", "0e3b06aa-9674-409a-a426-d730f55ecc85.pdf"),
]
MINIMAL_PDF_PATH = next((p for p in CANDIDATE_PATHS if os.path.exists(p)), CANDIDATE_PATHS[0])

def login():
    r = requests.post(f"{BASE_URL}/login",
                      data={"username": "demo1@example.com", "password": "Test12345"},
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    print(f"[OK] Login => 200  token={token[:20]}...")
    return {"Authorization": f"Bearer {token}"}


def run_analyze(headers, pdf_path, label=""):
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    r = requests.post(
        f"{BASE_URL}/cv/analyze",
        headers=headers,
        files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
        data={"requirements": json.dumps(REQUIREMENTS)},
    )
    print(f"\n[{label}] POST /cv/analyze => {r.status_code}")
    if r.status_code != 200:
        print("  ERROR BODY:", r.text[:500])
        return None
    resp = r.json()
    skills = resp.get("skills", [])
    print(f"  Total skills : {len(skills)}")
    matched = [s for s in skills if s.get("cv_match_status") == "Match"]
    missing = [s for s in skills if s.get("cv_match_status") != "Match"]
    print(f"  Matched      : {[s['skill'] for s in matched]}")
    print(f"  Missing      : {[s['skill'] for s in missing]}")
    print(f"  score_data   : {resp.get('score_data')}")
    print("\n  === FULL RESPONSE ===")
    print(json.dumps(resp, indent=2, default=str)[:4000])
    return resp


def main():
    print("=== Verification: /cv/analyze endpoint run ===")
    headers = login()
    resp_mock = run_analyze(headers, MINIMAL_PDF_PATH, label="EVAL")

    if resp_mock:
        skills = resp_mock.get("skills", [])
        python_skill = next((s for s in skills if s["skill"] == "Python"), None)
        sql_skill = next((s for s in skills if s["skill"] == "SQL"), None)
        docker_skill = next((s for s in skills if s["skill"] == "Docker"), None)
        k8s_skill = next((s for s in skills if s["skill"] == "Kubernetes"), None)

        print("\n=== Verification Results ===")
        if python_skill:
            print(f"  Python: {python_skill['cv_match_status']}")
        if sql_skill:
            print(f"  SQL: {sql_skill['cv_match_status']}")
        if docker_skill:
            print(f"  Docker: {docker_skill['cv_match_status']}")
        if k8s_skill:
            print(f"  Kubernetes: {k8s_skill['cv_match_status']}")

    # Check debug endpoint
    try:
        debug_r = requests.get(f"{BASE_URL}/debug")
        print(f"\n/debug: {debug_r.json()}")
    except Exception as e:
        print(f"\n/debug request failed: {e}")


if __name__ == "__main__":
    main()
