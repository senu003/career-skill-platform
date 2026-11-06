# Phase 3B: Private S3 Object Storage Migration & Operations Guide

## Overview

CareerSkill Platform Phase 3B introduces private object storage for all candidate CV documents. This replaces storing sensitive candidate PDF resumes on the application container's local disk with private, encrypted cloud object storage (AWS S3 or any S3-compatible service such as MinIO or Google Cloud Storage).

---

## 1. Storage Configuration & Credentials

All storage settings are configured via server-side environment variables (`backend/.env`). **Storage credentials are never exposed to the frontend, browser, or Git repository.**

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `STORAGE_BACKEND` | Optional | `local` | Set to `s3` for private object storage, or `local` for local filesystem development. |
| `S3_BUCKET_NAME` | S3 only | `career-skill-cv-uploads` | Name of the private S3 bucket. |
| `AWS_REGION` | S3 only | `us-east-1` | AWS region where the bucket resides. |
| `AWS_ACCESS_KEY_ID` | S3 only | *None* | AWS IAM access key ID with read/write permissions on the bucket. |
| `AWS_SECRET_ACCESS_KEY` | S3 only | *None* | AWS IAM secret access key. |
| `S3_ENDPOINT_URL` | Optional | *None* | Custom S3 endpoint URL for MinIO, LocalStack, or Cloudflare R2. |

---

## 2. Security & Access Control Architecture

1. **Private Access by Default**:
   - Every file uploaded to S3 is saved under a user-isolated namespace: `cvs/{user_id}/{uuid}.pdf`.
   - Files are stored with AES-256 server-side encryption (`ServerSideEncryption="AES256"`) and private access control (`ACL="private"`).
   - Public read access is strictly forbidden on the S3 bucket.

2. **Strict Backend Ownership Enforcement**:
   - The frontend never communicates directly with S3 using AWS access keys.
   - When a user views or downloads a CV, the backend enforces authorization before serving file bytes or generating a signed URL:
     - If the CV record does not exist: returns `404 Not Found`.
     - If the CV record belongs to a different candidate: returns `403 Forbidden` ("Not authorized to access this CV").
   - Short-lived presigned URLs (`GET /api/cv/{cv_id}/signed-url`) expire in 300 seconds (5 minutes), preventing link sharing or long-term credential leakage.

3. **Dual Resolution & Zero Downtime**:
   - The platform supports seamless backward compatibility:
     - New CVs uploaded with `STORAGE_BACKEND=s3` receive an `s3://` access path.
     - Historical CVs and past session reports created on local disk continue to be read from the local filesystem automatically.

---

## 3. How to Migrate Existing Local CVs to S3

If you are transitioning an existing deployment from local filesystem storage to S3, run the standalone migration utility:

### Step 1: Preview Migration (Dry-Run)
Inspect all local CV records without mutating the database or S3:
```bash
python backend/scripts/migrate_cvs_to_s3.py --dry-run
```

### Step 2: Execute Live Migration
Upload all existing local files to S3 and update the database records:
```bash
python backend/scripts/migrate_cvs_to_s3.py --run
```

### Step 3: Optional Cleanup
To remove the local copies once confirmed safe in S3:
```bash
python backend/scripts/migrate_cvs_to_s3.py --run --remove-local
```

---

## 4. Rollback and Retry Safety (Phase 3A Preservation)

- If a CV analysis fails due to an AI provider outage or database transaction error, the backend safely deletes **only the newly uploaded file** owned by that specific request via `storage.delete_file()`.
- Previously saved candidate CVs and historical analysis reports are never deleted or corrupted by a failed retry.

