from hipda_cli.text import segment_text


def test_segment_text_returns_space_separated_tokens_for_cjk():
    result = segment_text("半导体依然疯了")
    tokens = result.split()

    assert len(tokens) >= 2
    assert "半导体" in tokens


def test_segment_text_passes_through_ascii_words():
    assert segment_text("Hello World") == "Hello World"


def test_segment_text_handles_empty_string():
    assert segment_text("") == ""


def test_segment_text_drops_only_pure_whitespace_tokens():
    assert segment_text("半导体   反弹").split() == ["半导体", "反弹"]
