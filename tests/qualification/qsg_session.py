"""One sealed nine-instance/nine-Start synthetic qualification session."""
from copy import deepcopy
import xml.etree.ElementTree as ET

from ce_qualification.evidence import Stream, SidecarStore, digest
from ce_qualification.target import TargetRecorder, Instance, SyntheticMemory
from qsg_support import Model, policy, table, layout, plain, ROOT, SOURCES


class FullSession(Model):
    def __init__(self, directory, *, evidence_version=2):
        p=policy(); first=deepcopy(p['targets'][0]); p['targets']=[]
        for i in range(9):
            t=deepcopy(first); t['identity']['pid']=101+i; t['identity']['creation']=f'{0x10000005B+i:016X}'
            t['allocation_id']=f'allocation-{i}'
            t['phases']=([f'L{x:02}' for x in range(2,9)] if i==0 else ['L09-'+['zero','ambiguous','129_plus','incomplete','invalid'][i-1]] if i<=5 else ['L10'] if i==6 else ['L11'])
            if i==8: t['identity']['designation']='B'
            p['targets'].append(t)
        self.target_index=0; self.alive_count=1
        super().__init__(directory,phase='L02',policy_value=p)
        if evidence_version not in (1, 2):
            raise ValueError('EVIDENCE_VERSION')
        self.evidence_version = evidence_version
        self.sidecar_directory = self.directory / 'l12-sidecars'
        self.sidecars = SidecarStore(self.sidecar_directory, p['session_id']) if evidence_version == 2 else None
        self.w.capture_loader_diagnostics = evidence_version == 2
        self.b_stream=Stream(p['session_id'],'target-B')
        def start_request():
            self.starts+=1
            return table(self.lua,{'run_id':f'run-{self.starts}','writer_id':f'writer-{self.starts}',
                'epoch':f'epoch-{self.starts}','target':self.target_index,'phase':self.phase})
        self.host.start_request=self.wrap(start_request)

    def current_scope(self):
        if self.scope_override is not None: return deepcopy(self.scope_override)
        return {'scope':deepcopy(self.policy['targets'][self.target_index]),'alive':bool(self.w.alive),
            'alive_instances':self.alive_count,'ce_token':f'{int(self.w.opened or self.w.pid)}:{0x100000000+int(self.w.creation):016X}',
            'retired':{str(a):True for a in self.target.retired},'pages':{str(p):True for p in self.target.memory.pages}}

    def new_target(self,index,phase,mode):
        self.target_index=index; self.phase=phase; self.alive_count=1
        scope=self.policy['targets'][index]
        self.target=TargetRecorder(self.target_stream,Instance(**scope['identity']),SyntheticMemory(int(scope['base'])),scope['allocation_id'],enabled=True)
        self.target.context(f'run-{self.starts+1}',phase)
        plan=layout.plan(mode); self.target.apply(plan)
        self.w.use_layout(table(self.lua,plan['pages']),table(self.lua,plan['words']))
        self.w.pid=scope['identity']['pid']; self.w.creation=int(scope['identity']['creation'],16)&0xFFFFFFFF
        self.w.alive=True; self.w.cfg.target_pid=self.w.pid; self.w.cfg.diagnostics.session_token=f'SYNTHETIC-start-{self.starts+1}'

    def execute(self):
        self.start(); self.until('SCREENING'); self.phase_to('L03'); self.until('WRITING'); self.phase_to('L04')
        self.until('MONITORING'); self.phase_to('L05'); self.monitors(20); self.phase_to('L06')
        self.target.apply(layout.transition('drift','baseline_unique',0)); self.w.locate(0x100128).memory[0x100128]=0x42280000
        self.monitors(3); self.phase_to('L07'); self.relocate(); self.until('RESCAN_BACKOFF'); self.until('MONITORING')
        self.phase_to('L08'); self.w.alive=False; self.w.step(); self.stop(); self.target.shutdown()
        for i,(case,mode) in enumerate(zip(['zero','ambiguous','129_plus','incomplete','invalid'],
            ['zero_match','ambiguous','over_limit','incomplete_structure','invalid_structure']),1):
            self.new_target(i,'L09-'+case,mode); self.start()
            for _ in range(1000):
                self.w.step()
                if not self.api.status().running or self.api.status().state=='RESCAN_BACKOFF': break
            self.stop(); self.target.shutdown()
        self.new_target(6,'L10','baseline_unique'); self.w.cfg.diagnostics.cleanup_start_probe=True
        assert self.start(loader=True)==(True,None); self.until('MONITORING')
        assert self.api.start()==(False,'ALREADY_RUNNING')
        self.stable_stop()
        plan=layout.plan('zero_match'); self.w.use_layout(table(self.lua,plan['pages']),table(self.lua,plan['words']))
        self.target.memory.write_word(0x100128,0x42280000)
        self.w.cfg.diagnostics.session_token='SYNTHETIC-l10-second'; self.w.cfg.diagnostics.cleanup_start_probe=False
        assert self.api.start()==(True,None); self.w.step(50); self.stable_stop()
        self.load_and_rejections(); self.target.shutdown()
        self.new_target(7,'L11','zero_match')
        dest=self.policy['targets'][8]
        b=TargetRecorder(self.b_stream,Instance(**dest['identity']),SyntheticMemory(int(dest['base'])),dest['allocation_id'],enabled=True)
        b.context(f'run-{self.starts+1}','L11'); b.apply(layout.plan('baseline_unique')); self.alive_count=2
        self.start(); self.until('RESCAN_BACKOFF')
        before=plain(self.api.evidence()); self.w.opened=dest['identity']['pid']; self.w.step(); after=plain(self.api.evidence())
        self.recorder.core_stream.emit('target_switch',{'from':self.target.identity,'to':b.identity,
            'before':before['counters'],'after':after['counters'],'before_sequence':before['last_sequence'],'after_sequence':after['last_sequence']},
            run_id=self.lease['run_id'],scenario='L11')
        b.sample(0x100128,'switch-destination'); self.stop(); self.target.shutdown(); b.shutdown()
        return self.bundle()

    def stable_stop(self):
        self.stop(); before=plain(self.api.evidence())['counters']; self.w.step(60)
        after=plain(self.api.evidence())['counters']
        self.recorder.core_stream.emit('phase_boundary',{'phase':'after_stop','completed_wait_intervals':3,'before':before,'after':after},
            run_id=self.lease['run_id'],scenario='L10')

    def load_and_rejections(self):
        # Reuse the public loader's actual stopped prior-run evidence for L12.
        guard_module=self.lua.execute((ROOT/'tests/fixtures/ce_mvp_prestart_guard.lua').read_text())
        guard=guard_module.new(self.env,'synthetic'); guard.install()
        self.env.syntaxcheck=True; chunks=0
        for script in ET.parse(ROOT/'src/ce_mvp.CT').findall('.//AssemblerScript'):
            for chunk in script.text.split('{$lua}')[1:]:
                self.lua.eval("function(s,e) return assert(load(s,'@SYNTHETIC/ct','t',e))() end")(chunk.split('{$asm}')[0],self.env); chunks+=1
        # Inert singleton reload, accessors and status execute under the guard.
        self.lua.eval("function(s,e) return assert(load(s,'@SYNTHETIC/ce_mvp.lua','t',e))() end")(SOURCES['ce_mvp.lua'],self.env)
        self.api.evidence(); self.api.status(); self.env.syntaxcheck=False
        counts=plain(guard.snapshot())['attempted_calls']; guard.restore()
        self.recorder.core_stream.emit('load_observation',{'state':self.api.status().state,'attempted_calls':counts,
            'guard_restored':True,'ct_lua_syntax_blocks':chunks,'config_loaded':False,'ce_embedded_lua':'NOT_RUN'},run_id='load',scenario='L01')
        for sub in ['MISSING','DISABLED','INVALID']:
            guard=guard_module.new(self.env,'synthetic'); guard.install()
            before=plain(guard.snapshot())['attempted_calls']; retained=plain(self.api.evidence())
            self.w.config_missing=sub=='MISSING'; self.w.cfg.write_enabled=sub!='DISABLED'; self.w.cfg.scan.scan_budget=65537 if sub=='INVALID' else 128
            observation = None
            if self.sidecars is None:
                accepted,error=self.api.start()
            else:
                self.w.raw_start_error = None; self.w.loader_observation = None
                # Encode inside Lua before Lupa can decode a split UTF-8 return.
                observed = self.lua.eval('''function(api,w,path)
                    local function hex(s)
                        return (s:gsub('.',function(c) return string.format('%02x',string.byte(c)) end))
                    end
                    local values=table.pack(api.start())
                    local loader=w.loader_observation
                    return {accepted=values[1],return_arity=values.n,
                        path_utf8_hex=hex(path),returned_error_hex=hex(values[2]),
                        full_error_hex=hex(w.raw_start_error or values[2]),
                        loader_error_hex=loader and hex(loader.error) or false,
                        loader_return_arity=loader and loader.return_arity or 0,
                        full_error_source=w.raw_start_error and 'PCALL_ERROR' or 'API_RETURN'}
                end''')(self.api, self.w, str(self.directory / 'missing/ce_mvp_config.local.lua'))
                observation = plain(observed)
                accepted = observation.pop('accepted')
                observation.update(schema='ce.loader-diagnostic.v2', origin='SYNTHETIC',
                                   source='g1_mock_loader', truncation_bytes=240)
                error = bytes.fromhex(observation['returned_error_hex'])
            after=plain(guard.snapshot())['attempted_calls']; guard.restore()
            self.recorder.legacy.rejection(run_id='rejected-'+sub,scenario='L12-'+sub,accepted=accepted,diagnostic=error,
                guard_before=before,guard_after=after,restored=not guard.snapshot().installed,
                retained_before=retained,retained_after=plain(self.api.evidence()),
                sidecars=self.sidecars,diagnostic_observation=observation)
        self.w.config_missing=False; self.w.cfg.write_enabled=True; self.w.cfg.scan.scan_budget=128

    def bundle(self):
        bundle=super().bundle(); bundle['target']+=deepcopy(self.b_stream.rows)
        if self.sidecars is not None:
            bundle['schema'] = 'qsg.bundle.v2'
            bundle['sidecars'] = self.sidecars.seal(bundle['ce'])
        self.bundle_seal = digest(bundle)
        return bundle
