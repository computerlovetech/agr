"""Tests for agr.metadata module."""

import json
import re
from pathlib import Path

from agr.handle import ParsedHandle
from agr.metadata import (
    METADATA_FILENAME,
    METADATA_KEY_HANDLE,
    METADATA_KEY_INSTALLED_NAME,
    METADATA_KEY_LOCAL_PATH,
    METADATA_KEY_SOURCE,
    METADATA_KEY_TOOL,
    METADATA_KEY_TYPE,
    METADATA_TYPE_LOCAL,
    METADATA_TYPE_REMOTE,
    build_handle_id,
    build_handle_ids,
    compute_content_hash,
    read_skill_metadata,
    stamp_skill_metadata,
    write_skill_metadata,
)
from agr.source import DEFAULT_SOURCE_NAME


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_deterministic(self, tmp_path: Path):
        """Same directory produces the same hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "helper.py").write_text("print('hi')")

        hash1 = compute_content_hash(skill_dir)
        hash2 = compute_content_hash(skill_dir)
        assert hash1 == hash2

    def test_format(self, tmp_path: Path):
        """Hash matches sha256:<64 hex chars> format."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_excludes_agr_json(self, tmp_path: Path):
        """Adding .agr.json does not change the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        hash_before = compute_content_hash(skill_dir)
        (skill_dir / METADATA_FILENAME).write_text('{"id": "test"}')
        hash_after = compute_content_hash(skill_dir)

        assert hash_before == hash_after

    def test_detects_rename(self, tmp_path: Path):
        """Renaming a file changes the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "a.py").write_text("code")

        hash1 = compute_content_hash(skill_dir)
        (skill_dir / "a.py").rename(skill_dir / "b.py")
        hash2 = compute_content_hash(skill_dir)

        assert hash1 != hash2

    def test_detects_content_change(self, tmp_path: Path):
        """Changing file contents changes the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        hash1 = compute_content_hash(skill_dir)
        (skill_dir / "SKILL.md").write_text("# Changed")
        hash2 = compute_content_hash(skill_dir)

        assert hash1 != hash2

    def test_handles_binary(self, tmp_path: Path):
        """Binary files are hashed correctly."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "data.bin").write_bytes(b"\x00\x01\x02\xff")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_sorts_by_posix_path(self, tmp_path: Path):
        """Hash is the same regardless of file creation order."""
        # Create dir1 with files in one order
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "b.txt").write_text("B")
        (dir1 / "a.txt").write_text("A")

        # Create dir2 with files in reverse order
        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "a.txt").write_text("A")
        (dir2 / "b.txt").write_text("B")

        assert compute_content_hash(dir1) == compute_content_hash(dir2)

    def test_empty_dir(self, tmp_path: Path):
        """Empty directory produces a valid hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_single_file(self, tmp_path: Path):
        """Single file produces a valid hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Only file")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)


class TestWriteSkillMetadataContentHash:
    """Tests for content_hash parameter in write_skill_metadata."""

    def test_includes_content_hash(self, tmp_path: Path):
        """content_hash is written when provided."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        handle = ParsedHandle(is_local=True, name="test", local_path=skill_dir)
        write_skill_metadata(
            skill_dir,
            handle,
            tmp_path,
            "claude",
            "test",
            content_hash="sha256:abc123",
        )

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert meta["content_hash"] == "sha256:abc123"

    def test_omits_hash_when_none(self, tmp_path: Path):
        """content_hash key is absent when not provided."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        handle = ParsedHandle(is_local=True, name="test", local_path=skill_dir)
        write_skill_metadata(skill_dir, handle, tmp_path, "claude", "test")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert "content_hash" not in meta


class TestReadSkillMetadata:
    """Tests for read_skill_metadata function."""

    def test_returns_none_for_missing_file(self, tmp_path: Path):
        """Returns None when .agr.json does not exist."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        assert read_skill_metadata(skill_dir) is None

    def test_reads_valid_metadata(self, tmp_path: Path):
        """Reads and returns valid JSON metadata."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        data = {"id": "remote:github:user/skill", "tool": "claude", "type": "remote"}
        (skill_dir / METADATA_FILENAME).write_text(json.dumps(data))

        result = read_skill_metadata(skill_dir)
        assert result == data

    def test_returns_none_for_invalid_json(self, tmp_path: Path):
        """Returns None when .agr.json contains invalid JSON."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / METADATA_FILENAME).write_text("not valid json {{{")

        assert read_skill_metadata(skill_dir) is None

    def test_returns_none_for_non_dict_json(self, tmp_path: Path):
        """Returns None when .agr.json contains a JSON array instead of object."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / METADATA_FILENAME).write_text('["not", "a", "dict"]')

        assert read_skill_metadata(skill_dir) is None

    def test_returns_none_for_empty_file(self, tmp_path: Path):
        """Returns None when .agr.json is empty."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / METADATA_FILENAME).write_text("")

        assert read_skill_metadata(skill_dir) is None


class TestBuildHandleId:
    """Tests for build_handle_id function."""

    def test_local_handle(self, tmp_path: Path):
        """Local handle produces 'local:<resolved_path>' ID."""
        local_path = tmp_path / "my-skill"
        handle = ParsedHandle(is_local=True, name="my-skill", local_path=local_path)

        result = build_handle_id(handle, tmp_path)
        assert result == f"local:{local_path.resolve()}"

    def test_local_handle_relative_path(self, tmp_path: Path):
        """Local handle with relative path resolves against repo_root."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("./skills/my-skill")
        )

        result = build_handle_id(handle, tmp_path)
        assert result == f"local:{(tmp_path / 'skills' / 'my-skill').resolve()}"

    def test_local_handle_no_path(self):
        """Local handle with no local_path produces 'local:' ID."""
        handle = ParsedHandle(is_local=True, name="my-skill", local_path=None)

        result = build_handle_id(handle, None)
        assert result == "local:"

    def test_remote_two_part_no_source(self):
        """Remote two-part handle without source omits source prefix."""
        handle = ParsedHandle(username="user", name="skill")

        result = build_handle_id(handle, None)
        assert result == "remote:user/skill"

    def test_remote_three_part_no_source(self):
        """Remote three-part handle without source omits source prefix."""
        handle = ParsedHandle(username="user", repo="myrepo", name="skill")

        result = build_handle_id(handle, None)
        assert result == "remote:user/myrepo/skill"

    def test_remote_with_source(self):
        """Remote handle with explicit source includes source in ID."""
        handle = ParsedHandle(username="user", name="skill")

        result = build_handle_id(handle, None, source="github")
        assert result == "remote:github:user/skill"

    def test_remote_with_custom_source(self):
        """Remote handle with custom source includes it in the ID."""
        handle = ParsedHandle(username="user", repo="repo", name="skill")

        result = build_handle_id(handle, None, source="gitlab")
        assert result == "remote:gitlab:user/repo/skill"

    def test_same_handle_different_sources_differ(self):
        """Same handle with different sources produces different IDs."""
        handle = ParsedHandle(username="user", name="skill")

        id_github = build_handle_id(handle, None, source="github")
        id_gitlab = build_handle_id(handle, None, source="gitlab")
        id_none = build_handle_id(handle, None)

        assert id_github != id_gitlab
        assert id_github != id_none


class TestBuildHandleIds:
    """Tests for build_handle_ids function."""

    def test_local_handle_returns_single_id(self, tmp_path: Path):
        """Local handles produce exactly one ID (no legacy variants)."""
        local_path = tmp_path / "my-skill"
        handle = ParsedHandle(is_local=True, name="my-skill", local_path=local_path)

        ids = build_handle_ids(handle, tmp_path, source=None)

        assert len(ids) == 1
        assert ids[0] == f"local:{local_path.resolve()}"

    def test_remote_no_source_includes_default_variant(self):
        """Remote handle with source=None also generates DEFAULT_SOURCE_NAME variant."""
        handle = ParsedHandle(username="user", name="skill")

        ids = build_handle_ids(handle, None, source=None)

        assert len(ids) == 2
        assert ids[0] == "remote:user/skill"
        assert ids[1] == f"remote:{DEFAULT_SOURCE_NAME}:user/skill"

    def test_remote_default_source_includes_no_source_variant(self):
        """Remote handle with source=DEFAULT_SOURCE_NAME also generates sourceless variant."""
        handle = ParsedHandle(username="user", name="skill")

        ids = build_handle_ids(handle, None, source=DEFAULT_SOURCE_NAME)

        assert len(ids) == 2
        assert ids[0] == f"remote:{DEFAULT_SOURCE_NAME}:user/skill"
        assert ids[1] == "remote:user/skill"

    def test_remote_custom_source_returns_single_id(self):
        """Remote handle with a custom source produces exactly one ID."""
        handle = ParsedHandle(username="user", repo="repo", name="skill")

        ids = build_handle_ids(handle, None, source="gitlab")

        assert len(ids) == 1
        assert ids[0] == "remote:gitlab:user/repo/skill"

    def test_three_part_handle_no_source(self):
        """Three-part remote handle with source=None includes default variant."""
        handle = ParsedHandle(username="user", repo="myrepo", name="skill")

        ids = build_handle_ids(handle, None, source=None)

        assert len(ids) == 2
        assert ids[0] == "remote:user/myrepo/skill"
        assert ids[1] == f"remote:{DEFAULT_SOURCE_NAME}:user/myrepo/skill"

    def test_three_part_handle_default_source(self):
        """Three-part remote handle with DEFAULT_SOURCE_NAME includes sourceless variant."""
        handle = ParsedHandle(username="user", repo="myrepo", name="skill")

        ids = build_handle_ids(handle, None, source=DEFAULT_SOURCE_NAME)

        assert len(ids) == 2
        assert ids[0] == f"remote:{DEFAULT_SOURCE_NAME}:user/myrepo/skill"
        assert ids[1] == "remote:user/myrepo/skill"


class TestStampSkillMetadata:
    """Tests for stamp_skill_metadata function."""

    def test_writes_metadata_with_content_hash(self, tmp_path: Path):
        """stamp_skill_metadata computes a hash and writes it to metadata."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# My Skill\nInstructions here.")

        handle = ParsedHandle(username="user", name="my-skill")
        stamp_skill_metadata(skill_dir, handle, tmp_path, "claude", "my-skill")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert "content_hash" in meta
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", meta["content_hash"])

    def test_content_hash_matches_compute(self, tmp_path: Path):
        """The hash in metadata matches a direct compute_content_hash call."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")

        handle = ParsedHandle(username="user", name="my-skill")
        stamp_skill_metadata(skill_dir, handle, tmp_path, "claude", "my-skill")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        # The hash was computed before .agr.json was written, and
        # compute_content_hash excludes .agr.json, so they should match.
        assert meta["content_hash"] == compute_content_hash(skill_dir)

    def test_writes_remote_metadata_fields(self, tmp_path: Path):
        """Remote handle metadata includes type, handle, and source fields."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")

        handle = ParsedHandle(username="owner", repo="repo", name="my-skill")
        stamp_skill_metadata(
            skill_dir, handle, tmp_path, "cursor", "my-skill", source="github"
        )

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert meta[METADATA_KEY_TYPE] == METADATA_TYPE_REMOTE
        assert meta[METADATA_KEY_HANDLE] == "owner/repo/my-skill"
        assert meta[METADATA_KEY_SOURCE] == "github"
        assert meta[METADATA_KEY_TOOL] == "cursor"
        assert meta[METADATA_KEY_INSTALLED_NAME] == "my-skill"

    def test_writes_local_metadata_fields(self, tmp_path: Path):
        """Local handle metadata includes type and local_path fields."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        stamp_skill_metadata(skill_dir, handle, tmp_path, "claude", "my-skill")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert meta[METADATA_KEY_TYPE] == METADATA_TYPE_LOCAL
        assert meta[METADATA_KEY_LOCAL_PATH] == str(skill_dir.resolve())

    def test_source_defaults_to_default_source_name(self, tmp_path: Path):
        """Remote handle without explicit source uses DEFAULT_SOURCE_NAME."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")

        handle = ParsedHandle(username="user", name="my-skill")
        stamp_skill_metadata(skill_dir, handle, tmp_path, "claude", "my-skill")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert meta[METADATA_KEY_SOURCE] == DEFAULT_SOURCE_NAME
