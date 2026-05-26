"""
0009_court_record_seeds.py

Phase 3-C: PACER + State Court Adapters -- seed source_health_records.

Inserts one row per Phase 3-C court record source into `source_health_records`
so C24 (Source Health Monitor) has rows to update on first check rather than
needing to INSERT on first contact.

Sources seeded:
    court_listener  -- CourtListener / RECAP Archive (federal, cursor pagination)
    pacer           -- PACER Case Locator, federal courts (page-number pagination)
    court_tx        -- Texas Courts Search (offset/limit pagination)
    court_fl        -- Florida eCourts (offset/limit pagination)
    court_ny        -- New York eCourts WebCivil (page-number pagination)

No schema changes -- table was created in 0001, roles/RLS already cover it (0003).
Source category for all 5 rows is 'court' (SourceCategory.COURT from schema v1).
"""
from __future__ import annotations

from alembic import op

revision: str = "0009"
down_revision: str = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('court_listener', 'CourtListener / RECAP Archive',        'court', 'unknown', NOW()),
            ('pacer',          'PACER Case Locator (Federal Courts)',   'court', 'unknown', NOW()),
            ('court_tx',       'Texas Courts Search',                   'court', 'unknown', NOW()),
            ('court_fl',       'Florida eCourts',                       'court', 'unknown', NOW()),
            ('court_ny',       'New York eCourts WebCivil',             'court', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_health_records
        WHERE source_id IN (
            'court_listener',
            'pacer',
            'court_tx',
            'court_fl',
            'court_ny'
        )
    """)
