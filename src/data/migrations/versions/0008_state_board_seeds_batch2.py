"""
0008_state_board_seeds_batch2.py

Phase 3-B: State Board Adapters (Next 5 States) -- seed source_health_records.

Inserts one row per Phase 3-B state board source into `source_health_records`
so C24 (Source Health Monitor) has rows to update on first check rather than
needing to INSERT on first contact.

Sources seeded:
    state_board_ga  -- Georgia Composite Medical Board (REST_API SODA)
    state_board_pa  -- Pennsylvania State Medical Board (REST_API SODA)
    state_board_oh  -- Ohio State Medical Board (REST_API offset/limit)
    state_board_mi  -- Michigan LARA Bureau of Professional Licensing (REST_API SODA)
    state_board_nc  -- North Carolina Medical Board (REST_API page-number)

No schema changes -- table was created in 0001, roles/RLS already cover it (0003).
Continues the 'state_board_*' source ID namespace established in 0007.
"""
from __future__ import annotations

from alembic import op

revision: str = "0008"
down_revision: str = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('state_board_ga', 'Georgia Composite Medical Board',              'state_board', 'unknown', NOW()),
            ('state_board_pa', 'Pennsylvania State Medical Board',             'state_board', 'unknown', NOW()),
            ('state_board_oh', 'Ohio State Medical Board',                     'state_board', 'unknown', NOW()),
            ('state_board_mi', 'Michigan LARA Bureau of Professional Licensing','state_board', 'unknown', NOW()),
            ('state_board_nc', 'North Carolina Medical Board',                 'state_board', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_health_records
        WHERE source_id IN (
            'state_board_ga',
            'state_board_pa',
            'state_board_oh',
            'state_board_mi',
            'state_board_nc'
        )
    """)
