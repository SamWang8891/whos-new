from monitor import StateTracker


def test_first_online_emits_event():
    t = StateTracker()
    event = t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    assert event is not None
    assert event['ip'] == '10.0.0.1'
    assert event['status'] == 'ONLINE'
    assert event['mac'] == 'aa:bb:cc:dd:ee:ff'
    assert 'time' in event


def test_first_offline_emits_event():
    t = StateTracker()
    event = t.update('10.0.0.1', alive=False, mac='—')
    assert event is not None
    assert event['status'] == 'OFFLINE'


def test_no_change_returns_none():
    t = StateTracker()
    t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    event = t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    assert event is None


def test_online_to_offline_emits_event():
    t = StateTracker()
    t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    event = t.update('10.0.0.1', alive=False, mac='—')
    assert event is not None
    assert event['status'] == 'OFFLINE'


def test_offline_to_online_emits_event():
    t = StateTracker()
    t.update('10.0.0.1', alive=False, mac='—')
    event = t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    assert event is not None
    assert event['status'] == 'ONLINE'
    assert event['mac'] == 'aa:bb:cc:dd:ee:ff'


def test_get_returns_current_state():
    t = StateTracker()
    t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    state = t.get('10.0.0.1')
    assert state['status'] == 'ONLINE'
    assert state['mac'] == 'aa:bb:cc:dd:ee:ff'
    assert 'last_seen' in state


def test_get_unknown_ip_returns_none():
    t = StateTracker()
    assert t.get('10.0.0.99') is None


def test_get_all_returns_all_tracked():
    t = StateTracker()
    t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    t.update('10.0.0.2', alive=False, mac='—')
    all_state = t.get_all()
    assert '10.0.0.1' in all_state
    assert '10.0.0.2' in all_state
    assert len(all_state) == 2


def test_mac_updated_on_repeated_online():
    """MAC can change (e.g. ARP cache refresh), should be updated without emitting event."""
    t = StateTracker()
    t.update('10.0.0.1', alive=True, mac='aa:bb:cc:dd:ee:ff')
    event = t.update('10.0.0.1', alive=True, mac='11:22:33:44:55:66')
    assert event is None  # no status change
    assert t.get('10.0.0.1')['mac'] == '11:22:33:44:55:66'
