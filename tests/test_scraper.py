"""
Unit tests for scraper.py parsing logic.
No network calls — all HTML comes from fixture files.
"""
import pytest
from scraper import (
    parse_downstream,
    parse_upstream,
    parse_event_log,
    parse_wan_info,
)


class TestParseDownstream:
    def test_channel_count(self, html_downstream):
        channels = parse_downstream(html_downstream)
        assert len(channels) == 7

    def test_first_channel_values(self, html_downstream):
        ch = parse_downstream(html_downstream)[0]
        assert ch.channel_id == 1
        assert ch.frequency_hz == 114_000_000
        assert abs(ch.power_dbmv - 2.5) < 0.01
        assert abs(ch.snr_db - 38.2) < 0.01
        assert ch.modulation == "QAM256"
        assert ch.lock_status == "Locked"
        assert ch.corrected == 1042
        assert ch.uncorrectables == 0

    def test_docsis31_ofdm_detection(self, html_downstream):
        channels = parse_downstream(html_downstream)
        ofdm_ch = next(c for c in channels if c.channel_id == 33)
        assert ofdm_ch.docsis_version == "3.1"

    def test_docsis30_scqam_detection(self, html_downstream):
        channels = parse_downstream(html_downstream)
        sc_qam_ch = next(c for c in channels if c.channel_id == 1)
        assert sc_qam_ch.docsis_version == "3.0"

    def test_degraded_channel_values(self, html_downstream):
        """Channel 5 has intentionally bad signal in the fixture."""
        channels = parse_downstream(html_downstream)
        bad = next(c for c in channels if c.channel_id == 5)
        assert bad.power_dbmv == pytest.approx(-8.2, abs=0.01)
        assert bad.snr_db == pytest.approx(29.1, abs=0.01)
        assert bad.uncorrectables == 623

    def test_empty_html_returns_empty_list(self):
        result = parse_downstream("<html><body></body></html>")
        assert result == []

    def test_malformed_value_handled(self):
        html = """
        <table><thead><tr>
          <th>Channel ID</th><th>Frequency (Hz)</th><th>Power Level (dBmV)</th>
          <th>RxMER (dB)</th><th>Modulation</th><th>Lock Status</th>
          <th>Corrected</th><th>Uncorrectables</th><th>Channel Type</th>
        </tr></thead><tbody>
          <tr><td>1</td><td>N/A</td><td>N/A</td><td>N/A</td>
              <td></td><td></td><td>0</td><td>0</td><td>SC-QAM</td></tr>
        </tbody></table>
        """
        channels = parse_downstream(html)
        assert len(channels) == 1
        assert channels[0].power_dbmv is None
        assert channels[0].snr_db is None
        assert channels[0].frequency_hz is None


class TestParseUpstream:
    def test_channel_count(self, html_upstream):
        channels = parse_upstream(html_upstream)
        assert len(channels) == 4

    def test_first_channel_values(self, html_upstream):
        ch = parse_upstream(html_upstream)[0]
        assert ch.channel_id == 1
        assert ch.frequency_hz == 27_200_000
        assert abs(ch.power_dbmv - 42.5) < 0.01
        assert ch.channel_type == "ATDMA"
        assert ch.t3_timeouts == 0
        assert ch.t4_timeouts == 0

    def test_t3_timeout_detected(self, html_upstream):
        channels = parse_upstream(html_upstream)
        ch2 = next(c for c in channels if c.channel_id == 2)
        assert ch2.t3_timeouts == 2
        assert ch2.t4_timeouts == 0

    def test_t4_timeout_detected(self, html_upstream):
        channels = parse_upstream(html_upstream)
        ch3 = next(c for c in channels if c.channel_id == 3)
        assert ch3.t4_timeouts == 1
        assert ch3.power_dbmv == pytest.approx(49.5, abs=0.01)  # over threshold

    def test_empty_html_returns_empty_list(self):
        result = parse_upstream("<html><body></body></html>")
        assert result == []


class TestParseEventLog:
    def test_log_count(self, html_event_log):
        logs = parse_event_log(html_event_log)
        assert len(logs) == 5

    def test_critical_severity_classified(self, html_event_log):
        logs = parse_event_log(html_event_log)
        crit = [l for l in logs if l.severity == "CRITICAL"]
        assert len(crit) == 1
        assert "T4" in crit[0].message

    def test_warning_severity_classified(self, html_event_log):
        logs = parse_event_log(html_event_log)
        warn = [l for l in logs if l.severity == "WARNING"]
        assert len(warn) == 1
        assert "T3" in warn[0].message

    def test_notice_entries_present(self, html_event_log):
        logs = parse_event_log(html_event_log)
        notices = [l for l in logs if l.severity == "NOTICE"]
        assert len(notices) == 3


class TestParseWanInfo:
    def test_ip_extracted(self, html_wan):
        info = parse_wan_info(html_wan)
        assert info["wan_ip"] == "82.132.45.67"

    def test_uptime_parsed_days_hours_minutes(self, html_wan):
        info = parse_wan_info(html_wan)
        # 2d 14:23:07 = 2*86400 + 14*3600 + 23*60 + 7 = 224587
        assert info["uptime_secs"] == 224587

    def test_empty_html_returns_nones(self):
        info = parse_wan_info("<html><body></body></html>")
        assert info["wan_ip"] is None
        assert info["uptime_secs"] is None
