-- Pure prediction only; no process, file, scan, write, or training operations.
-- conditional_choice_linear_ridge_0.1, frozen at:
-- 36eabba2a2cdbd4b26fc5bf09532f9eb51eb9744
-- candidate-model.json SHA-256 (UTF-8/LF):
-- b8ff942bca7aaac2160d54b69c5999b259ba7b974aebbf057f792ceadb25ed50
-- SPDX-License-Identifier: GPL-3.0-only
local M = {}
local dimensions, temperature, tie_tolerance = 86, 8.0, 1e-10

-- Exact frozen linear coefficients in FEATURE_NAMES order. All 86 frozen
-- quadratic coefficients are zero. The first 13 component weights are zero.
-- Private constants: no model selection, fitting, or caller-supplied weights.
local linear = {
  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
  -0.04185142378035598, -0.06771922802089048, -0.00622352891859302,
  0.5936235605996362, -0.006652864232876807, -0.0174992913533556,
  -0.004730253282979716,
  0.25507185985768654, 0.2007230796201299, 0.1494841270469366,
  -0.2647846663971785, 0.24774728515570832, 0.2553876151893862,
  0.2521325483974782,
  0.33796579499960666, 0.28000856423667614, 0.25158245480022123,
  -0.2232097853558555, 0.27053789626150115, 0.30687980687150856,
  0.2866850587724443,
  -0.10246351527698003, -0.12998237080131989, 0.43895383717851355,
  -0.13690432679890066, -0.12160376233114913, -0.3258254547191962,
  -0.2556864793331882, 0.07280079193682956, -0.1647449505897651,
  -0.13057200151681797, -0.32962447966291447, 0.07181435672703122,
  -0.22810623121838572, -0.2172269940170922, -0.3968732806501386,
  0.045104078635558, 0.025667409782162812, 0.2863329654200692,
  -0.1448701327311621, -0.4303849686893388, -0.43014441175294876,
  0.0067934578936346, 0.0055779691786561, 0.04354872802473873,
  0.010807698746894799, -0.017956126731847256, -0.01361096201914694,
  -0.33823417805078154, -0.025735276688472766, 0.07081006706304578,
  0.0842340545181087, 0.06667390951150501, -0.025336592662750075,
  0.059488545349060534, 0.09130654954671819, 0.05790062048367999,
  0.018638917038562224, 0.0026263764087268754, 0.03223596965883441,
  -0.5588445007623472, -0.8364179236442725, -0.8865476622864843,
  -0.24406618270574393, -0.5026997565867246, 0.14617275893414625,
}

local function finite(v)
  return type(v) == 'number' and v == v and math.abs(v) ~= math.huge
end

local function plain_table(t)
  assert(type(t) == 'table' and getmetatable(t) == nil, 'expected a plain table')
end

local function array_size(t)
  plain_table(t)
  local count = 0
  for k in pairs(t) do
    assert(type(k) == 'number' and k % 1 == 0 and k >= 1, 'invalid array index')
    count = count + 1
  end
  for i = 1, count do assert(t[i] ~= nil, 'sparse array') end
  return count
end

local function numbers(t, count)
  assert(array_size(t) == count, 'invalid dimensions')
  for i = 1, count do assert(finite(t[i]), 'expected finite numbers') end
end

function M.features(words, components)
  -- Seven fixed slots: f08, f18, f20, f58, f68, f70, f78. nil means missing;
  -- do not use #words or ipairs(words), which would lose trailing missingness.
  -- Components follow mvp0_residual_rank.COMPONENTS, unchanged (13 columns).
  plain_table(words)
  for k, v in pairs(words) do
    assert(type(k) == 'number' and k % 1 == 0 and k >= 1 and k <= 7,
      'invalid observation index')
    assert(math.type(v) == 'integer' and v >= 0 and v < 4294967296,
      'observations must be uint32 or missing')
  end
  numbers(components, 13)
  local row = {}
  for i = 1, 13 do row[#row + 1] = components[i] / 64.0 end
  for kind = 1, 4 do
    for i = 1, 7 do
      local v = words[i]
      local yes = (kind == 1 and v == nil) or (kind == 2 and v == 0)
        or (kind == 3 and v ~= nil and v > 0 and v % 4 == 0)
        or (kind == 4 and v ~= nil and v > 0 and v % 8 == 0)
      row[#row + 1] = yes and 1.0 or 0.0
    end
  end
  local low, high
  for i = 1, 7 do
    local v = words[i]
    if v ~= nil then
      low = low and math.min(low, v) or v
      high = high and math.max(high, v) or v
    end
  end
  local span = low and high - low or 0
  for kind = 1, 2 do
    for i = 1, 6 do
      for j = i + 1, 7 do
        local a, b = words[i], words[j]
        local d = a ~= nil and b ~= nil and math.abs(a - b) or nil
        local value = 0.0
        if d ~= nil then
          if kind == 1 then value = span ~= 0 and d / span or 0.0
          else value = math.log(1 + d, 2) / 32 end
        end
        row[#row + 1] = value
      end
    end
  end
  local fs, ts, contrast = 0.0, 0.0, 0.0
  if words[1] ~= nil and words[2] ~= nil and words[3] ~= nil
      and words[5] ~= nil and words[6] ~= nil and words[7] ~= nil then
    fs = math.max(words[1], words[2], words[3]) - math.min(words[1], words[2], words[3])
    ts = math.max(words[5], words[6], words[7]) - math.min(words[5], words[6], words[7])
    local cross = 0
    for i = 1, 3 do
      for j = 5, 7 do cross = cross + math.abs(words[i] - words[j]) end
    end
    contrast = cross ~= 0 and cross / (cross + 3 * (fs + ts)) or 0.0
    fs, ts = span ~= 0 and fs / span or 0.0, span ~= 0 and ts / span or 0.0
  end
  row[#row + 1], row[#row + 2], row[#row + 3] = fs, ts, contrast
  return row
end

function M.predict(scores, rows)
  -- Caller supplies the complete, aligned eligible population and its existing
  -- baseline results. Prediction never applies the training competitor window.
  local count = array_size(scores)
  assert(count > 0 and array_size(rows) == count, 'nonempty aligned population required')
  numbers(scores, count)
  local predicted = {}
  for i = 1, count do
    numbers(rows[i], dimensions)
    -- Neumaier compensation approximates the frozen Python math.fsum without
    -- changing the formula. Parity tolerance is documented in the trial report.
    local total, correction = 0.0, 0.0
    for j = 1, dimensions do
      local term = linear[j] * rows[i][j]
      local next_total = total + term
      if math.abs(total) >= math.abs(term) then
        correction = correction + ((total - next_total) + term)
      else
        correction = correction + ((term - next_total) + total)
      end
      total = next_total
    end
    predicted[i] = scores[i] / temperature + (total + correction)
    assert(finite(predicted[i]), 'nonfinite prediction')
  end
  return predicted
end

function M.leaders(scores)
  local count = array_size(scores)
  assert(count > 0, 'nonempty scores required')
  numbers(scores, count)
  local best = scores[1]
  for i = 2, count do best = math.max(best, scores[i]) end
  local indices = {}
  for i = 1, count do
    local tied
    if math.type(best) == 'integer' and math.type(scores[i]) == 'integer' then
      -- Distinct integers are at least one apart. Avoid Lua 5.3 subtraction
      -- overflow at int64 extremes while preserving the frozen difference test.
      tied = scores[i] == best
    else
      tied = best - scores[i] <= tie_tolerance
    end
    if tied then indices[#indices + 1] = i end
  end
  -- Lua indices are one-based. Multiple indices mean unresolved ambiguity.
  return indices
end

return M
