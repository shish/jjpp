from . import text


class TestRemoveAnsi:
    def test_strip(self) -> None:
        assert text.remove_ansi("\x1b[31mHello\x1b[0m") == "Hello"
