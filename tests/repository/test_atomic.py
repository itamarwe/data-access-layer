from __future__ import annotations

import os

import pytest

import dal.repository.atomic as atomic


def test_multi_file_replacement_rolls_back_an_io_failure(tmp_path, monkeypatch):
    first = tmp_path / "semantic" / "a.yaml"
    second = tmp_path / "proposals" / "b.yaml"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("before-a", encoding="utf-8")
    second.write_text("before-b", encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def fail_second_replace(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected failure")
        return real_replace(source, target)

    monkeypatch.setattr(atomic.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="injected"):
        atomic.replace_texts({first: "after-a", second: "after-b"})

    assert first.read_text(encoding="utf-8") == "before-a"
    assert second.read_text(encoding="utf-8") == "before-b"
