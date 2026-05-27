"""
0010_commercial_source_seeds.py

Phase 3-D: Commercial Data Adapters -- seed source_health_records.

Inserts one row per Phase 3-D commercial source into `source_health_records`
so C24 (Source Health Monitor) has rows to update on first check rather than
needing to INSERT on first contact.

Sources seeded:
    ribbon_health  -- Ribbon Health Provider Directory (T3, contract required)
    healthgrades   -- Healthgrades Provider Profiles (T4, license required)
    vitals         -- Vitals Provider Profiles / WebMD Health Corp. (T4, license required)

No schema changes -- table was created in 0001, roles/RLS already cover it (0003).
Source category for all 3 rows is 'commercial_directory' (SourceCategory.COMMERCIAL_DIRECTORY).

Note: these adapters require signed data license agreements before live ingest.
Status seeds as 'unknown' in alignment with all other pre-ingest adapter rows.
"""
from __future__ import annotations

from alembic import op

revision: str = "0010"
down_revision: str = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('ribbon_health', 'Ribbon Health Provider Directory',              'commercial_directory', 'unknown', NOW()),
            ('healthgrades',  'Healthgrades Provider Profiles',                'commercial_directory', 'unknown', NOW()),
            ('vitals',        'Vitals Provider Profiles (WebMD Health Corp.)', 'commercial_directory', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_health_records
        WHERE source_id IN (
            'ribbon_health',
            'healthgrades',
            'vitals'
        )
    """)
