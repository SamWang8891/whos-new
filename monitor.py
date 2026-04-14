"""IP Range Monitor — continuously pings an IP range, shows online/offline events."""
import ipaddress
import platform as _platform
import queue
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional
import tkinter as tk
from tkinter import ttk, scrolledtext


# ---------------------------------------------------------------------------
# IP Parser
# ---------------------------------------------------------------------------

MAX_HOSTS = 65_536  # refuse ranges larger than /16


def parse_ip_range(input_str: str) -> list[str]:
    """Parse an IPv4 CIDR string or 'start-end' range into a flat list of IP strings.

    Supports:
    - CIDR notation: '192.168.1.0/24' (returns .hosts(); /32 returns the host address)
    - Start-end range: '192.168.1.1 - 192.168.1.254' (spaces optional)

    Raises ValueError for: invalid input, reversed ranges, ranges > 65,536 addresses.
    IPv6 is not supported.
    """
    input_str = input_str.strip()
    # Detect range format: contains '-' that is not part of a CIDR prefix
    # A '-' in a CIDR would only appear in the prefix length, which is numeric after '/'
    # So: if '-' appears and there is no '/' before the '-', treat as range.
    if '-' in input_str and '/' not in input_str:
        parts = input_str.split('-', 1)
        start = ipaddress.ip_address(parts[0].strip())
        end = ipaddress.ip_address(parts[1].strip())
        if int(end) < int(start):
            raise ValueError(f"End IP {end} must be >= start IP {start}")
        count = int(end) - int(start) + 1
        if count > MAX_HOSTS:
            raise ValueError(f"Range too large ({count:,} addresses); maximum is {MAX_HOSTS:,}")
        return [str(ipaddress.ip_address(i)) for i in range(int(start), int(end) + 1)]
    else:
        net = ipaddress.ip_network(input_str, strict=False)
        if net.num_addresses > MAX_HOSTS:
            raise ValueError(
                f"Range too large ({net.num_addresses:,} addresses); maximum is {MAX_HOSTS:,}"
            )
        hosts = list(net.hosts())
        if not hosts:
            # /32 — return the network address itself
            return [str(net.network_address)]
        return [str(ip) for ip in hosts]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(r'([\da-fA-F]{1,2}[:\-]){5}[\da-fA-F]{1,2}')
_SYSTEM = _platform.system()  # 'Darwin', 'Linux', or 'Windows'


def _build_ping_cmd(ip: str) -> list[str]:
    if _SYSTEM == 'Windows':
        return ['ping', '-n', '1', '-w', '1000', ip]
    if _SYSTEM == 'Darwin':
        return ['ping', '-c', '1', '-W', '1000', ip]  # -W in ms on macOS
    return ['ping', '-c', '1', '-W', '1', ip]          # -W in seconds on Linux


def _build_arp_cmd(ip: str) -> list[str]:
    if _SYSTEM == 'Windows':
        return ['arp', '-a', ip]
    if _SYSTEM == 'Linux':
        return ['arp', '-n', ip]
    return ['arp', ip]  # macOS


def ping_host(ip: str) -> bool:
    """Return True if host responds to ping."""
    cmd = _build_ping_cmd(ip)
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False


def get_mac(ip: str) -> str:
    """Return MAC address string from ARP cache, or '—' if not found."""
    cmd = _build_arp_cmd(ip)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        match = _MAC_RE.search(result.stdout)
        return match.group(0) if match else '—'
    except Exception:
        return '—'


def scan_host(ip: str) -> dict:
    """Ping host; if alive, fetch MAC. Returns {ip, alive, mac}."""
    alive = ping_host(ip)
    mac = get_mac(ip) if alive else '—'
    return {'ip': ip, 'alive': alive, 'mac': mac}


# ---------------------------------------------------------------------------
# State Tracker
# ---------------------------------------------------------------------------


class StateTracker:
    """Tracks per-IP status and emits change events."""

    def __init__(self) -> None:
        self._state: dict[str, dict] = {}

    def update(self, ip: str, alive: bool, mac: str) -> Optional[dict]:
        """
        Record new scan result. Returns a change-event dict if status changed,
        otherwise None. Format: {ip, status, mac, time}.
        """
        now = datetime.now().strftime('%H:%M:%S')
        new_status = 'ONLINE' if alive else 'OFFLINE'
        prev = self._state.get(ip)

        if prev is None or prev['status'] != new_status:
            self._state[ip] = {'status': new_status, 'mac': mac, 'last_seen': now}
            return {'ip': ip, 'status': new_status, 'mac': mac, 'time': now}

        # No status change — still update MAC and last_seen if online
        if alive:
            self._state[ip]['mac'] = mac
            self._state[ip]['last_seen'] = now
        return None

    def get(self, ip: str) -> Optional[dict]:
        return self._state.get(ip)

    def get_all(self) -> dict[str, dict]:
        return dict(self._state)


# ---------------------------------------------------------------------------
# Tkinter App
# ---------------------------------------------------------------------------


class MonitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('IP Range Monitor')
        self.root.minsize(720, 520)

        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._tracker = StateTracker()
        self._sweep_thread: Optional[threading.Thread] = None

        self._build_ui()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._poll()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # --- Control bar ---
        ctrl = ttk.Frame(self.root, padding=8)
        ctrl.pack(fill='x', side='top')

        ttk.Label(ctrl, text='IP Range:').pack(side='left')
        self._range_var = tk.StringVar(value='192.168.1.0/24')
        ttk.Entry(ctrl, textvariable=self._range_var, width=28).pack(side='left', padx=(4, 16))

        ttk.Label(ctrl, text='Interval (s):').pack(side='left')
        self._interval_var = tk.IntVar(value=5)
        ttk.Spinbox(ctrl, from_=1, to=300, textvariable=self._interval_var, width=6).pack(
            side='left', padx=(4, 16)
        )

        self._btn_text = tk.StringVar(value='Start')
        ttk.Button(ctrl, textvariable=self._btn_text, command=self._toggle).pack(side='left')

        self._error_var = tk.StringVar()
        ttk.Label(ctrl, textvariable=self._error_var, foreground='red').pack(
            side='left', padx=(8, 0)
        )

        # --- Notification log ---
        log_frame = ttk.LabelFrame(self.root, text='Events', padding=4)
        log_frame.pack(fill='x', side='top', padx=8, pady=(0, 4))

        self._log = scrolledtext.ScrolledText(
            log_frame, height=6, state='disabled', font=('Courier', 10), wrap='none',
            # background='white', foreground='black'
        )
        self._log.pack(fill='x')
        self._log.tag_configure('ONLINE', foreground='green')
        self._log.tag_configure('OFFLINE', foreground='red')

        # --- Live IP table ---
        table_frame = ttk.LabelFrame(self.root, text='Hosts', padding=4)
        table_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        cols = ('ip', 'status', 'mac', 'last_seen')
        self._tree = ttk.Treeview(table_frame, columns=cols, show='headings', selectmode='none')
        self._tree.heading('ip', text='IP')
        self._tree.heading('status', text='Status')
        self._tree.heading('mac', text='MAC')
        self._tree.heading('last_seen', text='Last Seen')
        self._tree.column('ip', width=140, anchor='w')
        self._tree.column('status', width=80, anchor='center')
        self._tree.column('mac', width=170, anchor='w')
        self._tree.column('last_seen', width=90, anchor='center')

        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self._tree.pack(fill='both', expand=True)

        self._tree.tag_configure('ONLINE', foreground='green')
        self._tree.tag_configure('OFFLINE', foreground='red')

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        if self._btn_text.get() == 'Start':
            self._start()
        else:
            self._stop()

    def _start(self) -> None:
        self._error_var.set('')
        try:
            ips = parse_ip_range(self._range_var.get())
        except ValueError as exc:
            self._error_var.set(str(exc))
            return

        # Signal any running sweep to stop and wait for it to exit
        self._stop_event.set()
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=5.0)

        # Reset table and tracker
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._tracker = StateTracker()
        for ip in ips:
            self._tree.insert('', 'end', iid=ip, values=(ip, '—', '—', '—'))

        self._stop_event.clear()
        self._sweep_thread = threading.Thread(
            target=self._sweep_loop, args=(ips,), daemon=True
        )
        self._sweep_thread.start()
        self._btn_text.set('Stop')

    def _stop(self) -> None:
        self._stop_event.set()
        self._btn_text.set('Start')

    def _on_close(self) -> None:
        self._stop_event.set()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Background sweep loop
    # ------------------------------------------------------------------

    def _sweep_loop(self, ips: list[str]) -> None:
        max_workers = min(50, len(ips))
        while not self._stop_event.is_set():
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(scan_host, ip): ip for ip in ips}
                for future in as_completed(futures):
                    try:
                        self._queue.put(future.result())
                    except Exception:
                        pass
            # Wait for the interval, but wake early if stopped
            interval = max(1, self._interval_var.get())
            self._stop_event.wait(interval)

    # ------------------------------------------------------------------
    # Queue polling (main thread)
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                result = self._queue.get_nowait()
                event = self._tracker.update(result['ip'], result['alive'], result['mac'])
                if event:
                    self._append_log(event)
                self._update_row(result['ip'])
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    def _append_log(self, event: dict) -> None:
        line = f"[{event['time']}] {event['ip']:<18} {event['status']:<10} {event['mac']}\n"
        self._log.configure(state='normal')
        self._log.insert('end', line, event['status'])
        self._log.see('end')
        self._log.configure(state='disabled')

    def _update_row(self, ip: str) -> None:
        state = self._tracker.get(ip)
        if state and self._tree.exists(ip):
            self._tree.item(
                ip,
                values=(ip, state['status'], state['mac'], state['last_seen']),
                tags=(state['status'],),
            )


if __name__ == '__main__':
    root = tk.Tk()
    # root.configure(bg='white')
    app = MonitorApp(root)
    # root.update()  # force initial render on macOS before entering the event loop
    root.mainloop()
