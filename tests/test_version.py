import ctx


def test_version_has_no_debian_revision():
    assert ctx.__version__
    assert "-" not in ctx.__version__
