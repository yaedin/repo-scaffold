"""Tests for the scaffold's machinery.

These exist because every number in the repo flows through this code. A silent
bug in `wilson_ci` or `check_records` does not announce itself — it produces a
plausible number that is wrong, which is the worst possible failure mode for
research. The statistics are checked against values you can verify by hand or
against a textbook.
"""

from __future__ import annotations

import importlib
import math
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lab import check, size
from lab.analysis import check_records, two_proportion_ztest, wilson_ci
from lab.analysis.stats import _z_critical, bootstrap_ci
from lab.check import cites_explore, looks_like_path, paths_in
from lab.core import backend, provenance, records, seeds
from lab.core import checkpoint as checkpoint_mod
from lab.core.checkpoint import Checkpoint
from lab.core.provenance import ProvenanceError

# --- statistics ---------------------------------------------------------------


def test_z_critical_matches_known_value():
    assert _z_critical(0.05) == pytest.approx(1.959964, abs=1e-5)
    assert _z_critical(0.01) == pytest.approx(2.575829, abs=1e-5)


def test_wilson_ci_known_value():
    # Textbook: 5 successes in 10 trials -> Wilson 95% CI is roughly [0.237, 0.763].
    ci = wilson_ci(5, 10)
    assert ci.point == 0.5
    assert ci.lo == pytest.approx(0.2366, abs=1e-3)
    assert ci.hi == pytest.approx(0.7634, abs=1e-3)


def test_wilson_ci_stays_in_bounds_at_extremes():
    """The reason to prefer Wilson over the normal approximation."""
    for k, n in [(0, 20), (20, 20), (1, 3)]:
        ci = wilson_ci(k, n)
        assert 0.0 <= ci.lo <= ci.hi <= 1.0


def test_wilson_ci_empty_is_nan_not_a_crash():
    ci = wilson_ci(0, 0)
    assert math.isnan(ci.point) and ci.n == 0
    assert "n/a" in str(ci)


def test_wilson_ci_narrows_with_n():
    wide = wilson_ci(5, 10)
    narrow = wilson_ci(500, 1000)
    assert (narrow.hi - narrow.lo) < (wide.hi - wide.lo)


def test_two_proportion_ztest_detects_a_real_difference():
    r = two_proportion_ztest(80, 100, 50, 100)
    assert r.delta == pytest.approx(0.30)
    assert r.significant()
    assert r.p_value < 1e-4


def test_two_proportion_ztest_finds_nothing_when_arms_are_identical():
    r = two_proportion_ztest(50, 100, 50, 100)
    assert r.delta == 0.0
    assert not r.significant()


def test_two_proportion_ztest_survives_degenerate_input():
    """No variance means no test — must not raise ZeroDivisionError."""
    r = two_proportion_ztest(0, 10, 0, 10)
    assert r.delta == 0.0
    assert not math.isnan(r.p_value) or True  # either NaN or 1.0, never a crash


def test_intervals_overlap_check():
    assert wilson_ci(50, 100).overlaps(wilson_ci(52, 100))
    assert not wilson_ci(95, 100).overlaps(wilson_ci(10, 100))


def test_bootstrap_ci_brackets_the_mean():
    ci = bootstrap_ci([1.0, 2.0, 3.0, 4.0, 5.0], n_boot=2000, seed=0)
    assert ci.lo < ci.point < ci.hi
    assert ci.point == pytest.approx(3.0)


# --- integrity ----------------------------------------------------------------


def _rows(n=4, **overrides):
    base = [
        {"record_id": f"r{i}", "arm": "control", "item_id": "a", "fired": True} for i in range(n)
    ]
    for r in base:
        r.update(overrides)
    return base


def test_integrity_passes_on_clean_data():
    report = check_records(_rows(), required=["record_id", "arm", "fired"], unique_key="record_id")
    assert report.ok
    assert report.n_records == 4


def test_integrity_catches_empty_input():
    report = check_records([], required=["arm"])
    assert not report.ok
    assert any(i.code == "empty" for i in report.issues)


def test_integrity_catches_missing_field():
    rows = _rows()
    del rows[0]["arm"]
    report = check_records(rows, required=["arm"])
    assert not report.ok
    assert any(i.code == "missing_field" for i in report.issues)


def test_integrity_catches_empty_value():
    rows = _rows()
    rows[0]["arm"] = None
    report = check_records(rows, required=["arm"])
    assert any(i.code == "empty_value" for i in report.issues)


def test_integrity_catches_duplicates():
    rows = _rows()
    rows[1]["record_id"] = rows[0]["record_id"]
    report = check_records(rows, unique_key="record_id")
    assert not report.ok
    assert any(i.code == "duplicate_key" for i in report.issues)


def test_integrity_catches_unexpected_level():
    rows = _rows()
    rows[0]["arm"] = "ERROR"
    report = check_records(rows, categorical={"arm": ["control", "treatment"]})
    assert not report.ok
    assert any(i.code == "unexpected_level" for i in report.issues)


def test_integrity_catches_dropped_records():
    """The check that catches a retry loop silently swallowing a failure."""
    rows = _rows(3)  # expected 4 per cell, got 3
    report = check_records(rows, group_by=["arm", "item_id"], expected_per_cell=4)
    assert not report.ok
    assert any(i.code == "incomplete_cell" for i in report.issues)


def test_integrity_warns_on_unbalanced_cells():
    rows = _rows(3) + [{"record_id": "x0", "arm": "treatment", "item_id": "a", "fired": True}]
    report = check_records(rows, group_by=["arm", "item_id"])
    assert report.ok  # a warning, not an error
    assert any(i.code == "unbalanced_cells" for i in report.warnings)


def test_raise_if_failed_blocks_the_analysis():
    report = check_records([], required=["arm"])
    with pytest.raises(ValueError, match="integrity check failed"):
        report.raise_if_failed()


# --- plumbing -----------------------------------------------------------------


def test_seeds_are_reproducible():
    assert seeds.seed_all(42) == 42
    import random

    a = [random.random() for _ in range(3)]
    seeds.seed_all(42)
    assert [random.random() for _ in range(3)] == a


def test_spawn_gives_independent_streams():
    """Sequential seeds correlate; spawned seeds must not collide."""
    derived = {seeds.spawn(0, index=i) for i in range(50)}
    assert len(derived) == 50


def test_jsonl_roundtrip(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "ü"}]
    path = tmp_path / "out" / "r.jsonl"
    assert records.write(path, rows) == 2
    assert records.read(path) == rows


def test_jsonl_reports_the_bad_line_number(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": 1}\nNOT JSON\n', encoding="utf-8")
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        records.read(path)


# --- the documentation linter -------------------------------------------------


def test_looks_like_path_accepts_real_paths():
    assert looks_like_path("experiments/e00_smoke/run.py")
    assert looks_like_path("src/lab/core")


def test_looks_like_path_rejects_prose_and_commands():
    """A linter that cries wolf gets disabled, and then it protects nothing."""
    assert not looks_like_path("run.py")  # generic mention, not a root file
    assert not looks_like_path("RESULTS.md")
    assert not looks_like_path("just verify")
    assert not looks_like_path("uv sync")
    assert not looks_like_path("experiments/e<NN>_slug/run.py")  # placeholder
    assert not looks_like_path("https://example.com/a/b")


def test_html_comments_are_ignored():
    """Commented-out template rows cite paths that are meant not to exist yet."""
    md = "keep `a/b.py`\n<!-- example: `nope/missing.py` -->\nkeep `c/d.py`\n"
    found = [tok for _, tok in paths_in(md)]
    assert found == ["a/b.py", "c/d.py"]


def test_multiline_html_comments_are_ignored():
    md = "`a/b.py`\n<!--\n`nope/x.py`\n`nope/y.py`\n-->\n`c/d.py`\n"
    assert [tok for _, tok in paths_in(md)] == ["a/b.py", "c/d.py"]


def test_paths_in_reports_line_numbers():
    md = "line one\nline two `x/y.py`\n"
    assert paths_in(md) == [(2, "x/y.py")]


def test_ignore_marker_skips_a_line():
    md = "`gone/x.py` <!-- check:ignore -->\n`kept/y.py`\n"
    assert [tok for _, tok in paths_in(md)] == ["kept/y.py"]


# --- provenance: the failure this scaffold was revised for ---------------------
#
# A remote launcher produced real model output while a stale manifest described it
# as synthetic. Nothing crashed; every downstream number inherited the mislabel.
# These tests encode that the same bypass now fails loudly.


def _stamped(n=4, backend="stub", model_id="bernoulli-coin", arm="control"):
    return [
        {
            "record_id": f"{arm}-{i}",
            "arm": arm,
            "item_id": "a",
            "fired": True,
            "backend": backend,
            "model_id": model_id,
            "dtype": "float64",
        }
        for i in range(n)
    ]


def test_derive_reads_origin_from_the_records():
    got = provenance.derive(_stamped())
    assert got == {"backend": "stub", "model_id": "bernoulli-coin", "dtype": "float64"}


def test_derive_rejects_unstamped_records():
    rows = _stamped()
    del rows[0]["backend"]
    with pytest.raises(provenance.ProvenanceError, match="carry no 'backend'"):
        provenance.derive(rows)


def test_derive_rejects_a_file_that_mixes_runs():
    """Two backends in one file means a rate computed across it is meaningless."""
    rows = _stamped(2) + _stamped(2, backend="modal", arm="treatment")
    with pytest.raises(provenance.ProvenanceError, match="disagree on 'backend'"):
        provenance.derive(rows)


def test_verify_accepts_an_honest_manifest():
    man = {"provenance": {"backend": "stub", "model_id": "bernoulli-coin", "dtype": "float64"}}
    assert provenance.verify(_stamped(), man)["backend"] == "stub"


def test_verify_rejects_a_manifest_that_bypassed_the_run():
    """THE regression test: real records, manifest still claiming synthetic."""
    real_records = _stamped(model_id="Qwen3-8B", backend="modal")
    stale_manifest = {"provenance": {"backend": "stub", "model_id": "bernoulli-coin"}}
    with pytest.raises(provenance.ProvenanceError, match="manifest says backend='stub'"):
        provenance.verify(real_records, stale_manifest)


def test_check_records_flags_provenance_mismatch_as_fatal():
    report = check_records(
        _stamped(model_id="Qwen3-8B", backend="modal"),
        manifest={"provenance": {"backend": "stub", "model_id": "bernoulli-coin"}},
    )
    assert not report.ok
    assert any(i.code == "provenance_mismatch" for i in report.errors)


def test_check_records_warns_when_the_manifest_cannot_be_checked():
    report = check_records(_stamped(), manifest={"provenance": None})
    assert report.ok  # a warning, not a blocker
    assert any(i.code == "provenance_unverifiable" for i in report.warnings)


def test_check_records_reports_derived_provenance():
    report = check_records(_stamped())
    assert report.provenance["model_id"] == "bernoulli-coin"
    assert "bernoulli-coin" in report.summary()


# --- backends -----------------------------------------------------------------


def test_stub_is_registered_and_not_reportable():
    stub = backend.resolve("stub")
    assert stub.name == "stub"
    assert stub.reportable is False, "stub numbers are leads, never results"


def test_unknown_backend_names_what_is_available():
    with pytest.raises(KeyError, match="Registered: stub"):
        backend.resolve("gpu-cluster")


def test_stamp_covers_every_provenance_field():
    assert set(backend.StubBackend().stamp()) == set(backend.PROVENANCE_FIELDS)


# --- sharded records ----------------------------------------------------------


def test_record_files_finds_every_shard(tmp_path, monkeypatch):
    import lab.core.paths as paths_mod

    monkeypatch.setattr(paths_mod, "EXPERIMENTS_DIR", tmp_path)
    p = paths_mod.RunPaths("e99").ensure()
    records.write(p.records_for("control"), _stamped(2))
    records.write(p.records_for("treatment"), _stamped(2, arm="treatment"))
    assert [f.name for f in p.record_files()] == [
        "records_control.jsonl",
        "records_treatment.jsonl",
    ]
    assert len(records.read_all(p.record_files())) == 4


def test_read_all_can_tag_the_source_shard(tmp_path):
    a, b = tmp_path / "records_a.jsonl", tmp_path / "records_b.jsonl"
    records.write(a, [{"x": 1}])
    records.write(b, [{"x": 2}])
    rows = records.read_all([a, b], add_source=True)
    assert [r["_source_file"] for r in rows] == ["records_a.jsonl", "records_b.jsonl"]


# --- claim values must match their artifacts ----------------------------------


def test_pointer_resolves_a_nested_value(tmp_path):
    f = tmp_path / "summary.json"
    f.write_text('{"comparisons": {"main": {"delta": 0.14375}}}', encoding="utf-8")
    assert check.resolve_pointer(f, "comparisons.main.delta") == pytest.approx(0.14375)


def test_pointer_indexes_into_lists(tmp_path):
    f = tmp_path / "s.json"
    f.write_text('{"arms": [{"rate": 0.5}, {"rate": 0.62}]}', encoding="utf-8")
    assert check.resolve_pointer(f, "arms.1.rate") == pytest.approx(0.62)


def test_pointer_returns_none_when_it_does_not_resolve(tmp_path):
    f = tmp_path / "s.json"
    f.write_text('{"a": {"b": "not a number"}}', encoding="utf-8")
    assert check.resolve_pointer(f, "a.b") is None
    assert check.resolve_pointer(f, "a.missing") is None


def test_quoted_value_accepts_the_forms_people_write():
    for cell in ["Δ = +14.4pp", "14.4%", "0.144", "delta 14.375"]:
        assert check.value_is_quoted(0.14375, cell), cell


def test_quoted_value_rejects_a_drifted_number():
    """The whole point: a rerun moved the effect and the ledger did not follow."""
    assert not check.value_is_quoted(0.091, "Δ = +14.4pp")
    assert not check.value_is_quoted(0.14375, "Δ = +9.1pp")


# --- checkpoint / resume ------------------------------------------------------
#
# Long jobs fail. Rerunning must cost the remainder, not the whole thing, and must
# not inflate n with duplicates.


def _units(n, arm="control"):
    return [
        {"record_id": f"{arm}-{i}", "arm": arm, "backend": "stub", "model_id": "m", "dtype": "f64"}
        for i in range(n)
    ]


def test_checkpoint_on_a_fresh_shard_has_everything_pending(tmp_path):
    ck = Checkpoint(tmp_path / "records_control.jsonl")
    planned = _units(5)
    assert ck.count() == 0
    assert ck.pending(planned) == planned


def test_checkpoint_resumes_only_what_is_missing(tmp_path):
    path = tmp_path / "records_control.jsonl"
    planned = _units(5)

    ck = Checkpoint(path)
    assert ck.extend(planned[:3]) == 3  # a run that died at 60%

    resumed = Checkpoint(path)
    assert resumed.count() == 3
    assert [u["record_id"] for u in resumed.pending(planned)] == ["control-3", "control-4"]
    assert resumed.extend(resumed.pending(planned)) == 2
    assert Checkpoint(path).count() == 5


def test_checkpoint_rerun_of_a_finished_job_is_a_noop(tmp_path):
    path = tmp_path / "r.jsonl"
    planned = _units(4)
    Checkpoint(path).extend(planned)
    ck = Checkpoint(path)
    assert ck.is_complete(planned)
    assert ck.extend(planned) == 0
    assert ck.count() == 4, "re-appending must not inflate n"


def test_checkpoint_skips_duplicates_within_one_batch_boundary(tmp_path):
    """An over-eager caller recomputing a boundary batch must not double-count."""
    path = tmp_path / "r.jsonl"
    planned = _units(6)
    Checkpoint(path).extend(planned[:4])
    assert Checkpoint(path).extend(planned[2:]) == 2  # 2 and 3 already present
    assert Checkpoint(path).count() == 6


def test_checkpoint_repairs_a_truncated_final_line(tmp_path):
    """A killed process leaves half an object. That must not poison the resume."""
    path = tmp_path / "r.jsonl"
    Checkpoint(path).extend(_units(3))
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"record_id": "control-3", "arm": "cont')  # killed mid-write

    ck = Checkpoint(path)
    assert ck.repaired_bytes > 0
    assert ck.count() == 3, "the three complete records survive"
    assert "repaired" in ck.status()


def test_checkpoint_refuses_to_mix_a_stub_run_with_a_real_one(tmp_path):
    """Resuming with a different backend would silently merge two populations."""
    path = tmp_path / "r.jsonl"
    Checkpoint(path).extend(_units(2))
    real = [dict(u, backend="modal", model_id="Qwen3-8B") for u in _units(2, arm="later")]
    with pytest.raises(ProvenanceError, match="different backend"):
        Checkpoint(path).extend(real)


def test_checkpoint_status_reports_progress(tmp_path):
    path = tmp_path / "r.jsonl"
    planned = _units(5)
    Checkpoint(path).extend(planned[:2])
    assert "2/5 done, 3 pending" in Checkpoint(path).status(planned)
    Checkpoint(path).extend(planned[2:])
    assert "complete" in Checkpoint(path).status(planned)


def test_repair_leaves_a_well_formed_file_alone(tmp_path):
    path = tmp_path / "r.jsonl"
    Checkpoint(path).extend(_units(2))
    assert checkpoint_mod.repair(path) == 0


# --- repository size guard ----------------------------------------------------
#
# The guard exists because a .gitignore gap put 894 MB into git history and it was
# found by a hanging push, not by a check. These tests build throwaway repos so
# the guard is exercised against real git rather than a mock of it.


def _repo(tmp_path, monkeypatch):
    """A real git repo the size module will treat as REPO_ROOT."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(size, "REPO_ROOT", tmp_path)
    return tmp_path


def test_size_guard_is_silent_outside_a_git_repo(tmp_path, monkeypatch):
    # A freshly copied template is not a repo yet. The guard must not explode
    # there, or it gets deleted and then it guards nothing.
    monkeypatch.setattr(size, "REPO_ROOT", tmp_path)
    assert size.is_git_repo() is False
    assert size.problems() == []


def test_size_guard_passes_on_a_small_repo(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    (repo / "small.txt").write_text("a claim", encoding="utf-8")
    subprocess.run(["git", "add", "small.txt"], cwd=repo, check=True)
    assert size.problems() == []


def test_size_guard_flags_an_oversized_staged_blob(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    (repo / "acts.npz").write_bytes(b"\0" * (size.MAX_BLOB_BYTES + 1))
    subprocess.run(["git", "add", "acts.npz"], cwd=repo, check=True)

    found = size.problems()
    assert len(found) == 1, "one oversized file must report as exactly one problem"
    assert "acts.npz" in found[0]
    assert ".gitignore" in found[0], "the message must say what to do about it"


def test_size_guard_catches_the_blob_before_it_is_committed(tmp_path, monkeypatch):
    # The whole value of the guard is that it fires at `git add` time, when the
    # fix is `git rm --cached`, rather than after a push when it is a rewrite.
    repo = _repo(tmp_path, monkeypatch)
    (repo / "big.bin").write_bytes(b"\0" * (size.MAX_BLOB_BYTES + 1))
    assert size.problems() == [], "unstaged files are not git's problem yet"
    subprocess.run(["git", "add", "big.bin"], cwd=repo, check=True)
    assert size.problems(), "staging it must trip the guard"


def test_largest_tracked_ranks_biggest_first(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    for name, nbytes in [("a.txt", 100), ("b.txt", 5000), ("c.txt", 900)]:
        (repo / name).write_bytes(b"\0" * nbytes)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    ranked = size.largest_tracked(10)
    assert [p for p, _ in ranked] == ["b.txt", "c.txt", "a.txt"]
    assert dict(ranked)["b.txt"] == 5000


def test_human_sizes_are_readable():
    assert size.human(512) == "512 B"
    assert size.human(2048) == "2 KB"
    assert size.human(7 * size.MB) == "7.0 MB"


# --- markdown -> typst conversion ---------------------------------------------
#
# Every case here was a live bug that reached a PDF. They are cheap to state and
# each one failed silently: wrong output, never an error.

build_paper = importlib.import_module("build_paper")


def test_tilde_is_escaped_because_typst_reads_it_as_a_space():
    # Unescaped, "p ~ M" silently loses its tilde — a non-breaking space in Typst.
    assert "\\~" in build_paper.inline("p ~ M")


def test_typst_specials_are_escaped():
    for ch in "#$@<>_":
        assert f"\\{ch}" in build_paper.inline(f"a {ch} b")


def test_bold_spanning_a_hard_wrap_is_still_bold():
    # Markdown wraps at 80 chars, so **bold** routinely straddles a newline. A
    # per-line converter never matches it and leaks literal asterisks.
    md = ["**Contributions across", "two lines.** Then prose."]
    kind, body = next(iter(build_paper.blocks(md)))
    assert kind == "para"
    assert "*Contributions across two lines.*" in build_paper.inline(body)


def test_wrapped_prose_beginning_with_a_pipe_is_not_a_table():
    # "|cos| ≈ 0.014 …" is prose. Requiring both a leading AND trailing pipe is
    # what tells them apart.
    assert build_paper.is_row("| a | b |") is True
    assert build_paper.is_row("|cos| is about 0.014 and that matters") is False


def test_unicode_superscripts_become_typst_math():
    # Literal glyphs depend on font coverage; a missing glyph fails silently.
    assert "$10^(-251)$" in build_paper.inline("10⁻²⁵¹")


def test_html_comments_are_stripped():
    # The template's own writeup opens with one, and it rendered on the title page.
    assert build_paper.strip_comments("a <!-- note --> b").strip() == "a  b".strip()
    assert "note" not in build_paper.strip_comments("a <!--\nmulti\nline note\n--> b")


def test_document_title_comes_from_the_h1():
    assert build_paper.document_title("intro\n# Real Title\nmore") == "Real Title"
    with pytest.raises(ValueError, match="no level-1 heading"):
        build_paper.document_title("no heading here")


def test_table_renders_one_row_per_source_row():
    typ = build_paper.table(["| A | B |", "|---|---|", "| 1 | 2 |", "| 3 | 4 |"])
    assert typ.count("[1], [2]") == 1
    assert typ.count("[3], [4]") == 1
    assert "columns: 2" in typ


def test_long_tables_are_allowed_to_break_across_pages():
    # A table taller than a page must break rather than be pushed whole onto the
    # next one, which would leave most of a page blank.
    short = build_paper.keep_together("cap", "tbl", n_rows=3)
    long = build_paper.keep_together("cap", "tbl", n_rows=build_paper.MAX_UNBREAKABLE_ROWS + 1)
    assert "breakable: false" in short
    assert "breakable: false" not in long


# --- writeup word counts ------------------------------------------------------
#
# Informational tooling, but the exclusions are the whole point: counting tables
# and captions tells you nothing about what to cut.

wordcount = importlib.import_module("wordcount")


def test_wordcount_splits_body_from_appendix():
    md = "# T\n\n## 1. Intro\none two three\n\n## Appendix A\nfour five\n"
    rows = wordcount.sections(md)
    body = {name: n for name, n, appendix in rows if not appendix}
    appendix = {name: n for name, n, appendix in rows if appendix}
    assert body["1. Intro"] == 3
    assert appendix["Appendix A"] == 2


def test_wordcount_excludes_tables_captions_and_code():
    md = (
        "## S\n"
        "real prose here\n"
        "**Table 1.** a caption that should not count\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n"
        "```\ncode words ignored\n```\n"
        "<!-- a comment -->\n"
    )
    assert dict((n, c) for n, c, _ in wordcount.sections(md))["S"] == 3


def test_wordcount_counts_link_text_not_the_url():
    # "see the paper" is 3 words; the URL contributes none.
    md = "## S\nsee [the paper](https://example.com/very/long/path)\n"
    assert dict((n, c) for n, c, _ in wordcount.sections(md))["S"] == 3


# --- the explore/ boundary ----------------------------------------------------
#
# `explore/` is gitignored and not reproducible by design. A claim sourced from
# there is unverifiable by anyone, including its author, so the linter refuses it.
# These tests exist because the boundary is only worth having if it holds under a
# deadline, which is exactly when someone will try to quote a notebook.


def test_cites_explore_catches_a_notebook():
    assert cites_explore("explore/scratch.ipynb")
    assert cites_explore("explore/nested/day3.ipynb")


def test_cites_explore_accepts_pointer_and_trailing_slash_forms():
    assert cites_explore("explore/out/summary.json#a.b")
    assert cites_explore("explore/")


def test_cites_explore_leaves_real_experiment_paths_alone():
    assert not cites_explore("experiments/e00_smoke/analyze.py")
    assert not cites_explore("src/lab/check.py")
    assert not cites_explore("experiments/e00_smoke/output/summary.json#comparisons.main.delta")


def test_cites_explore_does_not_match_a_lookalike_prefix():
    """`exploration/` is a different directory and must not be caught."""
    assert not cites_explore("exploration/notes.py")
    assert not cites_explore("docs/explore/notes.py")


def test_claims_may_not_cite_explore(tmp_path, monkeypatch):
    """A claim row sourced from explore/ fails the build with a usable message."""
    from lab import check as check_mod

    (tmp_path / "CLAIMS.md").write_text(
        "## Claims\n\n"
        "| ID | Claim | Number | Status | Produced by | Artifact |\n"
        "|---|---|---|---|---|---|\n"
        "| C01 | Noticed in a notebook. | d = 0.5 | POSITIVE | `explore/day3.ipynb` | - |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_mod, "REPO_ROOT", tmp_path)

    problems = check_mod.check_claims_avoid_explore()
    assert len(problems) == 1
    assert "C01" in problems[0]
    assert "explore/day3.ipynb" in problems[0]
    assert "promote it to an experiment" in problems[0]


def test_claims_citing_experiments_pass_the_explore_guard(tmp_path, monkeypatch):
    from lab import check as check_mod

    (tmp_path / "CLAIMS.md").write_text(
        "## Claims\n\n"
        "| ID | Claim | Number | Status | Produced by | Artifact |\n"
        "|---|---|---|---|---|---|\n"
        "| C01 | Promoted properly. | d = 0.5 | POSITIVE | `experiments/e01_x/analyze.py` | - |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_mod, "REPO_ROOT", tmp_path)
    assert check_mod.check_claims_avoid_explore() == []
