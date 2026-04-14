# whos-new

A desktop app that continuously pings an IP range and shows real-time online/offline notifications with MAC addresses.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

## Requirements

Python 3.12+ with Tkinter. On macOS, use Homebrew:

```bash
brew install python@3.12 python-tk@3.12
```

## Usage

```bash
python3.12 monitor.py
```

Enter an IP range, set a scan interval, and click **Start**.

**Supported range formats:**
- CIDR: `192.168.1.0/24`
- Start–end: `192.168.1.1-192.168.1.254`

## UI

```
┌─────────────────────────────────────────────────────┐
│  IP Range: [192.168.1.0/24]  Interval: [5s]  [Start]│
├─────────────────────────────────────────────────────┤
│  [14:32:01] 192.168.1.42   ONLINE    aa:bb:cc:dd:ee │  ← Events log
│  [14:32:05] 192.168.1.10   OFFLINE   —              │
├─────────────────────────────────────────────────────┤
│  IP             Status   MAC               Last Seen │  ← Live host table
│  192.168.1.1    ONLINE   aa:bb:cc:dd:ee:ff 14:32:01  │
└─────────────────────────────────────────────────────┘
```

- **Events log** — timestamped history of status changes (green = online, red = offline)
- **Hosts table** — live view of all IPs in the range with current status and MAC address

## Development

```bash
uv sync --dev
uv run pytest
```
