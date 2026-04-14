import pytest
from monitor import parse_ip_range


def test_cidr_24():
    ips = parse_ip_range("192.168.1.0/24")
    assert ips[0] == "192.168.1.1"
    assert ips[-1] == "192.168.1.254"
    assert len(ips) == 254


def test_cidr_30():
    ips = parse_ip_range("10.0.0.0/30")
    assert ips == ["10.0.0.1", "10.0.0.2"]


def test_cidr_host_route():
    # /32 has no hosts(), should return just the single IP
    ips = parse_ip_range("10.0.0.1/32")
    assert ips == ["10.0.0.1"]


def test_range_simple():
    ips = parse_ip_range("192.168.1.1-192.168.1.5")
    assert ips == ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5"]


def test_range_with_spaces():
    ips = parse_ip_range("  10.0.0.10 - 10.0.0.12  ")
    assert ips == ["10.0.0.10", "10.0.0.11", "10.0.0.12"]


def test_range_single_ip():
    ips = parse_ip_range("192.168.1.1-192.168.1.1")
    assert ips == ["192.168.1.1"]


def test_invalid_cidr_raises():
    with pytest.raises(ValueError):
        parse_ip_range("999.999.999.999/24")


def test_invalid_range_raises():
    with pytest.raises(ValueError):
        parse_ip_range("10.0.0.5-10.0.0.3")  # end before start


def test_cidr_too_large_raises():
    with pytest.raises(ValueError, match="too large"):
        parse_ip_range("10.0.0.0/8")  # 16.7M hosts


def test_range_too_large_raises():
    with pytest.raises(ValueError, match="too large"):
        parse_ip_range("10.0.0.1-10.1.0.1")  # > 65536 addresses
