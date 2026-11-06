#!/usr/bin/env python
"""
Migration Utility: Migrate Local CV Files to Private S3 Object Storage

Scans the database for CV records stored locally (file_path not starting with s3://),
uploads the file bytes to the configured private S3 bucket, and updates the database records.

Usage:
    python scripts/migrate_cvs_to_s3.py --dry-run
    python scripts/migrate_cvs_to_s3.py --run
    python scripts/migrate_cvs_to_s3.py --run --remove-local
"""

import os
import sys
import argparse
import logging
from typing import Tuple, Optional

# Ensure app root is on path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"), override=False)

from app.database import SessionLocal
from app.models import CV
from app.services.storage_service import S3StorageBackend, LocalStorageBackend

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cv_s3_migration")


def migrate_cvs(dry_run: bool = True, remove_local: bool = False, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Migrates local CV files to private S3 object storage.
    
    Returns (total_found, migrated_count, error_count).
    """
    db = SessionLocal()
    local_storage = LocalStorageBackend()
    s3_storage = S3StorageBackend()

    try:
        # Find CVs that are not already in S3
        query = db.query(CV)
        if user_id is not None:
            query = query.filter(CV.user_id == user_id)
        all_cvs = query.all()
        candidates = [c for c in all_cvs if c.file_path and not str(c.file_path).startswith("s3://")]

        total_found = len(candidates)
        logger.info(f"Discovered {total_found} local CV record(s) to inspect.")

        migrated_count = 0
        error_count = 0

        for cv in candidates:
            cv_id = cv.id
            user_id = cv.user_id
            local_path = cv.file_path
            filename = cv.file_name or f"cv_{cv_id}.pdf"

            # Check local file existence via LocalStorageBackend safe resolution
            safe_local_path = local_storage._resolve_safe_path(local_path)
            if not os.path.exists(safe_local_path):
                logger.warning(f"[CV #{cv_id}] Local file missing at {safe_local_path}. Skipping.")
                error_count += 1
                continue

            try:
                with open(safe_local_path, "rb") as f:
                    content = f.read()

                if not content:
                    logger.warning(f"[CV #{cv_id}] Empty file at {safe_local_path}. Skipping.")
                    error_count += 1
                    continue

                if dry_run:
                    logger.info(f"[DRY-RUN] Would upload CV #{cv_id} ({len(content)} bytes) to S3 bucket '{s3_storage.bucket_name}' for user {user_id}")
                    migrated_count += 1
                else:
                    storage_key, s3_access_path = s3_storage.save_file(
                        content=content,
                        original_filename=filename,
                        user_id=user_id
                    )
                    logger.info(f"[CV #{cv_id}] Uploaded to S3: {s3_access_path}")

                    # Update database record
                    cv.file_path = s3_access_path
                    db.commit()
                    migrated_count += 1

                    if remove_local:
                        try:
                            os.remove(safe_local_path)
                            logger.info(f"[CV #{cv_id}] Deleted local file {safe_local_path}")
                        except OSError as e:
                            logger.warning(f"[CV #{cv_id}] Could not delete local file: {e}")

            except Exception as e:
                logger.error(f"[CV #{cv_id}] Migration failed: {e}")
                if not dry_run:
                    db.rollback()
                error_count += 1

        mode_str = "DRY-RUN COMPLETE" if dry_run else "MIGRATION COMPLETE"
        logger.info(f"[{mode_str}] Discovered: {total_found}, Migrated: {migrated_count}, Errors: {error_count}")
        return total_found, migrated_count, error_count

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate local CV files to private S3 object storage.")
    parser.add_argument("--run", action="store_true", help="Execute actual S3 upload and database update (default is dry-run)")
    parser.add_argument("--remove-local", action="store_true", help="Remove local files after successful S3 upload (use with caution)")
    parser.add_argument("--user-id", type=int, default=None, help="Migrate CVs for a specific user ID only")

    args = parser.parse_args()
    dry_run = not args.run

    if dry_run:
        logger.info("Running in DRY-RUN mode. No changes will be made to database or files. Pass --run to execute.")
    else:
        logger.info("Executing LIVE migration to S3 object storage...")

    migrate_cvs(dry_run=dry_run, remove_local=args.remove_local, user_id=args.user_id)


if __name__ == "__main__":
    main()
