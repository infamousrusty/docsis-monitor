"""
Unit tests for model threshold/severity logic.
"""
import pytest
from models import DownstreamChannel, UpstreamChannel, Severity


class TestDownstreamChannelSeverity:
    # SNR thresholds (warn=33, crit=30)
    def test_snr_ok(self):
        ch = DownstreamChannel(snr_db=38.0)
        assert ch.snr_status == Severity.OK

    def test_snr_warn_boundary(self):
        ch = DownstreamChannel(snr_db=32.9)
        assert ch.snr_status == Severity.WARN

    def test_snr_warn_exact_threshold(self):
        # 33.0 is the warn threshold — at exactly 33 it should be OK
        ch = DownstreamChannel(snr_db=33.0)
        assert ch.snr_status == Severity.OK

    def test_snr_critical(self):
        ch = DownstreamChannel(snr_db=29.9)
        assert ch.snr_status == Severity.CRITICAL

    def test_snr_none_returns_unknown(self):
        ch = DownstreamChannel(snr_db=None)
        assert ch.snr_status == Severity.UNKNOWN

    # DS power thresholds (-7 to +7 dBmV)
    def test_power_ok_positive(self):
        ch = DownstreamChannel(power_dbmv=3.0)
        assert ch.power_status == Severity.OK

    def test_power_ok_negative(self):
        ch = DownstreamChannel(power_dbmv=-5.0)
        assert ch.power_status == Severity.OK

    def test_power_warn_below_min(self):
        ch = DownstreamChannel(power_dbmv=-7.1)
        assert ch.power_status == Severity.WARN

    def test_power_warn_above_max(self):
        ch = DownstreamChannel(power_dbmv=7.5)
        assert ch.power_status == Severity.WARN

    def test_power_at_exact_min_boundary(self):
        ch = DownstreamChannel(power_dbmv=-7.0)
        assert ch.power_status == Severity.OK

    def test_power_at_exact_max_boundary(self):
        ch = DownstreamChannel(power_dbmv=7.0)
        assert ch.power_status == Severity.OK

    def test_power_none_returns_unknown(self):
        ch = DownstreamChannel(power_dbmv=None)
        assert ch.power_status == Severity.UNKNOWN

    # Uncorrectables (warn=100, crit=500)
    def test_uncorrectables_ok(self):
        ch = DownstreamChannel(uncorrectables=50)
        assert ch.uncorrectable_status == Severity.OK

    def test_uncorrectables_warn(self):
        ch = DownstreamChannel(uncorrectables=100)
        assert ch.uncorrectable_status == Severity.WARN

    def test_uncorrectables_critical(self):
        ch = DownstreamChannel(uncorrectables=500)
        assert ch.uncorrectable_status == Severity.CRITICAL


class TestUpstreamChannelSeverity:
    # US power (warn=outside 38–48.5)
    def test_us_power_ok(self):
        ch = UpstreamChannel(power_dbmv=43.0)
        assert ch.power_status == Severity.OK

    def test_us_power_warn_low(self):
        ch = UpstreamChannel(power_dbmv=37.0)
        assert ch.power_status == Severity.WARN

    def test_us_power_warn_high(self):
        ch = UpstreamChannel(power_dbmv=50.0)
        assert ch.power_status == Severity.WARN

    def test_us_power_none_unknown(self):
        ch = UpstreamChannel(power_dbmv=None)
        assert ch.power_status == Severity.UNKNOWN

    # T3/T4 timeouts
    def test_no_timeouts_ok(self):
        ch = UpstreamChannel(t3_timeouts=0, t4_timeouts=0)
        assert ch.timeout_severity == Severity.OK

    def test_t3_timeout_critical(self):
        ch = UpstreamChannel(t3_timeouts=1, t4_timeouts=0)
        assert ch.timeout_severity == Severity.CRITICAL

    def test_t4_timeout_critical(self):
        ch = UpstreamChannel(t3_timeouts=0, t4_timeouts=1)
        assert ch.timeout_severity == Severity.CRITICAL
