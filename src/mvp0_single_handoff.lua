-- H1: pure, non-authorizing evidence from a completed blind Single run.
-- No filesystem, collector, process-memory, executor or authorization APIs.
local Handoff = {SCHEMA_VERSION = 1}

local function finite(value)
  return type(value) == "number" and value == value and math.abs(value) ~= math.huge
end

local function address(value)
  return finite(value) and value > 0 and value <= 0x1FFFFFFFFFFFFF and value % 1 == 0
end

local function token(value)
  return type(value) == "string" and #value > 0 and #value <= 80
    and value:match("^[A-Za-z0-9][A-Za-z0-9_-]*$") ~= nil
    and not value:find("__", 1, true) and value:sub(-1) ~= "_" and value ~= "nil"
end

local function float32(value)
  if not finite(value) then return nil end
  local ok, packed = pcall(string.pack, "<f", value)
  if not ok then return nil end
  local rounded = string.unpack("<f", packed)
  if not finite(rounded) then return nil end
  return string.unpack("<I4", packed)
end

local function pattern(value)
  return finite(value) and value >= 0 and value <= 0xFFFFFFFF and value % 1 == 0
    and finite(string.unpack("<f", string.pack("<I4", value)))
end

local function optional_enum(value, allowed)
  return value == nil or (type(value) == "string" and allowed[value] == true)
end

local CONFIDENCE = {HIGH = true, MEDIUM = true, LOW = true}
local RECOMMENDATION = {ACCEPT = true, REVIEW = true, REJECT = true}

-- source is a runner receipt for the exact log successfully published in this
-- run. It is not an independently measured process identity or a signature.
function Handoff.build(summary, result, source)
  if type(summary) ~= "table" or summary.validation_profile ~= "single"
      or summary.mode ~= "no_probe_A" or summary.probe_full_foundlist ~= false
      or summary.execution_mode ~= "disabled" or summary.write_enabled ~= false
      or summary.write_attempted ~= false or summary.write_ready ~= false
      or summary.execution_success ~= false or summary.baseline_eligible ~= false then
    return nil, "handoff_not_detect_only"
  end
  if summary.run_valid ~= true or summary.failure_class ~= nil or summary.error ~= nil
      or summary.collector_empty ~= false then
    return nil, "handoff_invalid_run"
  end
  if type(source) ~= "table" or not token(source.batch_id)
      or not token(source.case_id) or not token(source.session_id)
      or summary.single_source_batch_id ~= source.batch_id
      or summary.case_id ~= source.case_id or summary.session_id ~= source.session_id then
    return nil, "handoff_source_identity_invalid"
  end
  local stem = source.batch_id .. "__" .. source.session_id .. "__" .. source.case_id
  if source.log_filename ~= stem .. "__no_probe_A.log" then
    return nil, "handoff_source_identity_invalid"
  end
  if source.log_published ~= true or not finite(source.log_size_bytes)
      or source.log_size_bytes <= 0 or source.log_size_bytes % 1 ~= 0
      or summary.log_size_bytes ~= source.log_size_bytes then
    return nil, "handoff_source_log_unavailable"
  end
  if type(result) ~= "table" or type(result.ranked) ~= "table" or #result.ranked == 0
      or result.best ~= result.ranked[1] or result.second ~= result.ranked[2] then
    return nil, "handoff_ranking_invalid"
  end
  local count, seen, previous = 0, {}, nil
  for key in pairs(result.ranked) do
    if type(key) ~= "number" or key % 1 ~= 0 or key < 1 or key > #result.ranked then
      return nil, "handoff_ranking_invalid"
    end
    count = count + 1
  end
  if count ~= #result.ranked then return nil, "handoff_ranking_invalid" end
  for rank, item in ipairs(result.ranked) do
    if type(item) ~= "table" or type(item.candidate) ~= "table" or item.rank_position ~= rank
        or not address(item.candidate.value_addr) or seen[item.candidate.value_addr]
        or not finite(item.score) or (previous ~= nil and item.score > previous)
        or (item.final_score ~= nil and (not finite(item.final_score) or item.final_score ~= item.score)) then
      return nil, "handoff_ranking_invalid"
    end
    seen[item.candidate.value_addr], previous = true, item.score
  end
  local best, second = result.best, result.second
  if summary.best_candidate_addr ~= best.candidate.value_addr or summary.best_score ~= best.score
      or summary.second_score ~= (second and second.score) or summary.score_gap ~= result.score_gap
      or summary.confidence ~= result.confidence then
    return nil, "handoff_candidate_mismatch"
  end
  -- Preserve the ranker's existing single-candidate gap convention. A missing
  -- gap stays nil; neither a tie nor a large gap is evidence of correctness.
  if result.score_gap ~= nil and (not finite(result.score_gap)
      or (second ~= nil and result.score_gap < 0)
      or result.score_gap ~= (second and (best.score - second.score) or best.score)) then
    return nil, "handoff_score_gap_invalid"
  end
  if not optional_enum(result.confidence, CONFIDENCE) then
    return nil, "handoff_confidence_invalid"
  end
  local recommendation
  if result.final_decision ~= nil then
    if type(result.final_decision) ~= "table" then return nil, "handoff_recommendation_invalid" end
    local decision = result.final_decision
    if (decision.recommended_candidate ~= nil and decision.recommended_candidate ~= best)
        or (decision.confidence ~= nil and decision.confidence ~= result.confidence)
        or (decision.score_gap ~= nil and decision.score_gap ~= result.score_gap)
        or not optional_enum(decision.recommendation, RECOMMENDATION) then
      return nil, "handoff_recommendation_invalid"
    end
    recommendation = decision.recommendation
  end
  local search_float, search_pattern = summary.target_value_float, summary.target_value_pattern
  if search_float == nil and search_pattern == nil then return nil, "handoff_search_target_missing" end
  local bits = search_float ~= nil and float32(search_float) or nil
  if (search_float ~= nil and bits == nil) or (search_pattern ~= nil and not pattern(search_pattern)) then
    return nil, "handoff_search_target_invalid"
  end
  if bits ~= nil and search_pattern ~= nil and bits ~= search_pattern then
    return nil, "handoff_search_target_mismatch"
  end

  return {
    handoff_schema_version = Handoff.SCHEMA_VERSION,
    handoff_kind = "single_candidate_proposal",
    authorization_status = "NOT_AUTHORIZED",
    handoff_write_ready = false, write_attempted = false, baseline_eligible = false,
    source_batch_id = source.batch_id, source_case_id = source.case_id,
    source_session_id = source.session_id, source_mode = "no_probe_A",
    source_validation_profile = "single", source_log_filename = source.log_filename,
    source_log_size_bytes = source.log_size_bytes,
    run_valid = true, failure_class = nil, error = nil, probe_full_foundlist = false,
    candidate_rank = 1, candidate_address = string.format("0x%X", best.candidate.value_addr),
    candidate_count = count, best_score = best.score, second_score = second and second.score,
    score_gap = result.score_gap, confidence = result.confidence, recommendation = recommendation,
    search_target_float = search_float,
    search_target_pattern = search_pattern ~= nil and string.format("0x%08X", search_pattern) or nil,
    operator_process_identity_verified = false,
    session_identity_note = "internal session label does not identify a Windows process instance",
    independent_review_required = true,
    next_action = "independent_candidate_and_process_verification",
    warning = "NOT A WRITE GRANT; no live write can be triggered from this artifact; rank and confidence do not prove correctness",
    authentication_note = "not cryptographically authenticated",
    handoff_filename = stem .. "__single_handoff.txt",
  }
end

local FIELDS = {
  "handoff_schema_version", "handoff_kind", "authorization_status", "handoff_write_ready",
  "write_attempted", "baseline_eligible", "source_batch_id", "source_case_id", "source_session_id",
  "source_mode", "source_validation_profile", "source_log_filename", "source_log_size_bytes",
  "run_valid", "failure_class", "error", "probe_full_foundlist", "candidate_rank", "candidate_address",
  "candidate_count", "best_score", "second_score", "score_gap", "confidence", "recommendation",
  "search_target_float", "search_target_pattern", "operator_process_identity_verified",
  "session_identity_note", "independent_review_required", "next_action", "warning", "authentication_note",
}

-- Render only a fresh validated whitelist, never an arbitrary caller's table.
-- Required unavailable numeric fields use nil; absent optional labels are omitted.
function Handoff.render(summary, result, source)
  local record, failure = Handoff.build(summary, result, source)
  if not record then return nil, failure end
  local lines = {}
  for _, name in ipairs(FIELDS) do
    local value = record[name]
    if value ~= nil or (name ~= "confidence" and name ~= "recommendation") then
      local text = type(value) == "number" and math.type(value) == "float"
        and string.format("%.17g", value) or tostring(value)
      lines[#lines + 1] = name .. "=" .. text
    end
  end
  return table.concat(lines, "\r\n") .. "\r\n", nil, record.handoff_filename
end

return Handoff
