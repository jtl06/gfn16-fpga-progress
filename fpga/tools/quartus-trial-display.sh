#!/usr/bin/env bash
# Temporary authenticated display for the vendor's normal trial-activation GUI.
# No system service, external listening socket, or license-file modification.
set -euo pipefail
[[ "$(hostname -s)" == aethia ]] || { echo 'Run only on aethia.' >&2; exit 2; }
[[ -x /usr/bin/xkbcomp ]] || { echo 'Install x11-xkb-utils first.' >&2; exit 2; }
[[ ! -e /tmp/.X11-unix/X91 ]] || { echo 'Display :91 is already in use.' >&2; exit 2; }
umask 077
task_runtime=/home/jtl/gfn-fpga-lab/tools/gui-runtime
task_session=$(mktemp -d /home/jtl/gfn-fpga-lab/tools/quartus-display.XXXXXX)
task_children=()
cleanup() {
    trap - EXIT HUP INT TERM
    for task_pid in "${task_children[@]}"; do kill "$task_pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
    echo "Display stopped; private logs retained in $task_session"
}
trap cleanup EXIT HUP INT TERM
export PATH="$task_runtime/usr/bin:$PATH"
export LD_LIBRARY_PATH="$task_runtime/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$task_runtime/usr/lib/python3/dist-packages"
export DISPLAY=:91
export XAUTHORITY="$task_session/Xauthority"
xauth -f "$XAUTHORITY" add "$DISPLAY" MIT-MAGIC-COOKIE-1 "$(openssl rand -hex 16)"
openssl rand -base64 -out "$task_session/vnc-password.txt" 6
x11vnc -storepasswd "$(< "$task_session/vnc-password.txt")" "$task_session/vnc-password" >/dev/null
Xvfb "$DISPLAY" -screen 0 1280x900x24 -nolisten tcp -auth "$XAUTHORITY" >"$task_session/xvfb.log" 2>&1 &
task_children+=("$!")
for task_attempt in {1..30}; do
    [[ -e /tmp/.X11-unix/X91 ]] && break
    kill -0 "${task_children[0]}" || exit 1
    sleep 0.1
done
x11vnc -display "$DISPLAY" -auth "$XAUTHORITY" -listen 127.0.0.1 -localhost -rfbport 5911 \
    -rfbauth "$task_session/vnc-password" -forever -shared -noxdamage \
    >"$task_session/vnc.log" 2>&1 &
task_children+=("$!")
python3 -m websockify --web "$task_runtime/usr/share/novnc" 127.0.0.1:6081 127.0.0.1:5911 \
    >"$task_session/websockify.log" 2>&1 &
task_children+=("$!")
echo "SESSION=$task_session"
echo 'Forward SSH port 6081, then open http://127.0.0.1:6081/vnc.html'
/home/jtl/gfn-fpga-lab/tools/altera_pro/26.1/quartus/bin/quartus >"$task_session/quartus.log" 2>&1 &
task_children+=("$!")
wait "${task_children[-1]}"
