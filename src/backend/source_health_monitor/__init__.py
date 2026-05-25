"""
source_health_monitor — Source Health Monitor service (component C24).

Phase 2-C MVP: in-memory health state aggregation, threshold evaluation,
alert detection, and REST API for the 9 P1 federal data sources.

Public surface:
  SourceHealthMonitor  — stateless threshold evaluation engine
  HealthStore          — in-memory state + history aggregation
  AlertType            — alert classification enum
  AlertSeverity        — alert severity enum
  HealthAlert          — a single evaluated alert
"""
from .monitor import AlertSeverity, AlertType, HealthAlert, SourceHealthMonitor
from .store import HealthStore

__all__ = [
    "AlertSeverity",
    "AlertType",
    "HealthAlert",
    "SourceHealthMonitor",
    "HealthStore",
]
