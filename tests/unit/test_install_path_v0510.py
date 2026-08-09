from sric.install_path import append_path, path_contains


def test_path_contains_is_case_and_separator_insensitive() -> None:
    existing = r"C:\\Windows;C:\\Users\\Alice\\.local\\bin\\"
    assert path_contains(existing, r"c:\\users\\alice\\.local\\bin") is True


def test_append_path_is_idempotent() -> None:
    existing = r"C:\\Windows;C:\\Tools"
    assert append_path(existing, r"C:\\Tools") == existing
    assert append_path(existing, r"C:\\Users\\Alice\\.local\\bin") == (
        existing + r";C:\\Users\\Alice\\.local\\bin"
    )


def test_append_path_handles_empty_user_path() -> None:
    assert append_path("", r"C:\\Users\\Alice\\.local\\bin") == r"C:\\Users\\Alice\\.local\\bin"
