import subprocess
from unittest.mock import patch, MagicMock
import pytest
from monitor import _build_ping_cmd, _build_arp_cmd, ping_host, get_mac, scan_host


# --- _build_ping_cmd ---

def test_ping_cmd_macos():
    with patch('monitor._SYSTEM', 'Darwin'):
        cmd = _build_ping_cmd('10.0.0.1')
    assert cmd == ['ping', '-c', '1', '-W', '1000', '10.0.0.1']


def test_ping_cmd_linux():
    with patch('monitor._SYSTEM', 'Linux'):
        cmd = _build_ping_cmd('10.0.0.1')
    assert cmd == ['ping', '-c', '1', '-W', '1', '10.0.0.1']


def test_ping_cmd_windows():
    with patch('monitor._SYSTEM', 'Windows'):
        cmd = _build_ping_cmd('10.0.0.1')
    assert cmd == ['ping', '-n', '1', '-w', '1000', '10.0.0.1']


# --- _build_arp_cmd ---

def test_arp_cmd_macos():
    with patch('monitor._SYSTEM', 'Darwin'):
        cmd = _build_arp_cmd('10.0.0.1')
    assert cmd == ['arp', '10.0.0.1']


def test_arp_cmd_linux():
    with patch('monitor._SYSTEM', 'Linux'):
        cmd = _build_arp_cmd('10.0.0.1')
    assert cmd == ['arp', '-n', '10.0.0.1']


def test_arp_cmd_windows():
    with patch('monitor._SYSTEM', 'Windows'):
        cmd = _build_arp_cmd('10.0.0.1')
    assert cmd == ['arp', '-a', '10.0.0.1']


# --- ping_host ---

def test_ping_host_alive():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch('monitor.subprocess.run', return_value=mock_result) as mock_run:
        result = ping_host('10.0.0.1')
    assert result is True
    mock_run.assert_called_once()


def test_ping_host_dead():
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch('monitor.subprocess.run', return_value=mock_result):
        result = ping_host('10.0.0.1')
    assert result is False


def test_ping_host_subprocess_error():
    with patch('monitor.subprocess.run', side_effect=OSError("ping not found")):
        result = ping_host('10.0.0.1')
    assert result is False


# --- get_mac ---

def test_get_mac_found():
    mock_result = MagicMock()
    mock_result.stdout = "? (10.0.0.1) at aa:bb:cc:dd:ee:ff on en0"
    with patch('monitor.subprocess.run', return_value=mock_result):
        mac = get_mac('10.0.0.1')
    assert mac == 'aa:bb:cc:dd:ee:ff'


def test_get_mac_windows_format():
    mock_result = MagicMock()
    mock_result.stdout = "  10.0.0.1       aa-bb-cc-dd-ee-ff     static"
    with patch('monitor.subprocess.run', return_value=mock_result):
        mac = get_mac('10.0.0.1')
    assert mac == 'aa-bb-cc-dd-ee-ff'


def test_get_mac_not_found():
    mock_result = MagicMock()
    mock_result.stdout = "no entry for 10.0.0.1"
    with patch('monitor.subprocess.run', return_value=mock_result):
        mac = get_mac('10.0.0.1')
    assert mac == '—'


def test_get_mac_subprocess_error():
    with patch('monitor.subprocess.run', side_effect=Exception("oops")):
        mac = get_mac('10.0.0.1')
    assert mac == '—'


# --- scan_host ---

def test_scan_host_alive():
    with patch('monitor.ping_host', return_value=True), \
         patch('monitor.get_mac', return_value='aa:bb:cc:dd:ee:ff'):
        result = scan_host('10.0.0.1')
    assert result == {'ip': '10.0.0.1', 'alive': True, 'mac': 'aa:bb:cc:dd:ee:ff'}


def test_scan_host_dead():
    with patch('monitor.ping_host', return_value=False):
        result = scan_host('10.0.0.1')
    assert result == {'ip': '10.0.0.1', 'alive': False, 'mac': '—'}
    # get_mac should NOT be called for dead hosts
