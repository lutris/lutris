from lutris.api import normalize_version_architecture


def test_normalize_preserves_ge_proton_tags() -> None:
    assert normalize_version_architecture("GE-Proton11-7") == "GE-Proton11-7"
