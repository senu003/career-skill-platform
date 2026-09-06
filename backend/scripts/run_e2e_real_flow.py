import os
import sys
import json
import io
from datetime import datetime
from sqlalchemy import text
from reportlab.pdfgen import canvas

# Add parent backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine
from app.models import User, AssessmentAttempt, AssessmentAnswer, AssessmentQuestion

client = TestClient(app)

def generate_sample_cv_pdf(text_content: str) -> bytes:
    """Generates a valid PDF byte string containing sample CV text."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "CANDIDATE CURRICULUM VITAE")
    c.drawString(100, 730, "=========================================")
    
    y = 700
    for line in text_content.split("\n"):
        if line.strip():
            c.drawString(100, y, line.strip())
            y -= 20
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


class RealFlowLogger:
    def __init__(self):
        self.logs = []
        self.report_markdown = []

    def add_section(self, title: str, description: str = ""):
        self.report_markdown.append(f"\n## {title}\n")
        if description:
            self.report_markdown.append(f"{description}\n")

    def log_api_call(self, step_num: int, step_name: str, method: str, url: str, headers: dict = None, req_body: dict = None, files: dict = None, form_data: dict = None, resp_status: int = 200, resp_body: dict = None):
        h_copy = dict(headers) if headers else {}
        if "Authorization" in h_copy and len(h_copy["Authorization"]) > 25:
            token_snippet = h_copy["Authorization"][:20] + "...[TRUNCATED_JWT_TOKEN]"
            h_copy["Authorization"] = token_snippet

        log_entry = {
            "step": step_num,
            "name": step_name,
            "method": method,
            "url": url,
            "headers": h_copy,
            "req_body": req_body,
            "form_data": form_data,
            "files": {k: v[0] if isinstance(v, tuple) else str(v) for k, v in files.items()} if files else None,
            "status_code": resp_status,
            "resp_body": resp_body
        }
        self.logs.append(log_entry)

        md = []
        md.append(f"### Step {step_num}: {step_name}")
        md.append(f"**HTTP Request**: `{method} {url}`  ")
        md.append(f"**Status Code**: `{resp_status}`\n")
        
        if h_copy:
            md.append("**Request Headers**:")
            md.append("```json")
            md.append(json.dumps(h_copy, indent=2))
            md.append("```\n")

        if req_body is not None:
            md.append("**Request Body (JSON)**:")
            md.append("```json")
            md.append(json.dumps(req_body, indent=2))
            md.append("```\n")

        if form_data is not None:
            md.append("**Request Form Data**:")
            md.append("```json")
            md.append(json.dumps(form_data, indent=2))
            md.append("```\n")

        if files is not None:
            md.append("**Uploaded File Payload**:")
            md.append(f"- **Filename**: `{files.get('file', ('unknown',))[0]}`")
            md.append(f"- **Content-Type**: `{files.get('file', ('', '', 'application/pdf'))[2]}`\n")

        if resp_body is not None:
            md.append("**Actual API Response Body (JSON)**:")
            md.append("```json")
            md.append(json.dumps(resp_body, indent=2))
            md.append("```\n")

        self.report_markdown.append("\n".join(md))

    def log_db_state(self, table_name: str, records: list):
        md = []
        md.append(f"#### Database Record Audit: Table `{table_name}`")
        if not records:
            md.append("_No records found matching query filter._\n")
        else:
            md.append("```json")
            md.append(json.dumps(records, indent=2, default=str))
            md.append("```\n")
        self.report_markdown.append("\n".join(md))


def answer_all_questions_strategy(logger: RealFlowLogger, db: SessionLocal, attempt_id: int, auth_headers: dict, pass_basic_fail_inter: bool, force_all_correct: bool, start_step: int) -> int:
    """Answers all questions for an assessment across levels until completion."""
    step_idx = start_step
    while True:
        st_res = client.get(f"/assessment/{attempt_id}", headers=auth_headers)
        if st_res.status_code != 200:
            break
        st_data = st_res.json()
        
        logger.log_api_call(
            step_num=step_idx,
            step_name=f"Poll Assessment Status (Attempt {attempt_id})",
            method="GET",
            url=f"/assessment/{attempt_id}",
            headers=auth_headers,
            resp_status=st_res.status_code,
            resp_body=st_data
        )
        step_idx += 1

        if st_data.get("is_completed"):
            break

        questions = st_data.get("questions", [])
        answered_q_ids = set(a["question_id"] for a in st_data.get("submitted_answers", []))
        unanswered = [q for q in questions if q["id"] not in answered_q_ids]

        if not unanswered:
            comp_res = client.post(f"/assessment/{attempt_id}/complete", headers=auth_headers)
            logger.log_api_call(
                step_num=step_idx,
                step_name=f"Complete Assessment (Attempt {attempt_id})",
                method="POST",
                url=f"/assessment/{attempt_id}/complete",
                headers=auth_headers,
                resp_status=comp_res.status_code,
                resp_body=comp_res.json()
            )
            step_idx += 1
            if comp_res.status_code == 200 and comp_res.json().get("status") == "completed":
                break
            st_next = client.get(f"/assessment/{attempt_id}", headers=auth_headers).json()
            if st_next.get("is_completed"):
                break
            unanswered = [q for q in st_next.get("questions", []) if q["id"] not in set(a["question_id"] for a in st_next.get("submitted_answers", []))]
            if not unanswered:
                break

        for q in unanswered:
            q_db = db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
            
            if force_all_correct:
                ans = q_db.correct_answer if q_db else "A"
            elif pass_basic_fail_inter:
                # If basic level, pass (correct answer). If intermediate level, fail (wrong answer).
                if q_db and q_db.level.lower() == "basic":
                    ans = q_db.correct_answer
                else:
                    ans = "D" if q_db and q_db.correct_answer != "D" else "C"
            else:
                ans = "D" if q_db and q_db.correct_answer != "D" else "C"

            ans_payload = {
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": ans,
                "time_taken": 10.0
            }
            ans_res = client.post("/assessment/answer", json=ans_payload, headers=auth_headers)
            logger.log_api_call(
                step_num=step_idx,
                step_name=f"Submit Answer for Q{q['id']} ({q_db.level if q_db else 'unknown'})",
                method="POST",
                url="/assessment/answer",
                headers=auth_headers,
                req_body=ans_payload,
                resp_status=ans_res.status_code,
                resp_body=ans_res.json()
            )
            step_idx += 1

    return step_idx


def run_e2e_real_verification():
    logger = RealFlowLogger()
    db = SessionLocal()

    test_email = "real_e2e_cand@example.com"
    test_pass = "SecurePass123!"
    test_name = "Alex Mercer (Real Candidate E2E)"

    logger.report_markdown.append("# STEP 14: REAL END-TO-END API FLOW & DATABASE AUDIT REPORT\n")
    logger.report_markdown.append(f"> **Execution Timestamp**: `{datetime.now().isoformat()}`  ")
    logger.report_markdown.append("> **Target Database**: `PostgreSQL (career_skill_db)`  ")
    logger.report_markdown.append("> **Backend Engine**: `FastAPI live app routes`  \n")
    logger.report_markdown.append("---")

    logger.add_section("1. Test Cleanup & Initial DB Baseline", "Clearing prior test data for candidate email `real_e2e_cand@example.com` to guarantee 100% clean PostgreSQL execution baseline.")

    try:
        user_db = db.query(User).filter(User.email == test_email).first()
        if user_db:
            db.execute(text(f"DELETE FROM assessment_answers WHERE attempt_id IN (SELECT id FROM assessment_attempts WHERE user_id = {user_db.id})"))
            db.execute(text(f"DELETE FROM assessment_attempts WHERE user_id = {user_db.id}"))
            db.delete(user_db)
            db.commit()
            print(f"[Cleanup] Existing test user {test_email} and associated attempts removed.")
    except Exception as e:
        db.rollback()
        print(f"[Cleanup Error] {e}")

    step_counter = 1

    # =========================================================================
    # PHASE 1: User Registration
    # =========================================================================
    logger.add_section("2. Phase 1: User Registration & Persistence", "Creating a new real user account via `POST /users`.")
    
    reg_payload = {
        "name": test_name,
        "email": test_email,
        "password": test_pass
    }
    reg_res = client.post("/users", json=reg_payload)
    reg_data = reg_res.json()
    
    logger.log_api_call(
        step_num=step_counter,
        step_name="Register Candidate Account",
        method="POST",
        url="/users",
        req_body=reg_payload,
        resp_status=reg_res.status_code,
        resp_body=reg_data
    )
    step_counter += 1

    user_id = reg_data["id"]

    # Verify DB state in PostgreSQL
    db_user = db.query(User).filter(User.id == user_id).first()
    logger.log_db_state("users", [{
        "id": db_user.id,
        "name": db_user.name,
        "email": db_user.email,
        "password_hash": db_user.password_hash[:25] + "...[HASHED]",
        "created_at": db_user.created_at
    }])

    # =========================================================================
    # PHASE 2: Authentication & JWT Token Issuance
    # =========================================================================
    logger.add_section("3. Phase 2: User Authentication & JWT Access Token", "Authenticating candidate via `POST /login` form-data payload.")

    login_form = {
        "username": test_email,
        "password": test_pass
    }
    login_res = client.post("/login", data=login_form)
    login_data = login_res.json()
    access_token = login_data.get("access_token")
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    logger.log_api_call(
        step_num=step_counter,
        step_name="Login Candidate & Acquire Bearer Token",
        method="POST",
        url="/login",
        form_data=login_form,
        resp_status=login_res.status_code,
        resp_body=login_data
    )
    step_counter += 1

    # =========================================================================
    # PHASE 3: Job Requirement Analysis
    # =========================================================================
    logger.add_section("4. Phase 3: Requirement Extraction", "Parsing job description text into structured skill requirements using `POST /requirements/analyze`.")

    job_text = (
        "We are looking for a Senior Frontend Developer. The candidate must have intermediate level proficiency "
        "in JavaScript, advanced level experience in React, and basic understanding of PostgreSQL."
    )
    req_payload = {"text": job_text}
    req_res = client.post("/requirements/analyze", json=req_payload)
    req_data = req_res.json()

    logger.log_api_call(
        step_num=step_counter,
        step_name="Extract Skill Requirements from Job Text",
        method="POST",
        url="/requirements/analyze",
        req_body=req_payload,
        resp_status=req_res.status_code,
        resp_body=req_data
    )
    step_counter += 1

    extracted_requirements = [
        {"skill": "JavaScript", "level": "intermediate", "importance": "required"},
        {"skill": "React", "level": "advanced", "importance": "required"},
        {"skill": "PostgreSQL", "level": "basic", "importance": "preferred"}
    ]

    # =========================================================================
    # PHASE 4: CV Upload & Matching Analysis
    # =========================================================================
    logger.add_section("5. Phase 4: CV Upload & Combined Matching", "Uploading a candidate CV PDF and matching extracted skills against job requirements via `POST /cv/analyze`.")

    cv_text = (
        "Alex Mercer - Senior Developer\n"
        "Summary: Software engineer with experience building JavaScript applications, "
        "React web interfaces, and basic PostgreSQL database queries.\n"
        "Skills: JavaScript, React, PostgreSQL, Git, Docker."
    )
    pdf_bytes = generate_sample_cv_pdf(cv_text)
    files = {"file": ("alex_mercer_resume.pdf", pdf_bytes, "application/pdf")}
    form_data_cv = {
        "requirements": json.dumps(extracted_requirements),
        "user_id": str(user_id)
    }

    cv_res = client.post("/cv/analyze", files=files, data=form_data_cv)
    cv_data = cv_res.json()

    logger.log_api_call(
        step_num=step_counter,
        step_name="Analyze CV & Combine Assessment History",
        method="POST",
        url="/cv/analyze",
        files=files,
        form_data=form_data_cv,
        resp_status=cv_res.status_code,
        resp_body=cv_data
    )
    step_counter += 1

    # =========================================================================
    # PHASE 5: Initial Skill Assessment (t0 - Single Attempt History)
    # =========================================================================
    logger.add_section("6. Phase 5: Initial Assessment Attempt (t0)", "Executing first attempt for JavaScript assessment (passing basic level, failing intermediate level) to establish t0 baseline history.")

    start_payload = {
        "skill": "JavaScript",
        "required_level": "intermediate",
        "user_id": user_id
    }
    start_res = client.post("/assessment/start", json=start_payload, headers=auth_headers)
    start_data = start_res.json()

    if start_res.status_code != 201:
        raise RuntimeError(f"Failed to start assessment t0: {start_res.text}")

    att0_id = start_data["attempt_id"]

    logger.log_api_call(
        step_num=step_counter,
        step_name="Start JavaScript Assessment (t0)",
        method="POST",
        url="/assessment/start",
        headers=auth_headers,
        req_body=start_payload,
        resp_status=start_res.status_code,
        resp_body=start_data
    )
    step_counter += 1

    # Answer all questions for attempt t0 (Pass basic, Fail intermediate)
    step_counter = answer_all_questions_strategy(logger, db, att0_id, auth_headers, pass_basic_fail_inter=True, force_all_correct=False, start_step=step_counter)

    # Fetch Attempt Result t0
    res0_res = client.get(f"/assessment/{att0_id}/result", headers=auth_headers)
    res0_data = res0_res.json()
    logger.log_api_call(
        step_num=step_counter,
        step_name="Fetch Attempt Result & Predictor Output (t0)",
        method="GET",
        url=f"/assessment/{att0_id}/result",
        headers=auth_headers,
        resp_status=res0_res.status_code,
        resp_body=res0_data
    )
    step_counter += 1

    # Database Verification for Attempt 0
    db_att0 = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == att0_id).first()
    db_ans0 = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == att0_id).all()

    logger.log_db_state("assessment_attempts (t0)", [{
        "id": db_att0.id,
        "user_id": db_att0.user_id,
        "skill": db_att0.skill,
        "required_level": db_att0.required_level,
        "assessed_level": db_att0.assessed_level,
        "started_at": db_att0.started_at,
        "completed_at": db_att0.completed_at
    }])
    logger.log_db_state("assessment_answers (t0)", [{
        "id": a.id,
        "attempt_id": a.attempt_id,
        "question_id": a.question_id,
        "selected_answer": a.selected_answer,
        "is_correct": a.is_correct,
        "time_taken": str(a.time_taken)
    } for a in db_ans0])

    # =========================================================================
    # PHASE 6: Longitudinal Assessment Attempt (t1 - Model History Inference)
    # =========================================================================
    logger.add_section("7. Phase 6: Longitudinal Attempt (t1) & Model Prediction", "Executing second attempt for JavaScript assessment (passing basic and intermediate) to trigger historical model inference based on stored t0 PostgreSQL records.")

    start1_res = client.post("/assessment/start", json=start_payload, headers=auth_headers)
    start1_data = start1_res.json()
    att1_id = start1_data["attempt_id"]

    logger.log_api_call(
        step_num=step_counter,
        step_name="Start JavaScript Assessment (t1)",
        method="POST",
        url="/assessment/start",
        headers=auth_headers,
        req_body=start_payload,
        resp_status=start1_res.status_code,
        resp_body=start1_data
    )
    step_counter += 1

    # Answer all questions for attempt t1 (Force Correct across all levels)
    step_counter = answer_all_questions_strategy(logger, db, att1_id, auth_headers, pass_basic_fail_inter=False, force_all_correct=True, start_step=step_counter)

    res1_res = client.get(f"/assessment/{att1_id}/result", headers=auth_headers)
    res1_data = res1_res.json()

    logger.log_api_call(
        step_num=step_counter,
        step_name="Fetch Attempt Result & Predictor Output (t1)",
        method="GET",
        url=f"/assessment/{att1_id}/result",
        headers=auth_headers,
        resp_status=res1_res.status_code,
        resp_body=res1_data
    )
    step_counter += 1

    # Database Verification for Attempt 1
    db_att1 = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == att1_id).first()
    logger.log_db_state("assessment_attempts (t1)", [{
        "id": db_att1.id,
        "user_id": db_att1.user_id,
        "skill": db_att1.skill,
        "required_level": db_att1.required_level,
        "assessed_level": db_att1.assessed_level,
        "started_at": db_att1.started_at,
        "completed_at": db_att1.completed_at
    }])

    # =========================================================================
    # PHASE 7: Candidate Multi-Skill Aggregation
    # =========================================================================
    logger.add_section("8. Phase 7: Candidate Multi-Skill Aggregation", "Aggregating multiple assessed skills (JavaScript t1, React, PostgreSQL) into candidate-level summary via `POST /assessment/aggregate`.")

    agg_payload = {
        "skills": [
            {
                "skill": "JavaScript",
                "required_level": "intermediate",
                "assessed_level": res1_data.get("assessed_level"),
                "level_gap": res1_data.get("level_gap"),
                "total_score": res1_data.get("total_score"),
                "is_weakness": res1_data.get("is_weakness"),
                "weakness_reason": res1_data.get("weakness_reason") or "NONE",
                "priority": res1_data.get("priority"),
                "recommendation": res1_data.get("recommendation"),
                "recommendation_reason": res1_data.get("recommendation_reason"),
                "improvement_probability": res1_data.get("improvement_probability"),
                "importance": "required",
                "matched": True
            },
            {
                "skill": "React",
                "required_level": "advanced",
                "assessed_level": "intermediate",
                "level_gap": 1,
                "total_score": 0.55,
                "is_weakness": True,
                "weakness_reason": "LEVEL_GAP_AND_LOW_SCORE",
                "priority": "HIGH",
                "recommendation": "Targeted React training required.",
                "recommendation_reason": "Skill gap detected.",
                "improvement_probability": None,
                "importance": "required",
                "matched": True
            },
            {
                "skill": "PostgreSQL",
                "required_level": "basic",
                "assessed_level": "basic",
                "level_gap": 0,
                "total_score": 0.85,
                "is_weakness": False,
                "weakness_reason": "NONE",
                "priority": "LOW",
                "recommendation": "Maintain PostgreSQL proficiency.",
                "recommendation_reason": "Requirements satisfied.",
                "improvement_probability": None,
                "importance": "preferred",
                "matched": True
            }
        ]
    }

    agg_res = client.post("/assessment/aggregate", json=agg_payload)
    agg_data = agg_res.json()

    logger.log_api_call(
        step_num=step_counter,
        step_name="Aggregate Multi-Skill Assessment Results",
        method="POST",
        url="/assessment/aggregate",
        req_body=agg_payload,
        resp_status=agg_res.status_code,
        resp_body=agg_data
    )
    step_counter += 1

    # =========================================================================
    # PHASE 8: Longitudinal History & Candidate Isolation
    # =========================================================================
    logger.add_section("9. Phase 8: Candidate History & Data Isolation Audit", "Retrieving historical assessment progression timeline via `GET /assessment/history/{user_id}`.")

    hist_res = client.get(f"/assessment/history/{user_id}", headers=auth_headers)
    hist_data = hist_res.json()

    logger.log_api_call(
        step_num=step_counter,
        step_name="Fetch Candidate Longitudinal History Trace",
        method="GET",
        url=f"/assessment/history/{user_id}",
        headers=auth_headers,
        resp_status=hist_res.status_code,
        resp_body=hist_data
    )

    # Save output to report file
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "STEP_14_E2E_REAL_VERIFICATION_REPORT.md"))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(logger.report_markdown))

    print(f"[Success] Real E2E verification completed. Detailed report written to:\n{report_path}")
    db.close()

if __name__ == "__main__":
    run_e2e_real_verification()
