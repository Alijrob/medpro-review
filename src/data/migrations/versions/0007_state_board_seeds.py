"""
0007_state_board_seeds.py

Phase 3-A: State Board Adapters (Top 5 States) -- seed source_health_records.

Inserts one row per Phase 3-A state board source into `source_health_records`
so C24 (Source Health Monitor) has rows to update on first check rather than
needing to INSERT on first contact.

Sources seeded:
    state_board_ca  -- California Medical Board (BULK_DOWNLOAD CSV)
    state_board_ny  -- New York NYSED Office of Professions (REST_API SODA)
    state_board_tx  -- Texas Medical Board (REST_API paginated JSON)
    state_board_fl  -- Florida DOH FDBPR (REST_API paginated JSON)
    state_board_il  -- Illinois IDFPR (REST_API paginated JSON)

No schema changes -- table was created in 0001, roles/RLS already cover it (0003).
The phase-3 source IDs use the 'state_board_*' namespace to avoid collision with
phase-2 federal IDs (F1-F4, I1-I2, A1-A2).
"""
from __future__ import annotations

from alembic import op

revision: str = "0007"
down_revision: str = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('state_board_ca', 'California Medical Board',             'state_board', 'unknown', NOW()),
            ('state_board_ny', 'New York NYSED Office of Professions', 'state_board', 'unknown', NOW()),
            ('state_board_tx', 'Texas Medical Board',                  'state_board', 'unknown', NOW()),
            ('state_board_fl', 'Florida Department of Health FDBPR',   'state_board', 'unknown', NOW()),
            ('state_board_il', 'Illinois IDFPR',                       'state_board', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_health_records
        WHERE source_id IN (
            'state_board_ca',
            'state_board_ny',
            'state_board_tx',
            'state_board_fl',
            'state_board_il'
        )
    """)
