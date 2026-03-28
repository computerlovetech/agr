"""Unit tests for agr.source module."""

import pytest

from agr.exceptions import AgrError
from agr.source import (
    DEFAULT_GITHUB_URL,
    DEFAULT_SOURCE_NAME,
    SourceConfig,
    SourceResolver,
    default_sources,
)


class TestSourceConfig:
    """Tests for SourceConfig."""

    def test_build_repo_url_github(self) -> None:
        source = SourceConfig(name="github", type="git", url=DEFAULT_GITHUB_URL)
        assert source.build_repo_url("alice", "skills") == (
            "https://github.com/alice/skills.git"
        )

    def test_build_repo_url_custom_host(self) -> None:
        source = SourceConfig(
            name="gitlab",
            type="git",
            url="https://gitlab.com/{owner}/{repo}.git",
        )
        assert source.build_repo_url("bob", "tools") == (
            "https://gitlab.com/bob/tools.git"
        )

    def test_build_repo_url_no_git_suffix(self) -> None:
        source = SourceConfig(
            name="custom",
            type="git",
            url="https://example.com/{owner}/{repo}",
        )
        assert source.build_repo_url("user", "repo") == (
            "https://example.com/user/repo"
        )


class TestDefaultSources:
    """Tests for default_sources helper."""

    def test_returns_single_github_source(self) -> None:
        sources = default_sources()
        assert len(sources) == 1
        assert sources[0].name == DEFAULT_SOURCE_NAME
        assert sources[0].type == "git"
        assert sources[0].url == DEFAULT_GITHUB_URL

    def test_returns_fresh_list_each_call(self) -> None:
        a = default_sources()
        b = default_sources()
        assert a == b
        assert a is not b


class TestSourceResolver:
    """Tests for SourceResolver."""

    def test_default_factory(self) -> None:
        resolver = SourceResolver.default()
        assert len(resolver.sources) == 1
        assert resolver.default_source == DEFAULT_SOURCE_NAME

    def test_get_existing_source(self) -> None:
        resolver = SourceResolver.default()
        source = resolver.get("github")
        assert source.name == "github"

    def test_get_unknown_source_raises(self) -> None:
        resolver = SourceResolver.default()
        with pytest.raises(AgrError, match="Unknown source 'nonexistent'"):
            resolver.get("nonexistent")

    def test_ordered_no_explicit_returns_default_first(self) -> None:
        s1 = SourceConfig(
            name="primary", type="git", url="https://a.com/{owner}/{repo}"
        )
        s2 = SourceConfig(
            name="secondary", type="git", url="https://b.com/{owner}/{repo}"
        )
        resolver = SourceResolver(sources=[s1, s2], default_source="primary")

        ordered = resolver.ordered()
        assert [s.name for s in ordered] == ["primary", "secondary"]

    def test_ordered_default_not_first_in_list(self) -> None:
        s1 = SourceConfig(name="alpha", type="git", url="https://a.com/{owner}/{repo}")
        s2 = SourceConfig(name="beta", type="git", url="https://b.com/{owner}/{repo}")
        resolver = SourceResolver(sources=[s1, s2], default_source="beta")

        ordered = resolver.ordered()
        assert ordered[0].name == "beta"
        assert ordered[1].name == "alpha"

    def test_ordered_explicit_returns_only_that_source(self) -> None:
        s1 = SourceConfig(name="a", type="git", url="https://a.com/{owner}/{repo}")
        s2 = SourceConfig(name="b", type="git", url="https://b.com/{owner}/{repo}")
        resolver = SourceResolver(sources=[s1, s2], default_source="a")

        ordered = resolver.ordered(explicit="b")
        assert len(ordered) == 1
        assert ordered[0].name == "b"

    def test_ordered_explicit_unknown_raises(self) -> None:
        resolver = SourceResolver.default()
        with pytest.raises(AgrError, match="Unknown source"):
            resolver.ordered(explicit="nope")

    def test_ordered_empty_sources_returns_defaults(self) -> None:
        resolver = SourceResolver(sources=[], default_source="")

        ordered = resolver.ordered()
        assert len(ordered) == 1
        assert ordered[0].name == DEFAULT_SOURCE_NAME

    def test_ordered_single_source(self) -> None:
        s = SourceConfig(name="only", type="git", url="https://x.com/{owner}/{repo}")
        resolver = SourceResolver(sources=[s], default_source="only")

        ordered = resolver.ordered()
        assert len(ordered) == 1
        assert ordered[0].name == "only"

    def test_ordered_no_duplicate_default(self) -> None:
        """Default source should not appear twice in the ordered list."""
        s1 = SourceConfig(name="main", type="git", url="https://a.com/{owner}/{repo}")
        s2 = SourceConfig(name="other", type="git", url="https://b.com/{owner}/{repo}")
        resolver = SourceResolver(sources=[s1, s2], default_source="main")

        ordered = resolver.ordered()
        names = [s.name for s in ordered]
        assert names == ["main", "other"]
        assert len(set(names)) == len(names)
