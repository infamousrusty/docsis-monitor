from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    OK       = "ok"
    WARN     = "warn"
    CRITICAL = "critical"
    UNKNOWN  = "unknown"


class DownstreamChannel(BaseModel):
    channel_id: Optional[int] = None
    frequency_hz: Optional[int] = None
    power_dbmv: Optional[float] = None
    snr_db: Optional[float] = None
    modulation: Optional[str] = None
    lock_status: Optional[str] = None
    corrected: int = 0
    uncorrectables: int = 0
    docsis_version: str = "3.0"

    @property
    def power_status(self) -> Severity:
        if self.power_dbmv is None:
            return Severity.UNKNOWN
        from config import settings
        if settings.DS_POWER_MIN <= self.power_dbmv <= settings.DS_POWER_MAX:
            return Severity.OK
        return Severity.WARN

    @property
    def snr_status(self) -> Severity:
        if self.snr_db is None:
            return Severity.UNKNOWN
        from config import settings
        if self.snr_db >= settings.SNR_WARN_DB:
            return Severity.OK
        if self.snr_db >= settings.SNR_CRIT_DB:
            return Severity.WARN
        return Severity.CRITICAL

    @property
    def uncorrectable_status(self) -> Severity:
        from config import settings
        if self.uncorrectables >= settings.UNCORRECTABLE_CRIT:
            return Severity.CRITICAL
        if self.uncorrectables >= settings.UNCORRECTABLE_WARN:
            return Severity.WARN
        return Severity.OK


class UpstreamChannel(BaseModel):
    channel_id: Optional[int] = None
    frequency_hz: Optional[int] = None
    power_dbmv: Optional[float] = None
    channel_type: Optional[str] = None
    t1_timeouts: int = 0
    t2_timeouts: int = 0
    t3_timeouts: int = 0
    t4_timeouts: int = 0
    docsis_version: str = "3.0"

    @property
    def power_status(self) -> Severity:
        if self.power_dbmv is None:
            return Severity.UNKNOWN
        from config import settings
        if settings.US_POWER_MIN <= self.power_dbmv <= settings.US_POWER_MAX:
            return Severity.OK
        return Severity.WARN

    @property
    def timeout_severity(self) -> Severity:
        from config import settings
        if (self.t3_timeouts + self.t4_timeouts) >= settings.T3_T4_CRIT_COUNT:
            return Severity.CRITICAL
        return Severity.OK


class EventLogEntry(BaseModel):
    ts: str
    priority: Optional[int] = None
    severity: str = "NOTICE"
    message: str


class RouterSnapshot(BaseModel):
    polled_at: datetime
    router_up: bool
    wan_ip: Optional[str] = None
    uptime_secs: Optional[int] = None
    downstream: List[DownstreamChannel] = []
    upstream: List[UpstreamChannel] = []
    event_logs: List[EventLogEntry] = []
