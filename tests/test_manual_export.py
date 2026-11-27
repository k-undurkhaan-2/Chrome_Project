"""Direct CE entry and serializer checks with the existing offline fixtures.

CE APIs below are controlled doubles, not evidence of a live owned-test capture.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import time

import pytest

from mvp0_export_loader import load_inventory, load_replay
from test_offline_full_population import ROOT, records, runtime  # noqa: F401
from test_stable_prescore_optimization import plain


SOURCE = ROOT / "src/mvp0_manual_export.lua"


@pytest.fixture
def export_env(runtime, tmp_path):
    # The command's --basetemp is also under ignored log/. Refuse accidental
    # private data creation in a tracked or external output location.
    relative = tmp_path.relative_to(ROOT).as_posix()
    assert relative.startswith("log/")
    subprocess.run(["git", "check-ignore", "-q", relative], cwd=ROOT, check=True)
    lua, w = runtime
    (tmp_path / "log").mkdir()
    lua.globals().checksum = lambda path: hashlib.md5(Path(path).read_bytes()).hexdigest()
    lua.globals().wall_clock = lambda: int(time.perf_counter() * 1000)
    lua.execute("""
      md5file=function(path) return checksum(path) end
      getTickCount=function() return wall_clock() end
      for _,name in ipairs({'openProcess','getOpenedProcessID','readInteger','readFloat',
        'readBytes','writeInteger','writeFloat','writeBytes','getCurrentMemscan',
        'createMemScan','createFoundList','AOBScan','autoAssemble','injectDLL',
        'createTimer','createThread','executeCode','executeCodeLocal','shellExecute'}) do
        _G[name]=function() error('FORBIDDEN_TARGET_API: '..name) end
      end
      os.execute=function() error('FORBIDDEN_SHELL') end
      io.popen=function() error('FORBIDDEN_SHELL') end
    """)
    load = lua.eval("function(s,p) return assert(load(s,'@'..p,'t'))() end")
    path = (tmp_path / "src/mvp0_manual_export.lua").as_posix()
    api = load(SOURCE.read_text(encoding="utf-8"), path)
    assert not list((tmp_path / "log").iterdir())  # lazy module load
    return lua, w, api, tmp_path, lambda: load(SOURCE.read_text(encoding="utf-8"), path)


def snapshot(lua, w, count=3):
    records(w, count, good=(2,))
    # The existing fixture has additional native-test metadata. Supply exactly
    # the approved AC5 observations, retaining the same tables and source order.
    return lua.execute("""
      local population={}
      for i,r in ipairs(w.objects) do
        population[i]={addr=r.addr,mapped=r.mapped,protect=r.protect,memory=r.memory}
      end
      s={authorized_owned=true,source_category='ARTIFICIAL_FIXTURE',
        permission_disposition='EXPRESSLY_APPROVED',source_snapshot_status='OPERATOR_FROZEN_COPY',
        population_basis='INITIAL_SNAPSHOT',acquisition_completeness='UNKNOWN',
        source_id='offline-fixture',capture_utc='UNKNOWN',records=population,
        expected_source_count=#population,
        evaluation_options={target_value_pattern=0x42C80000,target_value_float=100.0}}
      return s
    """)


@pytest.fixture
def direct_env(export_env):
    lua, w, api, path, reload = export_env
    lua.globals().directory_mode = lambda p: "directory" if Path(p).is_dir() else None

    def mkdir(p):
        assert Path(p) == path / "log"
        Path(p).mkdir()
        return True

    lua.globals().mkdir_local = mkdir

    def save_result(count):
        folder = path / "ce-results"
        folder.mkdir(exist_ok=True)
        (folder / "ADDRESSES.TMP").write_bytes(b"\x06NORMAL" + bytes(count * 8))

    lua.globals().save_result_file = save_result
    lua.globals().result_folder = (path / "ce-results").as_posix()
    lua.execute("""
      package.preload.lfs=function() return {
        attributes=function(p) return directory_mode(p) end,
        mkdir=function(p) return mkdir_local(p) end} end
      ce={pid=1234, words={}, regions={}, reads={}, waits=0, messages={}}
      ce.fl={Count=0, Address={}}
      ce.ms={LastScanType='stFirstScan',LastScanWasRegionScan=false,
        ScanOption='soExactValue',VariableType='vtSingle',LastScanValue='100',
        Hexadecimal=false,OnlyOneResult=false,IsUnique=false,FoundList=ce.fl,
        ScanresultFolder=result_folder}
      ce.ms.waitTillDone=function() ce.waits=ce.waits+1 end
      ce.ms.getProgress=function() return {ResultsFound=0} end -- CE frees its scan workers
      cheatEngineIs64Bit=function() return true end
      ce.save_result=function() save_result_file(ce.fl.Count) end
      getCurrentMemscan=function() return ce.ms end
      getOpenedProcessID=function() return ce.pid end
      enumMemoryRegions=function() return ce.regions end
      readInteger=function(addr)
        assert(ce.allowed[addr], 'READ_OUTSIDE_CONTRACT')
        ce.reads[#ce.reads+1]=addr
        return ce.words[addr]
      end
      print=function(message) ce.messages[#ce.messages+1]=message end
      function ce.populate()
        ce.allowed={}
        for i,o in ipairs(w.objects) do
          ce.fl.Address[i-1]=string.format('%X',o.addr)
          ce.regions[i]={BaseAddress=o.addr-0x28,RegionSize=0x100,
            State=o.mapped and 0x1000 or 0x10000,Protect=o.protect,
            AllocationBase=0x100000,Type=0x20000}
          for _,off in ipairs({-0x20,-0x10,-8,0,0x30,0x40,0x48,0x50}) do
            ce.allowed[o.addr+off]=true
          end
          for addr,word in pairs(o.memory) do ce.words[addr]=word end
        end
        ce.fl.Count=#w.objects
        ce.save_result()
      end
    """)
    return lua, w, api, path, reload


def test_direct_entry_exports_all_8003_occurrences_without_preparation(direct_env):
    lua, w, api, path, reload = direct_env
    records(w, 8002, good=(2,))
    lua.execute("""
      ce.populate()
      ce.fl.Address[8002]=ce.fl.Address[1]; ce.fl.Count=8003; ce.save_result()
      ce.words[w.objects[3].addr]=0x42280000 -- drift does not remove an occurrence
      ce.words[w.objects[4].addr-8]=nil -- a real failed lookup remains missing
      ce.words[w.objects[5].addr-0x20]=-1 -- CE signed DWORD becomes the same uint32 bits
    """)
    (path / "log").rmdir()  # no operator output-directory preparation
    result = api.export()
    loaded, options, manifest = load_replay(result.manifest_path, lua)
    assert result.outcome == "REPLAY_READY" and len(loaded) == 8003
    assert loaded[8003].addr == loaded[2].addr
    assert loaded[3].memory[loaded[3].addr] == 0x42280000
    assert loaded[4].memory[loaded[4].addr - 8] is None
    assert loaded[5].memory[loaded[5].addr - 0x20] == 0xFFFFFFFF
    assert options.population_mode == "full" and options.target_value_pattern == 0x42C80000
    assert options.scan_budget is None and options.max_candidates is None
    assert manifest["counts"]["duplicate_occurrences"] == manifest["counts"]["unavailable_words"] == 1
    assert manifest["source_snapshot_status"] == "CE_SEQUENTIAL_READ"
    assert manifest["ce_capture"]["atomic"] is False and manifest["acquisition_completeness"] == "UNKNOWN"
    assert manifest["capture_wall_ms"] >= 0 and manifest["export_wall_ms"] >= 0
    assert len(lua.globals().ce.reads) == 8003 * 8
    assert lua.globals().ce.waits == 1
    assert result.manifest_path in lua.globals().ce.messages[1]
    before = Path(result.manifest_path).read_bytes()
    second = reload().export()
    assert second.manifest_path != result.manifest_path
    assert Path(result.manifest_path).read_bytes() == before


@pytest.mark.parametrize("entry", ["AC5", "AC6"])
def test_direct_capture_replays_unchanged_algorithms(direct_env, entry):
    lua, w, api, _, _ = direct_env
    records(w, 129, good=(2,))
    lua.execute("ce.populate()")
    result = api.export()
    loaded, options, _ = load_replay(result.manifest_path, lua)
    if entry == "AC5":
        evaluate = lambda r: w.load("mvp0_offline_scoring.lua", None).run(r, options, w.load)
    else:
        evaluate = lambda r: w.load("mvp0_foundlist_collector.lua", None).run(
            options, lua.table_from({"records": r, "load_module": w.load}))
    actual = evaluate(loaded)
    assert actual.completed and actual.population_complete and actual.counts.ranked == 129
    assert plain(actual) == plain(evaluate(w.objects))


@pytest.mark.parametrize("value,hexadecimal,bits", [
    ("1120403456", False, 0x42C80000), ("42C80000", True, 0x42C80000), ("-1", False, 0xFFFFFFFF),
])
def test_direct_dword_target_comes_from_scan_settings(direct_env, value, hexadecimal, bits):
    lua, w, api, _, _ = direct_env
    records(w, 1)
    lua.execute("ce.populate(); ce.ms.VariableType='vtDword'")
    lua.globals().ce.ms.LastScanValue = value
    lua.globals().ce.ms.Hexadecimal = hexadecimal
    _, options, _ = load_replay(api.export().manifest_path, lua)
    assert options.target_value_pattern == bits and options.target_value_float is None


@pytest.mark.parametrize("mutation,reason", [
    ("ce.ms.LastScanType='stNextScan'", "First Scan"),
    ("ce.ms.ScanOption='soUnknownValue'", "Exact Value"),
    ("ce.ms.VariableType='vtDouble'", "Float or 4 Bytes"),
    ("ce.ms.Hexadecimal=true", "hexadecimal Float"),
    ("ce.ms.OnlyOneResult=true", "limited"),
    ("ce.fl.Count=9000", "count"),
    ("ce.ms.ScanresultFolder=ce.ms.ScanresultFolder..'/missing'", "address file unavailable"),
    ("ce.ms.FoundList=nil", "FoundList unavailable"),
    ("enumMemoryRegions=nil", "capability unavailable: enumMemoryRegions"),
    ("readInteger=nil", "capability unavailable: readInteger"),
    ("ce.ms.LastScanValue='value_expression()'", "literal Float"),
    ("ce.pid=0", "no already attached"),
    ("local read=readInteger; readInteger=function(a) ce.pid=4321; return read(a) end", "attachment"),
    ("local read=readInteger; readInteger=function(a) ce.fl.Address[0]='200128'; return read(a) end", "membership"),
])
def test_direct_unavailable_or_changed_source_never_delivers_partial_success(direct_env, mutation, reason):
    lua, w, api, path, _ = direct_env
    records(w, 3)
    lua.execute("ce.populate(); " + mutation)
    with pytest.raises(Exception, match=reason):
        api.export()
    assert not list((path / "log").iterdir())


@pytest.mark.parametrize("mutation,issue", [
    ("table.remove(ce.regions,2)", "replay_observations_or_settings_missing"),
    ("ce.fl.Address[3]=ce.fl.Address[0]; ce.fl.Count=4; ce.save_result(); "
     "local read=readInteger; readInteger=function(a) local v=read(a); "
     "if a==w.objects[1].addr then ce.words[a]=7 end; return v end", "conflicting_observations"),
    ("local calls=0; enumMemoryRegions=function() calls=calls+1; "
     "if calls==1 then return ce.regions end; "
     "local t={}; for i,r in ipairs(ce.regions) do local c={}; "
     "for k,v in pairs(r) do c[k]=v end; t[i]=c end; t[1].Protect=2; return t end", "source_error_reported"),
])
def test_direct_incomplete_observations_remain_visible_and_not_replayable(direct_env, mutation, issue):
    lua, w, api, _, _ = direct_env
    records(w, 3)
    lua.execute("ce.populate(); " + mutation)
    result = api.export()
    manifest, exported = load_inventory(result.manifest_path)
    assert result.outcome == "INCOMPLETE" and len(exported) == lua.globals().ce.fl.Count
    assert manifest["issues"][issue]
    if issue == "source_error_reported":
        assert manifest["ce_capture"]["mapping_changes"]["1"]["after"]["protect"] == 2
    with pytest.raises(ValueError, match="not replay-ready"):
        load_replay(result.manifest_path, lua)


def test_direct_empty_first_scan_is_replayable(direct_env):
    lua, _, api, _, _ = direct_env
    lua.execute("ce.populate()")
    loaded, _, manifest = load_replay(api.export().manifest_path, lua)
    assert len(loaded) == 0 and manifest["outcome"] == "REPLAY_READY"


def test_complete_8003_population_preserves_every_observation_and_occurrence(export_env):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w, 8002)
    lua.execute("s.records[#s.records+1]=s.records[2]; s.expected_source_count=#s.records")
    lua.execute("s.evaluation_options.scan_budget=8000; s.evaluation_options.max_candidates=100")
    before = plain(s)
    result = api.export(s)
    manifest, restored = load_inventory(result.manifest_path)
    assert result.outcome == "REPLAY_READY" and result.exported_count == 8003
    assert restored == [plain(s.records[i]) for i in range(1, 8004)]
    assert manifest["counts"]["duplicate_occurrences"] == 1
    assert manifest["acquisition_completeness"] == "UNKNOWN"
    assert manifest["records"]["count"] == 8003
    assert result.records_bytes > 0 and result.export_wall_ms >= 0
    assert plain(s) == before


@pytest.mark.parametrize("mutation,outcome", [
    ("", "REPLAY_READY"),
    ("s.records={}; s.expected_source_count=0", "REPLAY_READY"),
    ("s.records={{addr='00100128'},{addr='00100128'}};s.expected_source_count=2", "ADDRESS_ONLY"),
    ("s.records[2]={addr=false}", "INCOMPLETE"),
    ("s.records[2]={}", "INCOMPLETE"),
    ("s.records[2].memory=nil", "INCOMPLETE"),
    ("s.records[2].mapped=nil", "INCOMPLETE"),
    ("s.expected_source_count=4", "INCOMPLETE"),
    ("s.records[1].memory[s.records[1].addr-8]=nil", "INCOMPLETE"),
    ("s.evaluation_options={}", "INCOMPLETE"),
    ("s.population_basis='BOUNDED_OR_FILTERED'", "INCOMPLETE"),
    ("s.population_basis=nil", "INCOMPLETE"),
    ("s.acquisition_completeness='INCOMPLETE'", "INCOMPLETE"),
    ("s.records[2]={addr=s.records[1].addr,mapped=false,protect=4,memory=s.records[1].memory}", "INCOMPLETE"),
    ("s.records[2].memory[s.records[1].addr]=3", "INCOMPLETE"),
    ("s.source_snapshot_status='UNAVAILABLE'", "INCOMPLETE"),
    ("s.source_snapshot_status=nil", "INCOMPLETE"),
    ("s.source_error='supplied enumeration was interrupted'", "INCOMPLETE"),
    ("s.source_category='UNKNOWN'", "INCOMPLETE"),
])
def test_explicit_dispositions(export_env, mutation, outcome):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w)
    lua.execute(mutation)
    result = api.export(s)
    manifest, restored = load_inventory(result.manifest_path)
    assert result.outcome == manifest["outcome"] == outcome
    assert len(restored) == len(s.records)
    if outcome != "REPLAY_READY":
        with pytest.raises(ValueError, match="not replay-ready"):
            load_replay(result.manifest_path, lua)
    else:
        loaded, opts, _ = load_replay(result.manifest_path, lua)
        opts.population_mode = "full"
        completed = w.load("mvp0_offline_scoring.lua", None).run(loaded, opts, w.load)
        assert completed.completed and completed.population_complete
        if not restored:
            assert completed.status == "EMPTY" and completed.counts.ranked == 0


def test_declared_unavailable_word_is_missing_not_zero(export_env):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w)
    lua.execute("""
      local r=s.records[2]; r.memory[r.addr-0x20]=nil; r.unavailable={[r.addr-0x20]=true}
    """)
    result = api.export(s)
    restored, opts, m = load_replay(result.manifest_path, lua)
    opts.population_mode = "full"
    actual = w.load("mvp0_offline_scoring.lua", None).run(restored, opts, w.load)
    original = w.load("mvp0_offline_scoring.lua", None).run(s.records, opts, w.load)
    assert plain(actual) == plain(original)
    assert restored[2].memory[restored[2].addr - 0x20] is None
    assert m["counts"]["unavailable_words"] == 1
    assert m["counts"]["undeclared_missing_words"] == 0


def test_freeze_and_source_change_are_explicit(export_env):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w)
    before = [plain(s.records[i]) for i in range(1, 4)]
    lua.execute("""
      local original=md5file
      md5file=function(path)
        s.records[1].memory[s.records[1].addr]=7
        s.records[4]=s.records[2]
        return original(path)
      end
    """)
    result = api.export(s)
    m, exported = load_inventory(result.manifest_path)
    assert exported == before and result.exported_count == 3
    assert result.outcome == "INCOMPLETE"
    assert m["source_snapshot_status"] == "CHANGED_DURING_EXPORT"
    assert not m["source_unchanged_at_checks"] and m["issues"]["source_changed_during_export"]
    with pytest.raises(ValueError, match="not replay-ready"):
        load_replay(result.manifest_path, lua)


def test_independent_labels_and_source_intervals_are_preserved_separately(export_env):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w)
    lua.execute("""
      s.observation_started_utc='2020-01-01T00:00:00Z'
      s.observation_finished_utc='2020-01-01T00:00:01Z'
      s.capture_wall_ms=1000
      s.configuration_id='fixture-config'; s.algorithm_revision='fixture-revision'
      s.source_id='fixture-quote-"-newline-\\n-unicode-测试'
      labels={independent=true,basis='independent fixture oracle',
        outcomes={[1]='NEGATIVE',[2]='POSITIVE',[3]='UNKNOWN'}}
    """)
    original = plain(s), plain(lua.globals().labels)
    result = api.export(s, lua.globals().labels)
    m, _ = load_inventory(result.manifest_path)
    truth = json.loads((Path(result.manifest_path).parent / m["labels_file"]).read_text(encoding="utf-8"))
    assert truth["outcomes"] == {"1": "NEGATIVE", "2": "POSITIVE", "3": "UNKNOWN"}
    assert truth["dataset_id"] == m["dataset_id"] and truth["records_md5"] == m["records"]["hash"]
    assert m["source_category"] == "ARTIFICIAL_FIXTURE" and m["capture_wall_ms"] == 1000
    assert m["source_id"] == s.source_id and m["observation_finished_utc"] == s.observation_finished_utc
    assert result.output_bytes == sum(p.stat().st_size for p in Path(result.manifest_path).parent.iterdir())
    loaded, options, _ = load_replay(result.manifest_path, lua)
    assert "labels" not in plain(options) and "known_true_addr" not in plain(options)
    assert all(set(plain(loaded[i])) == {"addr", "mapped", "protect", "memory"} for i in range(1, 4))
    assert original == (plain(s), plain(lua.globals().labels))


@pytest.mark.parametrize("entry", ["AC5", "AC6"])
def test_same_frozen_input_bounded_full_and_truth_isolation(export_env, entry):
    lua, w, api, _, _ = export_env
    s = snapshot(lua, w, 129)
    result = api.export(s)
    loaded, _, m = load_replay(result.manifest_path, lua)
    labels = Path(result.manifest_path).parent / m["labels_file"]
    truth = json.loads(labels.read_text())
    assert truth["status"] == "UNKNOWN" and truth["outcomes"] == {}
    assert truth["dataset_id"] == m["dataset_id"] and truth["records_md5"] == m["records"]["hash"]
    # A malicious/invalid label file is never even parsed by the replay loader.
    labels.write_text("not JSON; do not execute; unknown is not negative", encoding="utf-8")
    again, _, _ = load_replay(result.manifest_path, lua)
    assert plain(again) == plain(loaded)
    evaluate = (lambda r, o: w.load("mvp0_offline_scoring.lua", None).run(r, o, w.load)) if entry == "AC5" else (
        lambda r, o: w.load("mvp0_foundlist_collector.lua", None).run(
            o, lua.table_from({"records": r, "load_module": w.load})))
    frozen = plain(loaded)
    for mode in ("bounded", "full"):
        opts = lua.table_from({"population_mode": mode, "target_value_pattern": 0x42C80000,
                               "target_value_float": 100.0})
        start = time.perf_counter()
        actual = evaluate(loaded, opts)
        elapsed = time.perf_counter() - start
        assert elapsed >= 0  # evaluation only: export/loading/label work excluded
        assert actual.population_mode == mode and actual.completed
        assert actual.counts.supplied == 129 and actual.counts.ranked == (129 if mode == "full" else 20)
        assert actual.population_complete is (mode == "full")
        assert plain(actual) == plain(evaluate(s.records, opts))
        assert plain(loaded) == frozen


@pytest.mark.parametrize("mutation", [
    "s.authorized_owned=false", "s.permission_disposition=nil", "s.records[2]=nil", "setmetatable(s.records,{})",
    "setmetatable(s.records[1],{})", "s.records[1].memory[1]=0", "s.records[1].truth=true",
    "s.evaluation_options.known_true_addr=123", "s.evaluation_options=false",
    "s.evaluation_options.population_mode='full';s.evaluation_options.scan_budget=1",
    "s.evaluation_options.max_candidates=false", "s.population_basis=false",
    "s.records[1].memory[s.records[1].addr]=0/0", "s.records[1].mapped=0",
    "s.records[1].unavailable={[s.records[1].addr]=true}",
])
def test_invalid_requests_fail_before_files(export_env, mutation):
    lua, w, api, path, _ = export_env
    s = snapshot(lua, w)
    lua.execute(mutation)
    with pytest.raises(Exception, match="EXPORT_FAILED"):
        api.export(s)
    assert not list((path / "log").iterdir())


def test_repeat_and_module_reload_never_overwrite(export_env):
    lua, w, api, path, reload = export_env
    s = snapshot(lua, w)
    lua.execute("os.date=function(format) return 'fixed-time' end")
    results = [api.export(s)]
    before = {p: p.read_bytes() for p in (path / "log").iterdir()}
    results.extend([api.export(s), reload().export(s)])
    assert len({r.dataset_id for r in results}) == 3
    assert all(p.read_bytes() == data for p, data in before.items())
    assert all(r.outcome == "REPLAY_READY" for r in results)


@pytest.mark.parametrize("phase", ["write", "close", "hash", "publish"])
def test_io_failure_has_no_success_manifest_or_stale_result(export_env, phase):
    lua, w, api, path, _ = export_env
    s = snapshot(lua, w)
    first = api.export(s)
    original = Path(first.manifest_path).read_bytes()
    lua.globals().fault_phase = phase
    lua.execute("""
      if fault_phase=='hash' then md5file=function() error('HASH_FAILURE') end
      elseif fault_phase=='publish' then os.rename=function() return nil,'PUBLISH_FAILURE' end
      else
        local open=io.open
        io.open=function(path,mode)
          local f,e,c=open(path,mode)
          if mode=='wb' and path:match('records.jsonl$') then
            return {write=function(_,text)
                if fault_phase=='write' then return nil,'WRITE_FAILURE' end
                return f:write(text)
              end,
              close=function() f:close(); if fault_phase=='close' then return nil,'CLOSE_FAILURE' end
                return true end}
          end
          return f,e,c
        end
      end
    """)
    with pytest.raises(Exception, match="EXPORT_FAILED"):
        api.export(s)
    assert Path(first.manifest_path).read_bytes() == original
    assert len(list((path / "log").glob("*.manifest.json"))) == 1
    assert len(list((path / "log").glob("*.reserved"))) == 2


@pytest.mark.parametrize("damage", ["bytes", "count", "path", "options", "duplicate_key", "pending"])
def test_loader_rejects_tampering_without_executing_data(export_env, damage):
    lua, w, api, _, _ = export_env
    result = api.export(snapshot(lua, w))
    path = Path(result.manifest_path)
    m = json.loads(path.read_text())
    if damage == "bytes":
        records_path = path.parent / m["records"]["file"]
        records_path.write_text("os.execute('invalid-data')", encoding="utf-8")
    elif damage == "count": m["counts"]["source_count"] += 1
    elif damage == "path": m["records"]["file"] = "../outside.jsonl"
    elif damage == "options": m["evaluation_options"]["known_true_addr"] = 123
    elif damage == "pending":
        pending = path.with_suffix(".pending")
        path.rename(pending)
        path = pending
    if damage == "duplicate_key":
        path.write_text('{"format":"MVP0_MANUAL_EXPORT","format":"OTHER"}', encoding="utf-8")
    elif damage != "pending": path.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError):
        load_replay(path, lua)
