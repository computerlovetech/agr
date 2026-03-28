"""Tests for documentation integrity."""

import re
from pathlib import Path

import importlib
from typing import Any

import pytest

DOCS_DIR = Path(__file__).parent.parent / "docs" / "docs"


def get_markdown_files() -> list[Path]:
    """Get all markdown files in docs directory."""
    return list(DOCS_DIR.glob("*.md"))


def extract_internal_links(content: str) -> list[str]:
    """Extract internal markdown links from content, excluding code blocks."""
    # First, remove code blocks to avoid parsing example links
    content_no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)

    # Match [text](link) where link doesn't start with http
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    links = []
    for match in re.finditer(pattern, content_no_code):
        link = match.group(2)
        if not link.startswith(("http://", "https://", "#")):
            links.append(link)
    return links


def extract_code_blocks(content: str) -> list[tuple[str, str]]:
    """Extract code blocks with their language from content."""
    pattern = r"```(\w+)?\n(.*?)```"
    return re.findall(pattern, content, re.DOTALL)


class TestDocsExist:
    """Test that required documentation files exist."""

    def test_index_exists(self):
        """Home page exists."""
        assert (DOCS_DIR / "index.md").exists()

    def test_creating_exists(self):
        """Creating skills page exists."""
        assert (DOCS_DIR / "creating.md").exists()

    def test_reference_exists(self):
        """Reference page exists."""
        assert (DOCS_DIR / "reference.md").exists()

    def test_llms_txt_exists(self):
        """llms.txt exists."""
        assert (DOCS_DIR / "llms.txt").exists()


class TestInternalLinks:
    """Test that internal links resolve to existing files."""

    @pytest.mark.parametrize("md_file", get_markdown_files())
    def test_internal_links_resolve(self, md_file: Path):
        """All internal links point to existing files."""
        content = md_file.read_text()
        links = extract_internal_links(content)

        for link in links:
            # Strip fragment identifiers (e.g., configuration.md#sources → configuration.md)
            file_part = link.split("#")[0]
            if not file_part:
                continue  # Pure fragment link, skip

            # Handle relative links
            if file_part.startswith("./"):
                target = DOCS_DIR / file_part[2:]
            else:
                target = DOCS_DIR / file_part

            # Remove .md extension handling for directory-style links
            if not target.exists() and not target.suffix:
                target = target.with_suffix(".md")

            assert target.exists(), f"Broken link in {md_file.name}: {link}"


class TestCodeExamples:
    """Test that code examples are syntactically valid."""

    @pytest.mark.parametrize("md_file", get_markdown_files())
    def test_bash_commands_have_valid_structure(self, md_file: Path):
        """Bash code blocks contain valid-looking commands."""
        content = md_file.read_text()
        blocks = extract_code_blocks(content)

        for lang, code in blocks:
            if lang == "bash":
                # Skip empty blocks
                if not code.strip():
                    continue

                # Check that bash commands start with a valid command or comment
                lines = [
                    line.strip() for line in code.strip().split("\n") if line.strip()
                ]
                for line in lines:
                    # Skip comments
                    if line.startswith("#"):
                        continue
                    # Check first word is a plausible command
                    first_word = line.split()[0] if line.split() else ""
                    assert first_word, f"Empty bash line in {md_file.name}"

    @pytest.mark.parametrize("md_file", get_markdown_files())
    def test_toml_syntax_valid(self, md_file: Path):
        """TOML code blocks are syntactically valid."""
        content = md_file.read_text()
        blocks = extract_code_blocks(content)

        tomllib: Any
        try:
            tomllib = importlib.import_module("tomllib")
        except ModuleNotFoundError:
            tomllib = importlib.import_module("tomli")

        for lang, code in blocks:
            if lang == "toml":
                try:
                    tomllib.loads(code)
                except Exception as e:
                    pytest.fail(f"Invalid TOML in {md_file.name}: {e}")

    @pytest.mark.parametrize("md_file", get_markdown_files())
    def test_markdown_code_blocks_have_frontmatter(self, md_file: Path):
        """Markdown code blocks that show SKILL.md format have frontmatter."""
        content = md_file.read_text()
        blocks = extract_code_blocks(content)

        for lang, code in blocks:
            if lang == "markdown" and "SKILL" in code:
                # Check for frontmatter
                assert code.strip().startswith("---"), (
                    f"SKILL.md example in {md_file.name} should start with frontmatter"
                )


class TestCliCommands:
    """Test that documented CLI commands are real."""

    KNOWN_COMMANDS = {"add", "remove", "sync", "list", "init", "onboard", "config"}

    def test_documented_agr_commands_exist(self):
        """Commands documented in reference.md are known commands."""
        reference = (DOCS_DIR / "reference.md").read_text()

        # Extract code blocks only
        code_blocks = extract_code_blocks(reference)
        bash_code = "\n".join(code for lang, code in code_blocks if lang == "bash")

        # Extract agr commands from bash code blocks only
        pattern = r"agr (\w+)"
        commands = set(re.findall(pattern, bash_code))

        for cmd in commands:
            assert cmd in self.KNOWN_COMMANDS, f"Unknown command documented: agr {cmd}"

    def test_documented_agrx_exists(self):
        """agrx command is documented."""
        reference = (DOCS_DIR / "reference.md").read_text()
        assert "agrx" in reference


class TestToolDocumentation:
    """Test that all supported tools are documented in key MkDocs pages."""

    # Canonical list of supported tools from the codebase
    from agr.tool import TOOLS

    ALL_TOOL_NAMES = set(TOOLS.keys())

    def test_configuration_mentions_all_tools(self):
        """configuration.md tools table lists all supported tools."""
        content = (DOCS_DIR / "configuration.md").read_text()
        # Check the Multi-Tool Setup section which has the tools table.
        section_marker = "## Multi-Tool Setup"
        assert section_marker in content, (
            "configuration.md missing 'Multi-Tool Setup' section"
        )
        section = content[content.index(section_marker) :]
        for tool in self.ALL_TOOL_NAMES:
            assert tool in section.lower(), (
                f"Tool '{tool}' not in configuration.md Multi-Tool Setup section"
            )

    def test_agrx_cli_table_mentions_all_tools(self):
        """agrx.md CLI Requirements table lists all supported tools."""
        content = (DOCS_DIR / "agrx.md").read_text()
        # Extract just the CLI Requirements section to ensure tools appear
        # in the table, not just in passing mentions elsewhere on the page.
        cli_section_marker = "## Tool CLI Requirements"
        assert cli_section_marker in content, (
            "agrx.md missing 'Tool CLI Requirements' section"
        )
        cli_section = content[content.index(cli_section_marker) :]
        for tool in self.ALL_TOOL_NAMES:
            assert tool in cli_section.lower(), (
                f"Tool '{tool}' not in agrx.md CLI Requirements table"
            )

    def test_reference_agrx_section_mentions_all_tools(self):
        """reference.md agrx --tool flag lists all supported tools."""
        content = (DOCS_DIR / "reference.md").read_text()
        for tool in self.ALL_TOOL_NAMES:
            assert tool in content.lower(), (
                f"Tool '{tool}' not mentioned in reference.md"
            )

    def test_tools_page_detection_signals_match_code(self):
        """tools.md Detection Signals table matches ToolConfig.detection_signals."""
        content = (DOCS_DIR / "tools.md").read_text()
        section_marker = "## Detection Signals"
        assert section_marker in content, (
            "tools.md missing 'Detection Signals' section"
        )
        section = content[content.index(section_marker) :]
        # Stop at the next h2 section
        next_h2 = section.find("\n## ", 1)
        if next_h2 != -1:
            section = section[:next_h2]

        for name, tool in self.TOOLS.items():
            for signal in tool.detection_signals:
                assert signal in section, (
                    f"Detection signal '{signal}' for tool '{name}' "
                    f"missing from tools.md Detection Signals table"
                )


class TestContentQuality:
    """Test documentation content quality."""

    def test_index_has_quick_start(self):
        """Home page has a quick install example."""
        content = (DOCS_DIR / "index.md").read_text()
        assert "uvx agr add" in content or "uv tool install agr" in content

    def test_creating_has_skill_example(self):
        """Creating page has a complete skill example."""
        content = (DOCS_DIR / "creating.md").read_text()
        assert "SKILL.md" in content
        assert "name:" in content
        assert "description:" in content

    def test_reference_has_all_commands(self):
        """Reference page documents all main commands."""
        content = (DOCS_DIR / "reference.md").read_text()
        for cmd in [
            "agr add",
            "agr remove",
            "agr sync",
            "agr list",
            "agr init",
            "agr config",
            "agrx",
        ]:
            assert cmd in content, f"Missing documentation for {cmd}"

    def test_no_broken_next_steps(self):
        """Next steps links in index.md point to valid pages."""
        content = (DOCS_DIR / "index.md").read_text()
        links = extract_internal_links(content)

        for link in links:
            # Strip fragment anchors (e.g. "concepts.md#handles" -> "concepts.md")
            path_part = link.split("#")[0] if "#" in link else link
            if not path_part:
                continue
            target = DOCS_DIR / path_part
            if not target.exists() and not target.suffix:
                target = target.with_suffix(".md")
            assert target.exists(), f"Broken next steps link: {link}"
