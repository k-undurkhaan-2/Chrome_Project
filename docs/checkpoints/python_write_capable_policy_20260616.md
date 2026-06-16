# Python Write-Capable Feature Policy - 2026-06-16

## Purpose

Record the policy checkpoint for future Python write-capable features.

## Baseline

- only write-capable Python command = `report export`
- `writes_files_count = 1`
- `runs_ce_count = 0`
- `report export --dry-run` remains read-only
- no Python command mutates CE/runtime state

## Policy Summary

Future write-capable Python features must use:

- planning document
- contract document
- dry-run implementation
- dry-run smoke/checkpoint
- guarded real-write implementation
- guarded smoke/checkpoint
- boundary/operator documentation

## Required Gates

- approved roots or explicit state targets
- dry-run first
- default no overwrite / mutation
- protected path and protected hash checks
- command inventory risk marking
- validation-created file cleanup
- no CE/runtime mutation unless separately contracted

## Non-Goals

- no guarded write / restore migration
- no CE automation
- no PowerShell mutation replacement
- no Lua/runtime changes
- no algorithm rewrite
