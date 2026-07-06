"""
Template Engine

Loads template markdown files and populates them with item data.
Validates that rendered output conforms to template structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class TemplateEngine:
    """Manages loading and rendering knowledge base templates."""

    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self._cache: dict[str, str] = {}

    def load_template(self, name: str) -> str:
        """Load a template by name (without .md extension)."""
        if name in self._cache:
            return self._cache[name]

        template_path = self.template_dir / f"{name}.md"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        content = template_path.read_text(encoding="utf-8")
        self._cache[name] = content
        return content

    def render(self, template_name: str, **kwargs: Any) -> str:
        """
        Render a template with the given variables.

        Args:
            template_name: Name of the template (e.g., 'knowledge', 'memory', 'artifact')
            **kwargs: Variables to substitute in the template.

        Returns:
            Rendered markdown string.
        """
        template = self.load_template(template_name)

        # Simple {placeholder} substitution
        result = template
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                # Convert lists to comma-separated strings
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                elif not isinstance(value, str):
                    value = str(value)
                result = result.replace(placeholder, value)

        # Warn about unreplaced placeholders but don't crash
        import re
        remaining = re.findall(r"\{(\w+)\}", result)
        if remaining:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Unreplaced placeholders in template '%s': %s",
                template_name,
                remaining,
            )

        return result

    def validate_rendered(self, content: str, template_name: str) -> bool:
        """
        Validate that the rendered content still has the required structure.
        Checks that all section headers from the template are present.
        """
        template = self.load_template(template_name)
        import re

        # Extract ## headers from the template (required sections)
        template_headers = set(re.findall(r"^## (.+)$", template, re.MULTILINE))
        content_headers = set(re.findall(r"^## (.+)$", content, re.MULTILINE))

        missing = template_headers - content_headers
        if missing:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Template '%s' missing sections: %s",
                template_name,
                missing,
            )
            return False
        return True
