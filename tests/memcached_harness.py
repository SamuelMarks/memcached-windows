"""Cross-platform test harness for memcached.

Provides server process management and protocol clients (ASCII & Binary)
without requiring Perl, Bash, or any third-party dependencies.
"""

import os
import socket
import struct
import subprocess
import sys
import time


def find_free_port():
    """Allocate an ephemeral port on 127.0.0.1.

    :return: An available ephemeral TCP port number.
    :rtype: int
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_memcached_binary():
    """Locate the memcached executable.

    Checks the MEMCACHED_BIN environment variable and default filesystem locations.

    :return: Path to the memcached executable.
    :rtype: str
    """
    env_bin = os.environ.get("MEMCACHED_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    candidates = [
        os.path.join(".", "memcached.exe"),
        os.path.join(".", "memcached"),
        os.path.join("build_msvc", "memcached.exe"),
        os.path.join("build", "memcached"),
        os.path.join(os.path.dirname(__file__), "..", "build_msvc", "memcached.exe"),
        os.path.join(os.path.dirname(__file__), "..", "build", "memcached"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)

    return "memcached.exe" if sys.platform == "win32" else "memcached"


def get_emulator():
    """Return emulator command list when running Windows binaries on non-Windows.

    :return: List of command arguments representing the emulator, or an empty list.
    :rtype: list[str]
    """
    emulator = os.environ.get("MEMCACHED_EMULATOR")
    if emulator:
        return [emulator]
    bin_path = get_memcached_binary()
    if bin_path.endswith(".exe") and sys.platform != "win32":
        return ["wine"]
    return []


class MemcachedServer:
    """Manages the lifecycle of a memcached server process."""

    def __init__(self, port=None, extra_args=None):
        """Initialize a new MemcachedServer instance.

        :param port: TCP port for the server to bind to, or None to auto-allocate.
        :type port: int | None
        :param extra_args: Additional command-line flags passed to memcached.
        :type extra_args: list[str] | None
        """
        self.port = port or find_free_port()
        self.extra_args = extra_args or []
        self.proc = None
        self.bin_path = get_memcached_binary()
        self.emulator = get_emulator()

    def start(self, timeout=15.0):
        """Start the memcached daemon process and wait until socket is accepting connections.

        :param timeout: Maximum time in seconds to wait for socket readiness.
        :type timeout: float
        :return: self for chaining.
        :rtype: MemcachedServer
        :raises RuntimeError: If memcached terminates prematurely.
        :raises TimeoutError: If memcached fails to listen within the timeout.
        """
        cmd = (
            self.emulator
            + [
                self.bin_path,
                "-l",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-U",
                "0",
            ]
            + (["-u", "root"] if hasattr(os, "geteuid") and os.geteuid() == 0 else [])
            + self.extra_args
        )

        env = os.environ.copy()
        env["WINEDEBUG"] = "-all"
        env["MVK_CONFIG_LOG_LEVEL"] = "0"

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        start_time = time.time()
        connected = False
        while time.time() - start_time < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"memcached exited prematurely with code {self.proc.returncode}"
                )
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", self.port))
                    connected = True
                    break
            except (ConnectionRefusedError, socket.timeout, OSError):
                time.sleep(0.1)

        if not connected:
            self.stop()
            raise TimeoutError(
                f"Failed to connect to memcached on port {self.port} within {timeout}s"
            )
        return self

    def stop(self):
        """Stop the memcached process if active.

        :return: None
        :rtype: None
        """
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=2)
                except Exception:
                    pass
            self.proc = None

    def __enter__(self):
        """Context management entry to start server.

        :return: Started MemcachedServer instance.
        :rtype: MemcachedServer
        """
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context management exit to stop server.

        :param exc_type: Exception type if raised.
        :param exc_val: Exception instance if raised.
        :param exc_tb: Traceback if raised.
        :return: None
        :rtype: None
        """
        self.stop()

    def client(self):
        """Create and connect a client to this server.

        :return: Connected MemcachedClient instance.
        :rtype: MemcachedClient
        """
        return MemcachedClient("127.0.0.1", self.port)


class MemcachedClient:
    """Socket client for interacting with memcached ASCII and binary protocols."""

    def __init__(self, host="127.0.0.1", port=11211, timeout=5.0):
        """Initialize a new MemcachedClient and connect to the specified server.

        :param host: Server IP address or hostname.
        :type host: str
        :param port: Server TCP port.
        :type port: int
        :param timeout: Socket timeout in seconds.
        :type timeout: float
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((host, port))
        self._buf = b""

    def close(self):
        """Close the underlying TCP socket connection.

        :return: None
        :rtype: None
        """
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def __enter__(self):
        """Context management entry returning self.

        :return: The client instance.
        :rtype: MemcachedClient
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context management exit closing connection.

        :param exc_type: Exception type if raised.
        :param exc_val: Exception instance if raised.
        :param exc_tb: Traceback if raised.
        :return: None
        :rtype: None
        """
        self.close()

    # --- ASCII Protocol Methods ---

    def send_cmd(self, cmd_str):
        """Send a raw command string terminated with CRLF.

        :param cmd_str: Command string or bytes to transmit.
        :type cmd_str: str | bytes
        :return: None
        :rtype: None
        """
        if isinstance(cmd_str, str):
            cmd_str = cmd_str.encode("utf-8")
        if not cmd_str.endswith(b"\r\n"):
            cmd_str += b"\r\n"
        self.sock.sendall(cmd_str)

    def readline(self):
        """Read a single CRLF-delimited line from the socket.

        :return: Decoded line without CRLF.
        :rtype: str
        """
        while b"\r\n" not in self._buf:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            self._buf += chunk
        if b"\r\n" in self._buf:
            idx = self._buf.index(b"\r\n")
            line = self._buf[:idx]
            self._buf = self._buf[idx + 2 :]
            return line.decode("utf-8", errors="replace")
        line = self._buf
        self._buf = b""
        return line.decode("utf-8", errors="replace")

    def read_bytes(self, n):
        """Read exactly n bytes from the socket.

        :param n: Number of bytes to read.
        :type n: int
        :return: Raw byte data read from the socket.
        :rtype: bytes
        """
        while len(self._buf) < n:
            try:
                chunk = self.sock.recv(max(4096, n - len(self._buf)))
            except socket.timeout:
                break
            if not chunk:
                break
            self._buf += chunk
        data = self._buf[:n]
        self._buf = self._buf[n:]
        return data

    def set(self, key, val, flags=0, exptime=0, noreply=False):
        """Store an item via the ASCII set command.

        :param key: Item key.
        :type key: str
        :param val: Item value.
        :type val: str | bytes
        :param flags: Client flags.
        :type flags: int
        :param exptime: Expiration time in seconds.
        :type exptime: int
        :param noreply: Whether to request noreply.
        :type noreply: bool
        :return: Response status (e.g. STORED), or None if noreply.
        :rtype: str | None
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        cmd = f"set {key} {flags} {exptime} {len(val_bytes)}"
        if noreply:
            cmd += " noreply"
        self.send_cmd(cmd)
        self.sock.sendall(val_bytes + b"\r\n")
        if noreply:
            return None
        return self.readline().strip()

    def add(self, key, val, flags=0, exptime=0):
        """Store an item only if it does not already exist via ASCII add.

        :param key: Item key.
        :type key: str
        :param val: Item value.
        :type val: str | bytes
        :param flags: Client flags.
        :type flags: int
        :param exptime: Expiration time in seconds.
        :type exptime: int
        :return: Response status (e.g. STORED or NOT_STORED).
        :rtype: str
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        self.send_cmd(f"add {key} {flags} {exptime} {len(val_bytes)}")
        self.sock.sendall(val_bytes + b"\r\n")
        return self.readline().strip()

    def replace(self, key, val, flags=0, exptime=0):
        """Store an item only if it already exists via ASCII replace.

        :param key: Item key.
        :type key: str
        :param val: Item value.
        :type val: str | bytes
        :param flags: Client flags.
        :type flags: int
        :param exptime: Expiration time in seconds.
        :type exptime: int
        :return: Response status (e.g. STORED or NOT_STORED).
        :rtype: str
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        self.send_cmd(f"replace {key} {flags} {exptime} {len(val_bytes)}")
        self.sock.sendall(val_bytes + b"\r\n")
        return self.readline().strip()

    def append(self, key, val):
        """Append data to an existing item value via ASCII append.

        :param key: Item key.
        :type key: str
        :param val: Value bytes/str to append.
        :type val: str | bytes
        :return: Response status (e.g. STORED or NOT_STORED).
        :rtype: str
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        self.send_cmd(f"append {key} 0 0 {len(val_bytes)}")
        self.sock.sendall(val_bytes + b"\r\n")
        return self.readline().strip()

    def prepend(self, key, val):
        """Prepend data to an existing item value via ASCII prepend.

        :param key: Item key.
        :type key: str
        :param val: Value bytes/str to prepend.
        :type val: str | bytes
        :return: Response status (e.g. STORED or NOT_STORED).
        :rtype: str
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        self.send_cmd(f"prepend {key} 0 0 {len(val_bytes)}")
        self.sock.sendall(val_bytes + b"\r\n")
        return self.readline().strip()

    def cas(self, key, val, cas_id, flags=0, exptime=0):
        """Store an item conditionally using Compare-And-Swap (CAS).

        :param key: Item key.
        :type key: str
        :param val: Item value.
        :type val: str | bytes
        :param cas_id: Unique CAS token obtained from gets.
        :type cas_id: int
        :param flags: Client flags.
        :type flags: int
        :param exptime: Expiration time in seconds.
        :type exptime: int
        :return: Response status (e.g. STORED or EXISTS).
        :rtype: str
        """
        val_bytes = val.encode("utf-8") if isinstance(val, str) else bytes(val)
        self.send_cmd(f"cas {key} {flags} {exptime} {len(val_bytes)} {cas_id}")
        self.sock.sendall(val_bytes + b"\r\n")
        return self.readline().strip()

    def get(self, *keys):
        """Retrieve one or more keys.

        :param keys: Variable number of key strings to fetch.
        :type keys: str
        :return: Dictionary mapping key to tuple of (value_str, flags_int).
        :rtype: dict[str, tuple[str, int]]
        """
        self.send_cmd(f"get {' '.join(keys)}")
        results = {}
        while True:
            line = self.readline()
            if not line or line.startswith("END"):
                break
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "VALUE":
                k = parts[1]
                flags = int(parts[2])
                nbytes = int(parts[3])
                data = self.read_bytes(nbytes)
                self.read_bytes(2)  # consume trailing CRLF
                results[k] = (data.decode("utf-8", errors="replace"), flags)
        return results

    def gets(self, *keys):
        """Retrieve one or more keys with CAS identifiers.

        :param keys: Variable number of key strings to fetch.
        :type keys: str
        :return: Dictionary mapping key to tuple of (value_str, flags_int, cas_id).
        :rtype: dict[str, tuple[str, int, int]]
        """
        self.send_cmd(f"gets {' '.join(keys)}")
        results = {}
        while True:
            line = self.readline()
            if not line or line.startswith("END"):
                break
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == "VALUE":
                k = parts[1]
                flags = int(parts[2])
                nbytes = int(parts[3])
                cas_id = int(parts[4])
                data = self.read_bytes(nbytes)
                self.read_bytes(2)  # consume trailing CRLF
                results[k] = (data.decode("utf-8", errors="replace"), flags, cas_id)
        return results

    def delete(self, key):
        """Delete an item by key via ASCII delete.

        :param key: Key to delete.
        :type key: str
        :return: Response status (e.g. DELETED or NOT_FOUND).
        :rtype: str
        """
        self.send_cmd(f"delete {key}")
        return self.readline().strip()

    def incr(self, key, value=1):
        """Increment a numeric counter item via ASCII incr.

        :param key: Key of the counter.
        :type key: str
        :param value: Amount to increment by.
        :type value: int
        :return: New integer value of the counter, or error response string.
        :rtype: int | str
        """
        self.send_cmd(f"incr {key} {value}")
        res = self.readline().strip()
        try:
            return int(res)
        except ValueError:
            return res

    def decr(self, key, value=1):
        """Decrement a numeric counter item via ASCII decr.

        :param key: Key of the counter.
        :type key: str
        :param value: Amount to decrement by.
        :type value: int
        :return: New integer value of the counter, or error response string.
        :rtype: int | str
        """
        self.send_cmd(f"decr {key} {value}")
        res = self.readline().strip()
        try:
            return int(res)
        except ValueError:
            return res

    def touch(self, key, exptime):
        """Update the expiration time of an existing item via ASCII touch.

        :param key: Item key.
        :type key: str
        :param exptime: New expiration time in seconds.
        :type exptime: int
        :return: Response status (TOUCHED or NOT_FOUND).
        :rtype: str
        """
        self.send_cmd(f"touch {key} {exptime}")
        return self.readline().strip()

    def stats(self, arg=None):
        """Query memcached operational statistics.

        :param arg: Subcommand argument (e.g. 'settings', 'slabs', 'items').
        :type arg: str | None
        :return: Dictionary mapping stat name to stat value.
        :rtype: dict[str, str]
        """
        cmd = f"stats {arg}" if arg else "stats"
        self.send_cmd(cmd)
        res = {}
        while True:
            line = self.readline()
            if not line or line.startswith("END"):
                break
            parts = line.strip().split(None, 2)
            if len(parts) == 3 and parts[0] == "STAT":
                res[parts[1]] = parts[2]
            elif len(parts) == 2 and parts[0] == "STAT":
                res[parts[1]] = ""
        return res

    def flush_all(self, delay=0):
        """Invalidate all existing cache items immediately or after a delay.

        :param delay: Optional delay in seconds before invalidation.
        :type delay: int
        :return: Response status (OK).
        :rtype: str
        """
        cmd = f"flush_all {delay}" if delay else "flush_all"
        self.send_cmd(cmd)
        return self.readline().strip()

    def version(self):
        """Query server version.

        :return: Version string reported by memcached.
        :rtype: str
        """
        self.send_cmd("version")
        line = self.readline().strip()
        if line.startswith("VERSION "):
            return line[8:]
        return line

    def quit(self):
        """Send ASCII quit command and close the connection.

        :return: None
        :rtype: None
        """
        self.send_cmd("quit")
        self.close()

    # --- Binary Protocol Methods ---

    def bin_send(self, opcode, key=b"", val=b"", extras=b"", cas=0, opaque=0):
        """Construct and send a binary protocol request packet.

        :param opcode: Binary protocol command opcode.
        :type opcode: int
        :param key: Key bytes or string.
        :type key: bytes | str
        :param val: Value bytes or string.
        :type val: bytes | str
        :param extras: Optional binary extras payload.
        :type extras: bytes
        :param cas: Compare-and-swap token.
        :type cas: int
        :param opaque: Request tracking identifier.
        :type opaque: int
        :return: None
        :rtype: None
        """
        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(val, str):
            val = val.encode("utf-8")

        extlen = len(extras)
        keylen = len(key)
        bodylen = extlen + keylen + len(val)
        magic = 0x80  # Request
        datatype = 0
        vbucket = 0

        header = struct.pack(
            "!BBHBBHIIQ",
            magic,
            opcode,
            keylen,
            extlen,
            datatype,
            vbucket,
            bodylen,
            opaque,
            cas,
        )
        packet = header + extras + key + val
        self.sock.sendall(packet)

    def bin_recv(self):
        """Receive and unpack a 24-byte binary protocol response packet and body.

        :return: Dictionary containing parsed binary response fields, or None on EOF.
        :rtype: dict[str, int | bytes] | None
        """
        header = self.read_bytes(24)
        if len(header) < 24:
            return None
        magic, opcode, keylen, extlen, datatype, status, bodylen, opaque, cas = (
            struct.unpack("!BBHBBHIIQ", header)
        )
        body = self.read_bytes(bodylen) if bodylen > 0 else b""
        extras = body[:extlen]
        key = body[extlen : extlen + keylen]
        val = body[extlen + keylen :]
        return {
            "magic": magic,
            "opcode": opcode,
            "keylen": keylen,
            "extlen": extlen,
            "datatype": datatype,
            "status": status,
            "bodylen": bodylen,
            "opaque": opaque,
            "cas": cas,
            "extras": extras,
            "key": key,
            "val": val,
        }
