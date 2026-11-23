-- L01 test equipment only. Loading is inert; install() requires deliberate use.
-- Intercept attempted MVP API calls before Start and reject before forwarding.
-- This is an API-surface observation, not an OS-wide process/memory audit.
local M={}
function M.new(ce, source)
  local originals, wrappers, counts, installed={}, {}, {}, false
  local names={'openProcess','createMemScan','readInteger','readFloat','writeFloat',
    'createTimer','executeCodeLocalEx','createMemoryStream'}
  local api={}
  function api.install()
    assert(not installed,'L01_GUARD_ALREADY_INSTALLED')
    for _,name in ipairs(names) do assert(type(ce[name])=='function','L01_API_MISSING:' .. name) end
    for _,name in ipairs(names) do
      originals[name]=ce[name]; counts[name]=0
      wrappers[name]=function()
        counts[name]=counts[name]+1; error('L01_UNEXPECTED_API:' .. name,0)
      end
      ce[name]=wrappers[name]
    end
    installed=true
  end
  function api.snapshot()
    local out={source=source or 'CE',event_type='prestart_api_guard',installed=installed,attempted_calls={}}
    for k,v in pairs(counts) do out.attempted_calls[k]=v end
    return out
  end
  function api.restore()
    if not installed then return end
    for _,name in ipairs(names) do assert(ce[name]==wrappers[name],'L01_API_CHANGED:' .. name) end
    for _,name in ipairs(names) do ce[name]=originals[name] end
    installed=false
  end
  return api
end
return M
