# OKX Position Report Error Propagation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent failed OKX position queries from being interpreted as successful flat venue state.

**Architecture:** Propagate the original adapter exception after logging it. Reuse the existing
`LiveExecutionEngine` failed-venue path to skip reconciliation without changing successful empty
response semantics.

**Tech Stack:** Python 3.12, asyncio, pytest/pytest-asyncio, uv 0.11.25, GitHub Actions, Docker/GHCR.

---

### Task 1: Establish the regression test

**Files:**
- Modify: `tests/integration_tests/adapters/okx/test_execution.py:793`

**Step 1: Change the existing failure test**

Rename it to `test_generate_position_status_reports_propagates_failure` and replace the `[]`
assertion with:

```python
with pytest.raises(Exception, match="boom"):
    await client.generate_position_status_reports(command)
```

**Step 2: Run the test to verify RED**

Run:

```bash
uvx --from uv==0.11.25 uv run --python 3.12 --group test \
  pytest tests/integration_tests/adapters/okx/test_execution.py \
  -q -k generate_position_status_reports_propagates_failure
```

Expected: FAIL with `DID NOT RAISE` because the adapter still returns `[]`.

### Task 2: Implement the minimal adapter fix

**Files:**
- Modify: `nautilus_trader/adapters/okx/execution.py:1009`
- Test: `tests/integration_tests/adapters/okx/test_execution.py`
- Test: `tests/unit_tests/live/test_execution_recon.py`

**Step 1: Re-raise the logged exception**

Add a bare `raise` immediately after `_log_report_error(e, "PositionReports")`.

**Step 2: Run the regression test to verify GREEN**

Run the Task 1 command. Expected: `1 passed`.

**Step 3: Verify the engine error contract**

```bash
uvx --from uv==0.11.25 uv run --python 3.12 --group test \
  pytest tests/unit_tests/live/test_execution_recon.py \
  -q -k query_position_status_reports_handles_exceptions
```

Expected: `1 passed` and the failed venue is returned.

**Step 4: Run the complete OKX execution test file**

```bash
uvx --from uv==0.11.25 uv run --python 3.12 --group test \
  pytest tests/integration_tests/adapters/okx/test_execution.py -q
```

Expected: all tests pass.

**Step 5: Commit the fix and design**

```bash
git add nautilus_trader/adapters/okx/execution.py \
  tests/integration_tests/adapters/okx/test_execution.py docs/plans/
git commit -m "fix(okx): propagate position report query failures"
```

### Task 3: Prepare fork release 1.230.3

**Files:**
- Modify: `pyproject.toml`
- Modify: `crates/core/build.rs`
- Modify: `uv.lock`
- Modify: `RELEASES.md`
- Modify: `.github/workflows/release-wheel-ghcr-manual.yml`

**Step 1:** Update every fork version/default from `1.230.2` to `1.230.3`.

**Step 2:** Add a top release note describing safe propagation of failed OKX position queries.

**Step 3:** Run version consistency and focused tests.

**Step 4:** Commit with `chore(release): prepare fork 1.230.3`.

**Step 5:** Push `release/v1.230.3-fork`, create and push tag `v1.230.3`.

### Task 4: Publish and verify the GHCR wheel

**Step 1:** Dispatch `release-wheel-ghcr-manual.yml` with `source_ref=v1.230.3`,
`version=1.230.3`, and `push_latest=true`.

**Step 2:** Wait for the workflow to succeed.

**Step 3:** Verify the GitHub Release wheel asset, GHCR `1.230.3`/`latest` digest equality, and
`/wheels/nautilus_trader-1.230.3-*.whl` inside the image.

### Task 5: Deploy and verify testnet and prod

**Step 1:** From `nautilus_quants` main, dispatch fork-wheel prod deploys with
`wheel_image_tag=1.230.3` and `prod_use_fork_wheel=true` for `factor_a`, `factor_b`, and
`breakout_a`.

**Step 2:** Reuse the resulting immutable GHCR quants image for the current Shanghai
`nautilus-testnet-1hour` container, preserving its env file, mounts, and
`config/live/okx_testnet_breakout_1h.yaml` command.

**Step 3:** For all four containers, verify image digest, health, restart count, runtime package
versions, exact command/config, and recent startup/reconciliation logs.

**Step 4:** Re-query OKX testnet BTC position and protective stop. Report the pre-existing hidden
position mismatch separately; do not mutate it without explicit position-management authority.
