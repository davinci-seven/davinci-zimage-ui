"""Wait until ComfyUI HTTP API responds. Exit 0 if ready, 1 if timeout."""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

# 本包引擎 = 7777；界面 = 8888。避开 8188/7860 常见占用端口。
DEFAULT_PORT = 7777
TRIES = 150
INTERVAL = 2.0


def main() -> int:
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = DEFAULT_PORT
    url = f"http://127.0.0.1:{port}/system_stats"
    for i in range(1, TRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f"  ready after {i * INTERVAL:.0f}s  :{port}")
                    return 0
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        print(f"  waiting... {i}/{TRIES}  :{port}")
        time.sleep(INTERVAL)
    print(f"  timeout waiting for ComfyUI on :{port}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
