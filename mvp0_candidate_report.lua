-- Route B / MVP-0 candidate scoring report for Cheat Engine Lua
--
-- Usage example inside Cheat Engine Lua Engine:
--
-- dofile('mvp0_candidate_report.lua')
--
-- local input = MVP0.make_input({
--   0x28A061C8958,
--   0x28A06E2F394,
--   0x28A0730B620,
--   0x28A077B6710,
--   0x28A077B692C,
-- }, 0x42C80000, { target_value_float = 100.0, session_id = 'session-3' })
--
-- local result = MVP0.run(input)
-- print(result.report_text)

local MVP0 = {}

MVP0.CONFIG = {
  value_offset = 0x28,
  offsets = {
    f08 = 0x08,
    f18 = 0x18,
    f20 = 0x20,
    f28 = 0x28,
    f58 = 0x58,
    f68 = 0x68,
    f70 = 0x70,
    f78 = 0x78,
  },
  suspicious = {
    [0x00000000] = true,
    [0x3F800000] = true,
    [0xBF800000] = true,
    [0x42C80000] = true,
    [0x43300000] = true,
    [0x43320000] = true,
    [0x43800000] = true,
  },
  weights = {
    target_match = 10,
    nonzero_field = 2,
    not_floatlike_field = 2,
    status_nonzero = 3,
    status_small_int = 4,
    status_not_floatlike = 2,
    penalty_empty_front = 8,
    penalty_empty_tail = 8,
    penalty_floatlike_3plus = 10,
    penalty_floatlike_5plus = 15,
    penalty_value_copy = 6,
  },
  confidence = {
    high_gap = 10,
    medium_gap = 5,
  },
  recommendation = {
    accept_min_score = 30,
    review_min_score = 20,
  },
}

local function u32(n)
  if n == nil then
    return nil
  end
  if n < 0 then
    return n + 0x100000000
  end
  return n
end

local function hex_u32(n)
  if n == nil then
    return "nil"
  end
  return string.format("0x%08X", u32(n))
end

local function hex_u64(n)
  if n == nil then
    return "nil"
  end
  return string.format("0x%X", n)
end

local function read_u32(addr)
  return u32(readInteger(addr))
end

local function read_f32(addr)
  return readFloat(addr)
end

local function is_suspicious_float_like(x)
  return MVP0.CONFIG.suspicious[u32(x)] == true
end

local function is_small_int_like(x)
  x = u32(x)
  return x ~= 0 and x < 0x1000
end

local function count_suspicious(values)
  local count = 0
  for _, v in ipairs(values) do
    if is_suspicious_float_like(v) then
      count = count + 1
    end
  end
  return count
end

local function has_flag(scored_candidate, wanted_flag)
  for _, flag in ipairs(scored_candidate.flags) do
    if flag == wanted_flag then
      return true
    end
  end
  return false
end

function MVP0.make_input(candidate_value_addrs, target_value_pattern, opts)
  opts = opts or {}
  return {
    candidate_value_addrs = candidate_value_addrs,
    target_value_pattern = u32(target_value_pattern),
    target_value_float = opts.target_value_float,
    session_id = opts.session_id,
  }
end

function MVP0.build_candidate(value_addr)
  local c = {}
  local off = MVP0.CONFIG.offsets

  c.value_addr = value_addr
  c.base_addr = value_addr - MVP0.CONFIG.value_offset

  c.f08 = read_u32(c.base_addr + off.f08)
  c.f18 = read_u32(c.base_addr + off.f18)
  c.f20 = read_u32(c.base_addr + off.f20)
  c.f28 = read_u32(c.base_addr + off.f28)
  c.f58 = read_u32(c.base_addr + off.f58)
  c.f68 = read_u32(c.base_addr + off.f68)
  c.f70 = read_u32(c.base_addr + off.f70)
  c.f78 = read_u32(c.base_addr + off.f78)
  c.f28_float = read_f32(c.base_addr + off.f28)

  return c
end

function MVP0.score_candidate(candidate, target_value_pattern)
  local w = MVP0.CONFIG.weights
  local r = {
    candidate = candidate,
    score = 0,
    hard_pass = true,
    flags = {},
    reasons_positive = {},
    reasons_negative = {},
  }

  local function add_flag(flag)
    for _, v in ipairs(r.flags) do
      if v == flag then
        return
      end
    end
    table.insert(r.flags, flag)
  end

  if candidate.f28 == target_value_pattern then
    r.score = r.score + w.target_match
    add_flag("target_match")
    table.insert(r.reasons_positive, "target value matches")
  else
    r.hard_pass = false
    table.insert(r.reasons_negative, "target value mismatch")
  end

  for _, key in ipairs({"f08", "f18", "f20"}) do
    local v = candidate[key]
    if v ~= 0 then
      r.score = r.score + w.nonzero_field
      table.insert(r.reasons_positive, key .. " nonzero")
    end
    if not is_suspicious_float_like(v) then
      r.score = r.score + w.not_floatlike_field
      table.insert(r.reasons_positive, key .. " not float-like")
    end
  end

  for _, key in ipairs({"f68", "f70", "f78"}) do
    local v = candidate[key]
    if v ~= 0 then
      r.score = r.score + w.nonzero_field
      table.insert(r.reasons_positive, key .. " nonzero")
    end
    if not is_suspicious_float_like(v) then
      r.score = r.score + w.not_floatlike_field
      table.insert(r.reasons_positive, key .. " not float-like")
    end
  end

  if candidate.f58 ~= 0 then
    r.score = r.score + w.status_nonzero
    table.insert(r.reasons_positive, "f58 nonzero")
  end
  if is_small_int_like(candidate.f58) then
    r.score = r.score + w.status_small_int
    add_flag("small_int_status")
    table.insert(r.reasons_positive, "status field is small-int-like")
  end
  if not is_suspicious_float_like(candidate.f58) then
    r.score = r.score + w.status_not_floatlike
    table.insert(r.reasons_positive, "f58 not float-like")
  end

  local front_empty = candidate.f08 == 0 and candidate.f18 == 0 and candidate.f20 == 0
  local tail_empty = candidate.f68 == 0 and candidate.f70 == 0 and candidate.f78 == 0

  if front_empty then
    r.score = r.score - w.penalty_empty_front
    add_flag("sparse_buffer_like")
    table.insert(r.reasons_negative, "front block is empty")
  end
  if tail_empty then
    r.score = r.score - w.penalty_empty_tail
    add_flag("sparse_buffer_like")
    table.insert(r.reasons_negative, "tail block is empty")
  end

  local float_like_count = count_suspicious({
    candidate.f18, candidate.f20, candidate.f58,
    candidate.f68, candidate.f70, candidate.f78,
  })

  if float_like_count >= 3 then
    r.score = r.score - w.penalty_floatlike_3plus
    add_flag("float_block_like")
    table.insert(r.reasons_negative, "too many float-like fields")
  end
  if float_like_count >= 5 then
    r.score = r.score - w.penalty_floatlike_5plus
    add_flag("float_block_like")
    table.insert(r.reasons_negative, "candidate resembles float block")
  end

  if candidate.f20 == target_value_pattern and candidate.f28 == target_value_pattern then
    r.score = r.score - w.penalty_value_copy
    add_flag("value_copy_like")
    table.insert(r.reasons_negative, "candidate resembles value copy block")
  end

  if candidate.f08 ~= 0 and candidate.f18 ~= 0 and candidate.f20 ~= 0 then
    add_flag("strong_front_block")
    table.insert(r.reasons_positive, "front metadata present")
  end

  if candidate.f68 ~= 0 and candidate.f70 ~= 0 and candidate.f78 ~= 0 then
    add_flag("strong_tail_block")
    table.insert(r.reasons_positive, "tail reference block present")
  end

  if has_flag(r, "strong_front_block") and has_flag(r, "strong_tail_block") then
    add_flag("object_like")
  end

  return r
end

function MVP0.rank_candidates(scored)
  table.sort(scored, function(a, b)
    return a.score > b.score
  end)

  local best = scored[1]
  local second = scored[2]
  local gap = second and (best.score - second.score) or best.score
  local confidence
  if gap >= MVP0.CONFIG.confidence.high_gap then
    confidence = "HIGH"
  elseif gap >= MVP0.CONFIG.confidence.medium_gap then
    confidence = "MEDIUM"
  else
    confidence = "LOW"
  end

  return {
    best = best,
    second = second,
    ranked = scored,
    score_gap = gap,
    confidence = confidence,
    manual_review = (confidence == "LOW"),
  }
end

function MVP0.recommend_action(rank)
  local best = rank.best
  local second = rank.second
  local cfg = MVP0.CONFIG.recommendation
  local result = {
    recommended_candidate = best,
    recommendation = "REJECT",
    confidence = rank.confidence,
    score_gap = rank.score_gap,
    manual_review_required = true,
    rationale = {},
  }

  local function add_reason(reason)
    table.insert(result.rationale, reason)
  end

  if best == nil then
    add_reason("no candidates available")
    return result
  end

  if has_flag(best, "object_like") then
    add_reason("best candidate has object-like structure")
  end
  if has_flag(best, "strong_front_block") then
    add_reason("front metadata block is present")
  end
  if has_flag(best, "strong_tail_block") then
    add_reason("tail reference block is present")
  end
  if has_flag(best, "small_int_status") then
    add_reason("status field is small-int-like")
  end
  if second ~= nil then
    add_reason("score gap over second place is " .. tostring(rank.score_gap))
  else
    add_reason("only one matching candidate was scored")
  end

  if rank.confidence == "HIGH"
      and best.score >= cfg.accept_min_score
      and has_flag(best, "object_like")
      and not has_flag(best, "float_block_like") then
    result.recommendation = "ACCEPT"
    result.manual_review_required = false
    add_reason("high confidence candidate is suitable for direct use")
    return result
  end

  if best.score < cfg.review_min_score then
    result.recommendation = "REJECT"
    result.manual_review_required = true
    add_reason("top candidate score is below the review threshold")
    return result
  end

  result.recommendation = "REVIEW"
  result.manual_review_required = true
  add_reason("manual review is recommended before acting on this candidate")
  return result
end

function MVP0.render_report(rank, input_payload, recommendation)
  local lines = {}
  table.insert(lines, "=== Session Summary ===")
  if input_payload.session_id then
    table.insert(lines, "Session: " .. tostring(input_payload.session_id))
  end
  table.insert(lines, "Candidates: " .. tostring(#rank.ranked))
  table.insert(lines, "Target value pattern: " .. hex_u32(input_payload.target_value_pattern))
  if input_payload.target_value_float ~= nil then
    table.insert(lines, "Target value float: " .. tostring(input_payload.target_value_float))
  end
  table.insert(lines, "Best candidate: " .. hex_u64(rank.best.candidate.value_addr))
  table.insert(lines, "Best base: " .. hex_u64(rank.best.candidate.base_addr))
  table.insert(lines, "Best score: " .. tostring(rank.best.score))
  if rank.second then
    table.insert(lines, "Second score: " .. tostring(rank.second.score))
  end
  table.insert(lines, "Score gap: " .. tostring(rank.score_gap))
  table.insert(lines, "Confidence: " .. rank.confidence)
  table.insert(lines, "Manual review: " .. tostring(rank.manual_review))
  table.insert(lines, "=======================")
  table.insert(lines, "")

  if recommendation then
    table.insert(lines, "=== Recommendation ===")
    table.insert(lines, "Recommendation: " .. recommendation.recommendation)
    table.insert(lines, "Confidence: " .. recommendation.confidence)
    table.insert(lines, "Manual review required: " .. tostring(recommendation.manual_review_required))
    if recommendation.recommended_candidate then
      table.insert(lines, "Recommended value addr: " .. hex_u64(recommendation.recommended_candidate.candidate.value_addr))
      table.insert(lines, "Recommended base addr : " .. hex_u64(recommendation.recommended_candidate.candidate.base_addr))
      table.insert(lines, "Recommended score     : " .. tostring(recommendation.recommended_candidate.score))
    end
    if #recommendation.rationale > 0 then
      table.insert(lines, "Rationale: " .. table.concat(recommendation.rationale, "; "))
    end
    table.insert(lines, "======================")
    table.insert(lines, "")
  end

  for index, r in ipairs(rank.ranked) do
    local c = r.candidate
    table.insert(lines, "--- Candidate #" .. tostring(index) .. " ---")
    table.insert(lines, "value_addr = " .. hex_u64(c.value_addr))
    table.insert(lines, "base_addr  = " .. hex_u64(c.base_addr))
    table.insert(lines, "f08 = " .. hex_u32(c.f08))
    table.insert(lines, "f18 = " .. hex_u32(c.f18))
    table.insert(lines, "f20 = " .. hex_u32(c.f20))
    table.insert(lines, "f28 = " .. hex_u32(c.f28) .. " (" .. tostring(c.f28_float) .. ")")
    table.insert(lines, "f58 = " .. hex_u32(c.f58))
    table.insert(lines, "f68 = " .. hex_u32(c.f68))
    table.insert(lines, "f70 = " .. hex_u32(c.f70))
    table.insert(lines, "f78 = " .. hex_u32(c.f78))
    table.insert(lines, "score = " .. tostring(r.score))
    table.insert(lines, "hard_pass = " .. tostring(r.hard_pass))
    table.insert(lines, "flags = " .. table.concat(r.flags, ", "))
    table.insert(lines, "positive = " .. table.concat(r.reasons_positive, "; "))
    table.insert(lines, "negative = " .. table.concat(r.reasons_negative, "; "))
    table.insert(lines, "")
  end

  return table.concat(lines, "\n")
end

function MVP0.run(input_payload)
  local candidates = {}
  for _, value_addr in ipairs(input_payload.candidate_value_addrs) do
    table.insert(candidates, MVP0.build_candidate(value_addr))
  end

  local scored = {}
  for _, candidate in ipairs(candidates) do
    table.insert(scored, MVP0.score_candidate(candidate, input_payload.target_value_pattern))
  end

  local ranked = MVP0.rank_candidates(scored)
  ranked.recommendation = MVP0.recommend_action(ranked)
  ranked.report_text = MVP0.render_report(ranked, input_payload, ranked.recommendation)
  return ranked
end

_G.MVP0 = MVP0
return MVP0