from __future__ import annotations

from scripts.external_dataset_manager import main


def test_download_command_refuses_without_flags() -> None:
    status = main(["download", "--dataset", "footgait3d"])

    assert status == 1


def test_print_download_instructions_works(capsys) -> None:
    status = main(["print-download-instructions", "--dataset", "focus_synfoot2_foot3d"])
    captured = capsys.readouterr()

    assert status == 0
    assert "External datasets are research-only and not accuracy proof." in captured.out
    assert "https://github.com/OllieBoyne/FOCUS" in captured.out


def test_list_command_works(capsys) -> None:
    status = main(["list"])
    captured = capsys.readouterr()

    assert status == 0
    assert "focus_synfoot2_foot3d" in captured.out
