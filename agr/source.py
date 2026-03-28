"""Source configuration and resolution."""

from __future__ import annotations

from dataclasses import dataclass

from agr.exceptions import AgrError

DEFAULT_SOURCE_NAME = "github"
DEFAULT_GITHUB_URL = "https://github.com/{owner}/{repo}.git"
SOURCE_TYPE_GIT = "git"


@dataclass(frozen=True)
class SourceConfig:
    """Configuration for a remote source."""

    name: str
    type: str
    url: str

    def build_repo_url(self, owner: str, repo: str) -> str:
        """Build the repository URL for this source."""
        return self.url.format(owner=owner, repo=repo)


def default_sources() -> list[SourceConfig]:
    """Return the default source list (GitHub)."""
    return [
        SourceConfig(
            name=DEFAULT_SOURCE_NAME,
            type=SOURCE_TYPE_GIT,
            url=DEFAULT_GITHUB_URL,
        )
    ]


@dataclass
class SourceResolver:
    """Resolve sources in the correct priority order."""

    sources: list[SourceConfig]
    default_source: str = DEFAULT_SOURCE_NAME

    @classmethod
    def default(cls) -> SourceResolver:
        """Create a resolver with the default GitHub source."""
        return cls(default_sources(), DEFAULT_SOURCE_NAME)

    def get(self, name: str) -> SourceConfig:
        """Get a source by name."""
        for source in self.sources:
            if source.name == name:
                return source
        raise AgrError(f"Unknown source '{name}'.")

    def ordered(self, explicit: str | None = None) -> list[SourceConfig]:
        """Return sources in priority order."""
        if explicit:
            return [self.get(explicit)]
        if not self.sources:
            return default_sources()
        default = (
            self.get(self.default_source) if self.default_source else self.sources[0]
        )
        return [default] + [s for s in self.sources if s.name != default.name]
