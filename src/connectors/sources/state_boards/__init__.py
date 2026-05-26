"""
connectors.sources.state_boards -- P2 state medical licensing board adapters (Phase 3-A).

Builds on the C9 connector framework (connectors.base.SourceConnector). These adapters
cover the top-5-physician-population states: CA, NY, TX, FL, IL.

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing here
hits the network on import; tests drive every adapter with stubbed transports. Running
against a live state board endpoint is a deploy-time action behind that gate.

Source ID namespace: state_board_* to avoid collision with P1 federal IDs (F1-F4, I1-I2, A1-A2).

Phase 3-A state board batch:
    S1  CA Medical Board (DCA bulk CSV)         -- state_boards.ca_medical_board   (built, 3-A)
    S2  NY NYSED Office of Professions (SODA)   -- state_boards.ny_op_nysed        (built, 3-A)
    S3  Texas Medical Board (JSON lookup)        -- state_boards.tx_medical_board   (built, 3-A)
    S4  Florida DOH FDBPR (REST endpoint)        -- state_boards.fl_doh             (built, 3-A)
    S5  Illinois IDFPR (license API)             -- state_boards.il_idfpr           (built, 3-A)
"""
from .ca_medical_board import CaMedicalBoardConnector, ca_medical_board_config
from .fl_doh import FlDohConnector, fl_doh_config
from .il_idfpr import IlIdfprConnector, il_idfpr_config
from .ny_op_nysed import NyMedicalBoardConnector, ny_op_nysed_config
from .tx_medical_board import TxMedicalBoardConnector, tx_medical_board_config

__all__ = [
    "CaMedicalBoardConnector",
    "ca_medical_board_config",
    "NyMedicalBoardConnector",
    "ny_op_nysed_config",
    "TxMedicalBoardConnector",
    "tx_medical_board_config",
    "FlDohConnector",
    "fl_doh_config",
    "IlIdfprConnector",
    "il_idfpr_config",
]
