"""Manual Windows smoke using real CE, an isolated table and an owned process.

Run: python tests/ce_mvp_native_smoke.py [candidate_count]
Only the target PID is substituted in a copy of the existing local config.
The runtime never imports this driver or its target. No CE APIs are mocked.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def target(count):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel.VirtualAlloc.restype = ctypes.c_void_p
    kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
    kernel.VirtualFree.restype = ctypes.c_int
    base = kernel.VirtualAlloc(None, max(65536, (count + 2) * 256), 0x3000, 4)
    assert base
    for index in range(count):
        ctypes.c_float.from_address(base + 0x128 + index * 256).value = 100
    address = base + 0x128 + (count - 1) * 256
    fields = [0x10011200, 0x10013800, 0x10042100, 0x10060000, 0x10025600, 0x10028400, 0x10086300]
    for offset, word in zip([-0x20, -0x10, -8, 0x30, 0x40, 0x48, 0x50], fields):
        ctypes.c_uint32.from_address(address + offset).value = word
    print(json.dumps({"pid": os.getpid(), "address": address}), flush=True)
    allocated = True
    try:
        for line in sys.stdin:
            command = line.strip()
            if command == "drift":
                ctypes.c_float.from_address(address).value = 42
            elif command == "unreadable":
                assert kernel.VirtualFree(base, 0, 0x8000)
                allocated = False
            elif command == "exit":
                break
            print(json.dumps({"command": command,
                              "value": ctypes.c_float.from_address(address).value if allocated else None}), flush=True)
    finally:
        if allocated:
            assert kernel.VirtualFree(base, 0, 0x8000)


def run(count):
    if os.name != "nt" or count < 1:
        raise SystemExit("Windows and a positive candidate count are required")
    sys.path.insert(0, str(ROOT / "src"))
    from prepare_ce_mvp import lua_path, prepare
    location = ROOT / "reports/2026-11-26/ce-native-id1-local" / ("product-smoke-" + time.strftime("%H%M%S"))
    location.mkdir(parents=True)
    # No source modules, adapters or fixtures are copied beside the table.
    table = prepare(ROOT / "src", location / "ce_mvp.local.CT")
    child = subprocess.Popen([sys.executable, str(__file__), "--target", str(count)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    ce = None
    try:
        ready = json.loads(child.stdout.readline())
        print(json.dumps({"stage": "target_ready", **ready, "directory": str(location)}), flush=True)
        config = (ROOT / "src/ce_mvp_config.local.lua").read_text(encoding="utf-8")
        config, replacements = re.subn(r"target_pid\s*=\s*\d+", f'target_pid = {ready["pid"]}', config, count=1)
        assert replacements == 1
        (location / "ce_mvp_config.local.lua").write_text(config, encoding="utf-8")
        output = location / "result.txt"
        signal = location / "signal.txt"
        root = ET.parse(table).getroot()
        # A separate trainer drives the unchanged generated ID1 record. The
        # production CT has no startup LuaScript or automatic activation.
        ET.SubElement(root, "LuaScript").text = f'''
local result_path={lua_path(output.as_posix())}
local signal_path={lua_path(signal.as_posix())}
local expected_pid={ready['pid']}
local expected_address={ready['address']}
local minimum_count={count}
local timer,stage,started,stop_time=nil,0,getTickCount(),nil
local function save(path,value)
  local f=assert(io.open(path,'w')); f:write(value); f:close()
end
local function finish(value)
  if timer then timer.Enabled=false; timer.destroy(); timer=nil end
  if CE_MVP_PRODUCT then CE_MVP_PRODUCT.stop() end
  save(result_path,value)
  closeCE()
end
print=function() end
timer=createTimer(nil,false); timer.Interval=100
timer.OnTimer=function()
  local ok,err=pcall(function()
    if getTickCount()-started>145000 then error('SMOKE_TIMEOUT') end
    local control=assert(getAddressList().getMemoryRecordByID(1))
    local live=assert(getAddressList().getMemoryRecordByID(3))
    if stage==0 then
      control.Active=true
      assert(control.Active and CE_MVP_PRODUCT,'ID1_START_FAILED')
      stage=1; return
    end
    local s=CE_MVP_PRODUCT.status()
    if s.state=='ERROR' then
      assert(stage>=3 and not s.running and s.cleanup_ok and s.write_count==2,
        'RUNTIME:'..tostring(s.stop_reason))
      assert(s.stop_reason:find('VALUE_UNREADABLE',1,true),'WRONG_STOP_REASON')
      assert(not control.Active and tostring(live.Value):find('?',1,true),'STOP_OR_DISPLAY_FAILED')
      stop_time=stop_time or getTickCount()
      if getTickCount()-stop_time>=2200 then
        finish('PASS pid='..expected_pid..' address='..string.format('%X',s.address)..
          ' raw='..s.raw_count..' inspected='..s.inspected_count..' scored='..s.scored_count..
          ' writes='..s.write_count..' rewrites='..s.rewrite_count..
          ' stopped_display='..tostring(live.Value)..' control_active='..tostring(control.Active)..
          ' stop='..s.stop_reason..' elapsed_ms='..(getTickCount()-started))
      end
      return
    end
    if stage==1 and s.state=='MONITORING' then
      assert(s.pid==expected_pid and s.address==expected_address,'WRONG_CANDIDATE')
      assert(s.current_value==125 and s.readback_verified and tonumber(live.Value)==125,'INITIAL_READBACK')
      assert(s.raw_count>=minimum_count and s.raw_count==s.inspected_count
        and s.scored_count==s.filtered_count and s.scored_count>=minimum_count,'INCOMPLETE_POOL')
      live.Active=true
      assert(not live.Active,'LIVE_ROW_MUST_NOT_FREEZE')
      save(signal_path,'drift'); stage=2
    elseif stage==2 and s.write_count==2 then
      assert(s.rewrite_count==1 and s.current_value==125 and tonumber(live.Value)==125,'REWRITE_READBACK')
      save(signal_path,'unreadable'); stage=3
    end
  end)
  if not ok then finish('FAIL '..tostring(err)) end
end
timer.Enabled=true
'''
        trainer = location / "native_smoke.CETRAINER"
        ET.ElementTree(root).write(trainer, encoding="utf-8", xml_declaration=True)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        ce = subprocess.Popen([r"C:\Program Files\Cheat Engine\cheatengine-x86_64.exe", str(trainer)], startupinfo=startup)
        print(json.dumps({"stage": "ce_started", "ce_pid": ce.pid}), flush=True)
        delivered = set()
        deadline = time.monotonic() + 155
        while time.monotonic() < deadline and not output.exists():
            if signal.exists():
                command = signal.read_text(encoding="utf-8").strip()
                if command and command not in delivered:
                    delivered.add(command)
                    child.stdin.write(command + "\n"); child.stdin.flush()
                    print(child.stdout.readline().strip(), flush=True)
            if ce.poll() is not None:
                break
            time.sleep(.1)
        result = output.read_text(encoding="utf-8") if output.exists() else f"NO_RESULT ce_exit={ce.poll()}"
        print(result, flush=True)
        (location / "driver-result.txt").write_text(result, encoding="utf-8")
        return 0 if result.startswith("PASS") else 1
    finally:
        if ce is not None and ce.poll() is None:
            try:
                ce.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ce.terminate(); ce.wait(timeout=10)
        if child.poll() is None:
            child.stdin.write("exit\n"); child.stdin.flush()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.terminate(); child.wait(timeout=5)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--target"]:
        target(int(sys.argv[2]))
    else:
        raise SystemExit(run(int(sys.argv[1]) if sys.argv[1:] else 1))
