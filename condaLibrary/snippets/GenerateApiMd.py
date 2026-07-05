# FileName: GenerateApiMd.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Generate Markdown API documentation from the final snippet descriptions."""

import textwrap
from typing import cast

from ApiConfig import DictSnippetsItem
from GenerateApiData import DictApiItem, DictOverloadInfo
from SnippetUtils import get_snippets_dir, read_json


def _parse_docstring_sections(docstring: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"description": []}
    current = "description"

    sectionHeaders = {
        "Parameters:": "parameters",
        "Returns:": "returns",
        "Raises:": "raises",
        "Examples:": "examples",
        "Example:": "examples",
        "Usage Example:": "usageExample",
        "Usage Examples:": "usageExample",
        "Notes:": "notes",
    }

    for line in docstring.splitlines():
        stripped = line.strip()
        sectionKey = sectionHeaders.get(stripped)
        if sectionKey is not None:
            current = sectionKey
            sections.setdefault(current, [])
            continue

        sections.setdefault(current, []).append(line)

    return {key: textwrap.dedent("\n".join(lines)).strip() for key, lines in sections.items()}


def _render_code_section(title: str, content: str) -> str:
    return f"{title}:\n\n```text\n{content}\n```"


def _render_python_section(title: str, content: str) -> str:
    return f"{title}:\n\n```python\n{content}\n```"


def _render_markdown_section(title: str, content: str) -> str:
    return f"{title}:\n\n{content}"


def _render_overload_signatures(overloads: list[DictOverloadInfo]) -> str:
    if not overloads:
        return ""

    lines: list[str] = []
    for overload in overloads:
        lines.append("@overload")
        lines.append(f"def {overload['signature']}: ...")

    return _render_python_section(title="Overload signatures", content="\n".join(lines))


def _render_description(description: str, overloads: list[DictOverloadInfo]) -> str:
    if not description:
        return ""

    sections = _parse_docstring_sections(description)
    parts: list[str] = []

    descriptionText = sections.get("description", "")
    if descriptionText:
        parts.append(descriptionText)

    overloadsText = _render_overload_signatures(overloads=overloads)
    if overloadsText:
        parts.append(overloadsText)

    parametersText = sections.get("parameters", "")
    if parametersText:
        parts.append(_render_code_section(title="Parameters", content=parametersText))

    returnsText = sections.get("returns", "")
    if returnsText:
        parts.append(_render_code_section(title="Returns", content=returnsText))

    raisesText = sections.get("raises", "")
    if raisesText:
        parts.append(_render_code_section(title="Raises", content=raisesText))

    notesText = sections.get("notes", "")
    if notesText:
        parts.append(_render_markdown_section(title="Notes", content=notesText))

    examplesText = sections.get("examples", "")
    if examplesText:
        parts.append(_render_markdown_section(title="Examples", content=examplesText))

    usageExampleText = sections.get("usageExample", "")
    if usageExampleText:
        parts.append(_render_markdown_section(title="Usage Example", content=usageExampleText))

    return "\n\n".join(parts)


def _load_api_manifest_by_title() -> dict[str, DictApiItem]:
    manifestPath = get_snippets_dir() / "api_manifest.json"
    if not manifestPath.is_file():
        return {}

    apiManifest = cast(list[DictApiItem], read_json(manifestPath, list))
    return {item["title"]: item for item in apiManifest}


def _generate_api_markdown(dictSnippets: dict[str, DictSnippetsItem]) -> str:
    markdownParts: list[str] = []
    currentModule: str | None = None
    apiManifestByTitle = _load_api_manifest_by_title()

    for title, snippet in dictSnippets.items():
        if "." in title:
            moduleName, functionName = title.split(".", maxsplit=1)
        else:
            moduleName = "Other"
            functionName = title

        if moduleName != currentModule:
            currentModule = moduleName
            markdownParts.append(f"## {moduleName}")

        markdownParts.append(f"### {functionName}")

        apiItem = apiManifestByTitle.get(title)
        overloads = apiItem.get("overloads", []) if apiItem is not None else []

        description = snippet.get("description", "")
        renderedDescription = _render_description(description=description, overloads=overloads)
        if renderedDescription:
            markdownParts.append(renderedDescription)
        else:
            raise ValueError(f"No description.{currentModule}")

    return "\n\n".join(markdownParts).strip() + "\n"


def main() -> None:
    snippetsDir = get_snippets_dir()
    snippetsPath = snippetsDir / "snippets_final.snippets"
    dictSnippets = cast(dict[str, DictSnippetsItem], read_json(snippetsPath, dict))
    apiMarkdown = _generate_api_markdown(dictSnippets=dictSnippets)
    (snippetsDir / "api.md").write_text(apiMarkdown, encoding="utf-8")
    # Then copy the content of api.md into README.md.


if __name__ == "__main__":
    main()
