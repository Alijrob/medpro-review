"""
0011_review_platform_source_seeds.py

Phase 3-E: Review Platform Adapters -- seed source_health_records.

Inserts one row per Phase 3-E review platform source into `source_health_records`
so C24 (Source Health Monitor) has rows to update on first check rather than
needing to INSERT on first contact.

Sources seeded:
    google_places  -- Google Places Provider Reviews (T2, paid Maps Platform API key)
    yelp           -- Yelp Fusion Provider Reviews (T2, Yelp Developer API key)

No schema changes -- table was created in 0001, roles/RLS already cover it (0003).
Source category for both rows is 'review_platform' (SourceCategory.REVIEW_PLATFORM).

Note: both adapters require API keys before live ingest and are additionally gated
on the Phase 0 FCRA determination. Status seeds as 'unknown' in alignment with all
other pre-ingest adapter rows.
"""
from __future__ import annotations

from alembic import op

revision: str = "0011"
down_revision: str = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('google_places', 'Google Places Provider Reviews', 'review_platform', 'unknown', NOW()),
            ('yelp',          'Yelp Fusion Provider Reviews',   'review_platform', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_health_records
        WHERE source_id IN (
            'google_places',
            'yelp'
        )
    """)
