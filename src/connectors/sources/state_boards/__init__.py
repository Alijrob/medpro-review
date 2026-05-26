"""
connectors.sources.state_boards -- P2 state medical licensing board adapters
(Phase 3-A + Phase 3-B).

Builds on the C9 connector framework (connectors.base.SourceConnector). These
adapters cover the top-10-physician-population states (by licensed physician
count from AMA/FSMB data):

  Phase 3-A (built): CA, NY, TX, FL, IL
  Phase 3-B (built): GA, PA, OH, MI, NC

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination.
Nothing here hits the network on import; tests drive every adapter with
stubbed transports. Running against a live state board endpoint is a
deploy-time action behind that gate.

Source ID namespace: state_board_* to avoid collision with P1 federal IDs
(F1-F4, I1-I2, A1-A2).

Phase 3-A state board batch:
    S1  CA Medical Board (DCA bulk CSV)          -- state_boards.ca_medical_board          (built, 3-A)
    S2  NY NYSED Office of Professions (SODA)    -- state_boards.ny_op_nysed               (built, 3-A)
    S3  Texas Medical Board (JSON lookup)         -- state_boards.tx_medical_board          (built, 3-A)
    S4  Florida DOH FDBPR (REST endpoint)         -- state_boards.fl_doh                   (built, 3-A)
    S5  Illinois IDFPR (license API)              -- state_boards.il_idfpr                 (built, 3-A)

Phase 3-B state board batch:
    S6  GA Composite Medical Board (SODA)         -- state_boards.ga_composite_medical_board (built, 3-B)
    S7  Pennsylvania State Medical Board (SODA)   -- state_boards.pa_medical_board           (built, 3-B)
    S8  Ohio State Medical Board (REST offset)    -- state_boards.oh_state_medical_board     (built, 3-B)
    S9  Michigan LARA BPL (SODA)                  -- state_boards.mi_lara                    (built, 3-B)
    S10 North Carolina Medical Board (JSON)       -- state_boards.nc_medical_board           (built, 3-B)
"""
# Phase 3-A
from .ca_medical_board import CaMedicalBoardConnector, ca_medical_board_config
from .fl_doh import FlDohConnector, fl_doh_config
from .il_idfpr import IlIdfprConnector, il_idfpr_config
from .ny_op_nysed import NyMedicalBoardConnector, ny_op_nysed_config
from .tx_medical_board import TxMedicalBoardConnector, tx_medical_board_config

# Phase 3-B
from .ga_composite_medical_board import (
    GaCompositeMedicalBoardConnector,
    ga_composite_medical_board_config,
)
from .mi_lara import MiLaraConnector, mi_lara_config
from .nc_medical_board import NcMedicalBoardConnector, nc_medical_board_config
from .oh_state_medical_board import OhStateMedicalBoardConnector, oh_state_medical_board_config
from .pa_medical_board import PaMedicalBoardConnector, pa_medical_board_config

__all__ = [
    # Phase 3-A
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
    # Phase 3-B
    "GaCompositeMedicalBoardConnector",
    "ga_composite_medical_board_config",
    "PaMedicalBoardConnector",
    "pa_medical_board_config",
    "OhStateMedicalBoardConnector",
    "oh_state_medical_board_config",
    "MiLaraConnector",
    "mi_lara_config",
    "NcMedicalBoardConnector",
    "nc_medical_board_config",
]
