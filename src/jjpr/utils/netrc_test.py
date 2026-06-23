from pathlib import Path

from . import netrc


class TestRead:
    def test_read_no_netrc(self, tmp_home: Path) -> None:
        assert netrc.read("example.com") is None

    def test_read_success(self, tmp_home: Path) -> None:
        Path(".netrc").write_text("machine example.com login user password pass\n")
        Path(".netrc").chmod(0o600)
        assert netrc.read("example.com") == ("user", "pass")

    def test_read_missing_hostname(self, tmp_home: Path) -> None:
        Path(".netrc").write_text("machine example.com login user password pass\n")
        Path(".netrc").chmod(0o600)
        assert netrc.read("tastycake.com") is None

    def test_read_missing_password(self, tmp_home: Path) -> None:
        Path(".netrc").write_text("machine example.com login user\n")
        Path(".netrc").chmod(0o600)
        assert netrc.read("example.com") is None


class TestWrite:
    def test_write_new_file(self, tmp_home: Path) -> None:
        netrc.write("example.com", "testuser", "testpass")
        rc_path = Path.home() / ".netrc"
        assert rc_path.exists()
        content = rc_path.read_text()
        assert "machine example.com" in content
        assert "login testuser" in content
        assert "password testpass" in content
        # Verify permissions
        assert (rc_path.stat().st_mode & 0o777) == 0o600

    def test_write_append_to_existing(self, tmp_home: Path) -> None:
        rc_path = Path.home() / ".netrc"
        rc_path.write_text("machine first.com\nlogin user1\npassword pass1\n")
        rc_path.chmod(0o600)

        netrc.write("second.com", "user2", "pass2")

        content = rc_path.read_text()
        assert "machine first.com" in content
        assert "machine second.com" in content
        assert "login user1" in content
        assert "login user2" in content
        # Verify permissions are still 0o600
        assert (rc_path.stat().st_mode & 0o777) == 0o600
