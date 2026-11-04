# Release 1.0 Readiness Audit

**Audit date:** 2026-11-04  
**Repository:** `senu003/career-skill-platform`  
**Audit mode:** Read-only source/configuration review plus safe validation. No application source was modified.  
**Release conclusion:** **Not release-ready.** The shortest path is to fix the two P0/P1 security blockers, make the backend test/deployment path reproducible, and validate the primary CV-to-assessment journey against a real PostgreSQL environment.

## 1. Executive summary

The current repository is a substantial full-stack prototype rather than a verified Release 1.0. It contains a React/Vite SPA, FastAPI API, SQLAlchemy/Alembic schema, local/S3 storage abstraction, Gemini/Groq integrations, deterministic assessment logic, and scikit-learn artifacts. The main CV analysis and assessment journey is represented end-to-end in code, but several production-critical claims are not verified.

The two confirmed security blockers are:

1. `POST /auth/forgot-password` returns the raw reset token in `dev_reset_token` without a production gate ([backend/app/routers/auth.py](backend/app/routers/auth.py):312-349, `forgot_password`).
2. Docker Compose supplies a public fallback HS256 JWT secret ([docker-compose.yml](docker-compose.yml):43-44), allowing forged bearer tokens when deployment secrets are not overridden; token signing/verification is in [backend/app/auth_deps.py](backend/app/auth_deps.py):25-40.

The frontend build completed successfully. Lint completed with warnings. Backend pytest was **not run**: the checked-in backend virtual environment has no pytest, and the available tests perform destructive database cleanup in setup/teardown, which is outside this audit's allowed operations. The README's “50 Suites Passing” badge is therefore not an independently verified current result.

Other release blockers are operational: there is no refresh-token lifecycle, logout is audit-only and does not revoke tokens, database transactions are split across multiple commits in CV analysis, the local backend dependency environment is incomplete, and Docker Compose has no frontend health check or production secret enforcement.

## 2. Current architecture overview

### Directory structure

- `frontend/src/`: React pages, contexts, components, API wrapper, and interview-prep screens.
- `backend/app/routers/`: FastAPI routers for authentication, CV/analysis, assessment, requirements, ML, aggregation, and users.
- `backend/app/services/`: CV/PDF/storage, LLM requirement extraction, matching/scoring, assessment, recommendation, longitudinal, and interview-prep services.
- `backend/app/models.py`: SQLAlchemy models for users, CVs, jobs, analyses, assessment attempts/answers/questions, reset tokens, and audit logs.
- `backend/alembic/`: two migrations plus migration configuration.
- `backend/app/ml/`: dataset generation, feature engineering, training/evaluation scripts, persisted joblib models, and predictors.
- `backend/tests/`: 50 Python test modules covering security, CV processing, migrations, assessment, ML, and services.
- `.github/workflows/ci.yml`: backend pytest, frontend build, and Docker image build jobs.
- `docker-compose.yml`: PostgreSQL, Redis, backend, and Nginx frontend services.
- `uploads/`, `backend/models/`, `backend/data/`, and `eval/`: local files, generated datasets, model artifacts, and evaluation data.

### Architectural conventions

The intended layering (router → service → SQLAlchemy model/provider) is generally present. It is not consistent:

- Legacy `/users` and `/login` routes remain alongside the newer `/auth/*` routes ([backend/app/routers/users.py](backend/app/routers/users.py):17-79).
- [backend/app/routers/cv.py](backend/app/routers/cv.py) contains orchestration, persistence, file cleanup, response shaping, and repeated historical-session reconstruction.
- [backend/app/services/requirement_service.py](backend/app/services/requirement_service.py) constructs clients at import time, owns provider selection, caching, retries, parsing, and HTTP exception translation.
- [backend/app/services/assessment_service.py](backend/app/services/assessment_service.py) mixes question selection, progression rules, persistence, and scoring.
- The repository has duplicated/legacy model concepts (`Question`/`Answer`/`Assessment` and `AssessmentQuestion`/`AssessmentAnswer`/`AssessmentAttempt`); the active paths use the latter.

The working tree was already dirty at audit start: many tracked files were modified, two old files were deleted, and several new files were untracked. Findings describe the current working tree, not the last commit. No unrelated changes were reverted.

## 3. Feature completeness matrix

| Journey | Status | Frontend evidence | Backend/data evidence | Release note |
|---|---|---|---|---|
| Registration/password login | Partially implemented | [frontend/src/api.js](frontend/src/api.js):35-80; [frontend/src/pages/LoginPage.jsx](frontend/src/pages/LoginPage.jsx) | `/auth/register`, `/auth/login` in [backend/app/routers/auth.py](backend/app/routers/auth.py):141-208; legacy `/users`, `/login` in [backend/app/routers/users.py](backend/app/routers/users.py):27-79 | Two auth surfaces create compatibility and policy drift. |
| Google OAuth/SSO | Implemented in code, unverified operationally | [frontend/src/pages/LoginPage.jsx](frontend/src/pages/LoginPage.jsx) and `loginWithGoogle` in [frontend/src/api.js](frontend/src/api.js):82-101 | Server verification in [backend/app/services/google_auth_service.py](backend/app/services/google_auth_service.py); account linking in [backend/app/routers/auth.py](backend/app/routers/auth.py):234-298 | Requires configured Google client ID and real provider test. |
| Access/refresh lifecycle | Partially implemented | Session storage access token in [frontend/src/context/AuthContext.jsx](frontend/src/context/AuthContext.jsx):26-116 | HS256 access token only in [backend/app/auth_deps.py](backend/app/auth_deps.py):25-40 | No refresh token, rotation, reuse detection, or server revocation. |
| CV upload/parsing | Implemented with limitations | Upload flows in [frontend/src/pages/DashboardPage.jsx](frontend/src/pages/DashboardPage.jsx):213-226 and [frontend/src/pages/HistoryPage.jsx](frontend/src/pages/HistoryPage.jsx):102-126 | Size/type/signature checks in [backend/app/services/cv_service.py](backend/app/services/cv_service.py):34-119; parsing in [backend/app/services/pdf_service.py](backend/app/services/pdf_service.py) | PDF-only; parser reports `pages: 1` regardless of actual page count. |
| CV analysis/job matching | Partially implemented | Dashboard submits requirements then CV in [frontend/src/pages/DashboardPage.jsx](frontend/src/pages/DashboardPage.jsx):198-237 | `/requirements/analyze` and `/cv/analyze`; persistence in [backend/app/routers/cv.py](backend/app/routers/cv.py):293-459 | LLM dependency, cache behavior, and multi-commit persistence need production validation. |
| Skill gap identification | Implemented in code, unverified | Results and dashboard render gap fields in [frontend/src/pages/ResultsPage.jsx](frontend/src/pages/ResultsPage.jsx) | `combine_cv_and_assessment` and scoring services | Output is dependent on LLM extraction and deterministic post-processing. |
| Skill assessment | Implemented for a fixed skill bank | [frontend/src/pages/AssessmentPage.jsx](frontend/src/pages/AssessmentPage.jsx):82-204 | `/assessment/start`, `/answer`, completion in [backend/app/routers/assessment.py](backend/app/routers/assessment.py):45-79, 257-268 | Supported skills are fixed to six names; question seeding must exist. |
| Adaptive progression | Partially implemented | Next-question transition in [frontend/src/pages/AssessmentPage.jsx](frontend/src/pages/AssessmentPage.jsx):157-204 | Progression in [backend/app/services/assessment_service.py](backend/app/services/assessment_service.py):140-224 | Uses a fixed five questions per level and random selection; concurrency/idempotency is not evidenced. |
| History/comparisons | Implemented in code, unverified | [frontend/src/pages/HistoryPage.jsx](frontend/src/pages/HistoryPage.jsx), [frontend/src/pages/ResultsPage.jsx](frontend/src/pages/ResultsPage.jsx) | `/cv/sessions`, `/assessment/history/me` | Historical CV session reconstruction performs repeated queries and depends on files remaining on disk. |
| Career readiness | Partially implemented | [frontend/src/pages/FinalResultPage.jsx](frontend/src/pages/FinalResultPage.jsx):151-224 | Aggregation route and rule-based predictor in [backend/app/ml/predict_readiness.py](backend/app/ml/predict_readiness.py) | Primary verdict is deterministic; persisted ML model is a challenger, not the source of truth. |
| AI recommendations | Partially implemented | Recommendation rendering in [frontend/src/pages/ResultsPage.jsx](frontend/src/pages/ResultsPage.jsx) | Gemini/Groq code in [backend/app/services/requirement_service.py](backend/app/services/requirement_service.py); recommendation services | Response validation and prompt-injection defenses are not demonstrated. |
| Profile/account management | Partially implemented | Profile hydration in [frontend/src/App.jsx](frontend/src/App.jsx):18-37; logout in [frontend/src/components/Navbar.jsx](frontend/src/components/Navbar.jsx):24-37 | `/auth/me`, change/reset password in [backend/app/routers/auth.py](backend/app/routers/auth.py):300-431 | No profile edit/delete UI; logout does not revoke existing JWTs. |

## 4. Confirmed bugs

### BUG-001 — Reset endpoint exposes account takeover token

- **Severity/Priority:** Critical / P0
- **Category:** Authentication
- **Status:** Confirmed
- **Files/symbols:** [backend/app/routers/auth.py](backend/app/routers/auth.py):312-349, `forgot_password`; `reset_password` at 356-392.
- **Evidence:** The unauthenticated endpoint generates a valid raw token and returns it as `dev_reset_token`; the only control is a comment saying it should be removed in production. The application has no environment check around this response.
- **Impact:** Anyone who knows a registered email can obtain a reset token and change that account's password.
- **Minimal fix:** Never return raw reset tokens from a deployed API. Deliver them through a trusted email channel; if a local development mode is retained, require an explicit non-production setting and fail closed otherwise.
- **Blocks Release 1.0:** Yes.

### BUG-002 — Docker deployment has a forgeable default JWT key

- **Severity/Priority:** Critical / P0
- **Category:** Deployment/authentication
- **Status:** Confirmed when `JWT_SECRET` is not overridden
- **Files/symbols:** [docker-compose.yml](docker-compose.yml):43-44; [backend/app/auth_deps.py](backend/app/auth_deps.py):25-40, `create_access_token`, `get_current_user`.
- **Evidence:** Compose injects a fixed fallback secret; all bearer tokens use HS256 with that value.
- **Impact:** An attacker can forge a token with an arbitrary `sub` and access protected records as another user.
- **Minimal fix:** Remove the fallback, require a strong injected secret, fail startup when it is absent/weak, and rotate any deployment that used the fallback.
- **Blocks Release 1.0:** Yes.

### BUG-003 — CV analysis is not atomic

- **Severity/Priority:** High / P1
- **Category:** Data integrity
- **Status:** Confirmed
- **Files/symbols:** [backend/app/routers/cv.py](backend/app/routers/cv.py):389-445, `analyze_cv`.
- **Evidence:** The job is committed before the analysis is created and committed. If the second commit or later response construction fails, an orphan job remains. LLM analysis is performed before the job/analysis transaction and can fail after a CV file has been persisted.
- **Impact:** Partial sessions and orphaned records/files; retries can create duplicate jobs and analyses.
- **Minimal fix:** Use one explicit transaction for related rows, or add compensating cleanup and idempotency around the analysis request.
- **Blocks Release 1.0:** Yes for production data reliability.

### BUG-004 — PDF metadata reports one page for every document

- **Severity/Priority:** Medium / P2
- **Category:** Functional correctness
- **Status:** Confirmed
- **Files/symbols:** [backend/app/services/pdf_service.py](backend/app/services/pdf_service.py), `extract_pdf_text`.
- **Evidence:** The returned dictionary hard-codes `"pages": 1` after extracting all pages.
- **Impact:** UI and downstream telemetry misrepresent multi-page CVs.
- **Minimal fix:** Return the page count from the successful parser (and from OCR fallback where available).
- **Blocks Release 1.0:** No, unless page count is part of the demo claim.

### BUG-005 — Deactivated users retain access through existing JWTs

- **Severity/Priority:** High / P1
- **Category:** Authorization
- **Status:** Confirmed
- **Files/symbols:** [backend/app/auth_deps.py](backend/app/auth_deps.py):36-48, `get_current_user`; [backend/app/routers/auth.py](backend/app/routers/auth.py):184-207, login.
- **Evidence:** Login checks `user.is_active`, but `get_current_user` only decodes the token and fetches the user; it does not reject inactive users.
- **Impact:** Deactivation does not terminate already-issued 24-hour access tokens.
- **Minimal fix:** Enforce `is_active` in the required current-user dependency and introduce server-side revocation/versioning if immediate invalidation is required.
- **Blocks Release 1.0:** Yes if account deactivation is supported.

## 5. Security findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🔴 CRITICAL | backend/app/routers/auth.py | 312-349 | Password-reset endpoint returns the raw reset token to an unauthenticated caller | 10/10 |
| 2 | 🔴 CRITICAL | docker-compose.yml; backend/app/auth_deps.py | 43-44; 25-40 | Public fallback HS256 JWT secret permits forged bearer tokens when not overridden | 10/10 |
| 3 | 🟠 HIGH | backend/app/auth_deps.py | 36-48 | Existing tokens are accepted for inactive users because current-user lookup omits `is_active` enforcement | 9/10 |
| 4 | 🟠 HIGH | backend/app/routers/auth.py | 300-309 | Logout records an event but does not revoke the bearer token; token remains usable until expiry | 9/10 |
| 5 | 🟡 MEDIUM | backend/app/services/requirement_service.py | 119-121 | Groq HTTP client disables TLS certificate verification with `verify=False` | 9/10 |
| 6 | 🟡 MEDIUM | backend/app/rate_limiter.py | 39-58 | Rate limiting trusts client-supplied `X-Forwarded-For`/`X-Real-IP` without a trusted-proxy boundary | 8/10 |
| 7 | 🟡 MEDIUM | backend/app/services/requirement_service.py | 37-69, 420-568 | Uploaded CV/JD text is inserted into LLM prompts without an explicit prompt-injection boundary or output provenance policy | 8/10 |
| 8 | ⚪ LOW | backend/app/main.py | 77-87 | CORS allows all methods and headers for configured origins; safe only if origins remain tightly controlled | 8/10 |

Items 1 and 2 are the security-review-confirmed release blockers. Items 3-8 are direct source observations requiring hardening or deployment verification; they should not be represented as already mitigated.

Positive evidence: bcrypt is used for passwords, Google ID tokens are verified server-side with an audience, upload size and PDF signature checks exist, ownership checks are present on CV/session/assessment paths, and SQLAlchemy parameterization is used rather than string-built SQL in the inspected application paths.

Refresh rotation, token reuse detection, CSRF protections, email delivery, secret rotation, production TLS termination, dependency scanning, and a complete account deletion flow are not demonstrated.

## 6. Frontend architecture and functionality

- Routing is centralized in [frontend/src/App.jsx](frontend/src/App.jsx):39-112 with `PrivateRoute`; the protected-route pattern is clear, but `/results` redirects to the interview-prep hub rather than a result page, which is confusing and should be confirmed against intended UX.
- State is split between `AuthContext` and `AssessmentContext`. Auth state is stored in `sessionStorage`; analysis data is also stored client-side. There is no refresh flow, cross-tab token synchronization, or server-backed draft recovery.
- [frontend/src/api.js](frontend/src/api.js) centralizes authenticated fetches, but login/register/Google/demo/reset calls duplicate response parsing and do not share the auth-error handling path.
- Loading/error states exist on major pages, but several effects suppress errors or use `console.warn`; `ProfileHydrator` intentionally ignores failures ([frontend/src/App.jsx](frontend/src/App.jsx):29-34).
- Form validation is mostly delegated to backend schemas. The frontend has password-strength UI, but the legacy `/users` schema has no equivalent password validation.
- `npm run lint` passed with warnings, including missing hook dependencies and synchronous state updates in effects. These are not necessarily runtime failures but should be resolved before claiming a clean release.
- `npm run build` passed using the current frontend dependencies and produced a production bundle. No browser-level smoke test was run.
- Accessibility and responsiveness were not fully verified. Source inspection shows standard buttons/forms but no automated accessibility suite or documented keyboard/screen-reader evidence.

## 7. Backend architecture and functionality

- FastAPI startup and middleware are in [backend/app/main.py](backend/app/main.py). Runtime DDL is disabled by default, while Compose runs migrations before Uvicorn; this is the correct direction, but the two modes remain operationally divergent.
- Authentication has both modern and legacy routers. The modern routes issue user profiles; the legacy routes return only tokens and use weaker validation. This duplication increases maintenance and policy drift.
- Ownership checks are generally present: CV sessions filter by `current_user.id`, assessment attempts compare `attempt.user_id`, and `cv_id` ownership is checked in `analyze_cv`.
- Optional guest assessment starts are allowed, while all attempt read/answer/complete paths require authentication. The guest record is consequently not recoverable by the guest, which is a functional inconsistency.
- Error handling avoids returning stack traces in the global handler, but provider exceptions are sometimes converted into detailed 502 messages and some service failures are silently swallowed (for example historical CV extraction).
- `get_past_analysis_sessions` performs per-analysis job/CV queries and reconstructs matching data in Python, creating an N+1 pattern for history.
- Provider clients and model loading occur at import/constructor time. Startup can fail on missing configuration, and model loading/training fallback can be expensive or nondeterministic for an API worker.

## 8. Database and data integrity

- Alembic has an initial schema and a follow-up question-review migration. The migrations are idempotent by checking table/column existence, but they do not comprehensively add indexes, unique constraints, or foreign-key cascade policies for all relationships.
- `User.email` is unique; OAuth identity (`oauth_provider`, `oauth_id`) is not uniquely constrained. Concurrent Google sign-ins can therefore race into duplicate OAuth identities.
- CV, Job, Analysis, and assessment relationships are mostly foreign-keyed, but several foreign keys lack `ondelete` behavior. Orphan prevention is therefore dependent on application code.
- The model file includes legacy and active assessment table families. This is a schema maintenance risk and makes migration/application parity harder to reason about.
- `SecurityAuditLog` is described as immutable but has no database trigger/permission boundary enforcing immutability.
- Assessment answer uniqueness/idempotency and concurrent submission protection were not evidenced in the inspected model/migration sections. Duplicate answer submissions can affect progression unless enforced by service logic.
- The migration runner waits for PostgreSQL and runs `upgrade head`, then seeds questions. It logs seed failures as non-critical; a deployment can therefore become “healthy” with an empty assessment bank.
- No production backup, restore, retention, or migration rollback procedure is documented.

## 9. AI/ML reliability

- Requirement extraction and CV evaluation are LLM-generated, cached on local disk using a hash, and retried. The cache is process/filesystem-local and has no eviction, tenant namespace, encryption, or shared-storage strategy.
- The Groq path explicitly disables TLS verification and performs a provider model-list request on each call; this adds latency and weakens transport security.
- LLM output is JSON-parsed and levels are normalized, but the inspected path does not establish a strict Pydantic response schema for every field, bounded list size, skill-name allowlist, or evidence length.
- CV and job text are untrusted prompt input. The prompt says not to invent skills but does not isolate instructions from document content, so prompt injection and contaminated recommendations remain possible.
- [backend/app/ml/predict_weakness.py](backend/app/ml/predict_weakness.py) and [backend/app/ml/predict_readiness.py](backend/app/ml/predict_readiness.py) use persisted joblib models when available and deterministic fallbacks when not. The readiness predictor explicitly makes rules primary and ML a challenger.
- Training/evaluation scripts and README identify synthetic data. Reported metrics therefore demonstrate consistency with generated labels, not real-world hiring or candidate readiness validity. No real, independently labeled holdout set was found in the inspected structure.
- Feature preprocessing and model artifact compatibility are not enforced by a model-version/schema contract. A stale or incompatible joblib file can fall back silently or produce a logged error.
- Recommendations should be presented as guidance, not objective employability decisions. The UI currently uses strong readiness labels such as “Interview Ready”; limitations and confidence provenance should be visible in the release demo.

## 10. Testing and deployment findings

### Tests actually run

- Frontend `npm run lint`: completed with warnings listed above.
- Frontend `npm run build`: **passed**; Vite transformed 1,846 modules and emitted a production bundle.
- Backend pytest: **not run**. The checked backend virtualenv lacks pytest. The available test modules also contain destructive database cleanup statements, so they were not run against the current database under the audit rule prohibiting destructive DB operations.
- No Docker build, Compose startup, live API smoke test, migration upgrade, provider call, or browser smoke test was run.

### CI/CD

- CI installs backend requirements, runs `pytest`, builds the frontend, and builds Docker images ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
- CI has no dependency vulnerability scan, migration smoke test, API integration test, frontend lint step, or deployment health check.
- The backend test job does not define Redis, Google client ID, Groq settings, upload directory, or all optional provider configuration. Tests that rely on those services may not represent production.
- The frontend Dockerfile uses `npm install` rather than `npm ci`; reproducibility is weaker than the CI job, which uses `npm ci`.
- Docker Compose exposes Redis directly on host port 6379 and uses development fallbacks for database credentials and JWT signing. This is unsuitable as a production baseline.
- Backend health only returns `{"status":"ok"}` and does not verify database, Redis, question-bank, storage, or provider readiness.
- Uploaded CV storage defaults to a local volume. This is acceptable for a single-host demo but not a durable multi-instance deployment without backup and access controls.
- README setup instructions and reported metrics are broader than the evidence actually verified in this audit; the passing badge should not be treated as current evidence.

## 11. Missing functionality

The following are missing or not evidenced and should not be presented as complete Release 1.0 capabilities:

1. Secure production password-reset delivery and reset-token non-disclosure.
2. Refresh tokens, rotation, reuse detection, and server-side revocation.
3. Immediate enforcement of account deactivation for already-issued tokens.
4. Profile editing, account deletion, and data export/retention behavior.
5. Transactional/idempotent CV analysis persistence.
6. Durable shared LLM cache and bounded cache retention.
7. Strict LLM response schema validation and prompt-injection handling.
8. Real labeled ML evaluation and documented model/version provenance.
9. Database backup/restore and migration rollback runbook.
10. Production health/readiness checks and error reporting.
11. Verified browser-level demo and API integration run against PostgreSQL/Redis.
12. A reproducible backend test environment that can run safely in CI and locally.

## 12. Release 1.0 definition

### Include in Release 1.0

- Email/password registration and login through one canonical route.
- Optional Google sign-in only if real client configuration and end-to-end verification are available.
- PDF CV upload with size/type/signature validation and text extraction.
- Job-description requirement extraction with clearly labeled AI assistance and fallback/error states.
- CV-to-job skill comparison with persisted user-owned history.
- Fixed-bank adaptive assessment for the currently supported six skills.
- Assessment result, review, history, and rule-based recommendations.
- Docker Compose deployment for a single host with PostgreSQL, Redis, backend, and frontend, provided secrets and readiness checks are fixed.

### Postpone or explicitly label as experimental

- ML readiness forecasting as a production decision-maker; keep it as an offline/challenger experiment backed by synthetic-data limitations.
- Longitudinal improvement claims until real repeated-user data and evaluation exist.
- S3 mode until it is dependency-tested and ownership/access behavior is verified.
- Password reset until a real email provider and secure token delivery exist.
- Guest assessments unless a recoverable guest-session design is implemented.

### Successful end-to-end demo

1. Start the documented stack from a clean checkout with explicit secrets.
2. Register or Google-login a test user.
3. Upload a multi-page PDF and show accurate page count and parse quality.
4. Submit a job description, inspect extracted requirements, and show a persisted analysis.
5. Start an assessment for a supported skill, answer through progression, complete it, and display the result/review.
6. Reopen history as the same user and verify that another user cannot access the session, CV, or attempt.
7. Restart the stack and confirm migrations, question seeding, and persisted history remain usable.

## 13. Prioritized remediation plan

| Priority | Work | Evidence of completion | Release impact |
|---|---|---|---|
| P0 | Remove reset-token response and add trusted email delivery or disable reset in production | Integration test proves token is never in JSON; reset flow uses out-of-band delivery | Security blocker |
| P0 | Remove Compose JWT fallback; require strong secret and rotate exposed/default deployment secrets | Clean deployment fails without secret and succeeds with injected secret; forged-token test fails | Security blocker |
| P1 | Enforce inactive-user rejection and choose a revocation strategy; make logout semantics honest | Auth tests cover deactivation, logout, expiry, and revoked tokens | Security/reliability blocker |
| P1 | Make CV analysis persistence atomic/idempotent and clean up failed files/jobs | Failure-injection test leaves no orphan records/files; retry does not duplicate sessions | Core workflow blocker |
| P1 | Establish safe PostgreSQL/Redis integration test environment and run backend suite | CI and local clean checkout run tests without destructive shared DB assumptions | Verification blocker |
| P1 | Add production readiness checks, secret/config validation, and deployment smoke test | Health/readiness reports DB/Redis/question-bank/storage state; Compose smoke test passes | Deployment blocker |
| P2 | Remove legacy auth route duplication or document a compatibility boundary | One canonical auth policy and route contract | Maintainability |
| P2 | Fix page-count reporting, history N+1 queries, answer idempotency, and missing indexes/constraints | Targeted regression/performance/integrity tests | Reliability |
| P2 | Add strict LLM schemas, bounded inputs/outputs, prompt-injection handling, timeouts, and safe TLS | Provider contract tests and failure-mode tests | AI reliability |
| P2 | Add real frontend smoke/accessibility tests and resolve lint warnings | CI includes lint plus critical route/form tests | UX confidence |
| P3 | Improve model provenance, real-data evaluation, cache lifecycle, account deletion/export, and operational observability | Documented metrics and runbooks | Post-release quality |

## Final release decision

**Do not publish this repository as a completed Release 1.0 or claim production security/testing readiness yet.** It is suitable for an internship portfolio as an actively developed full-stack prototype if the README is honest about synthetic ML data, limited supported skills, local/single-host storage, and unverified provider/deployment paths. After P0/P1 remediation and a clean, non-destructive integration run, it can credibly be presented as a reproducible Release 1.0 demo.
