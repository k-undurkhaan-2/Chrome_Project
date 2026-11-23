-- Synthetic-only public-loader host. No real CE/global process API is exposed.
return function(w, sources, missing_path)
  local env={}
  for k,v in pairs(_G) do env[k]=v end
  for k,v in pairs(w.ce) do env[k]=v end
  env._G=env
  -- Explicit fixture opt-in only; preserve every original return and its arity.
  if w.capture_loader_diagnostics then
    env.pcall=function(...)
      local values=table.pack(pcall(...))
      if values[1]==false then w.raw_start_error=tostring(values[2]) end
      return table.unpack(values,1,values.n)
    end
  end
  env.loadfile=function(path, mode, scope)
    local name=path:match('[^/\\]+$')
    if name=='ce_mvp_config.local.lua' then
      if w.config_missing then
        if not w.capture_loader_diagnostics then return loadfile(missing_path,mode,{}) end
        local values=table.pack(loadfile(missing_path,mode,{}))
        w.loader_observation={path=missing_path,error=values[2],return_arity=values.n}
        return table.unpack(values,1,values.n)
      end
      return function() return w.cfg end
    end
    if name=='ce_mvp_adapter.lua' then
      return function()
        local m=assert(load(sources[name],'@'..path,mode,scope))()
        local new=m.new
        m.new=function(cfg,ce,loader) return new(cfg,ce,loader,'synthetic') end
        return m
      end
    end
    return load(assert(sources[name]),'@'..path,mode,scope)
  end
  local api=assert(load(sources['ce_mvp.lua'],'@SYNTHETIC/ce_mvp.lua','t',env))()
  return api,env
end
