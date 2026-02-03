"""Build markdown graph-context sections for the LLM prompt."""


def build_graph_context_section(graph_context: dict) -> str:
    """Build a markdown section from graph context for the LLM prompt."""
    parts: list[str] = []

    affected = graph_context.get("affected_symbols", [])
    if affected:
        parts.append("**Affected Symbols:**")
        for sym in affected[:20]:
            source_snippet = (sym.get("source") or "")[:1000]
            parts.append(
                f"- `{sym.get('name')}` ({sym.get('type')}) "
                f"in `{sym.get('change_file')}` lines {sym.get('start_line')}-{sym.get('end_line')}"
            )
            if source_snippet:
                parts.append(f"  ```\n  {source_snippet}\n  ```")

    imports = graph_context.get("imports", [])
    if imports:
        parts.append("\n**Imported Functions (used in changes):**")
        for imp in imports[:10]:
            parts.append(
                f"- `{imp.get('name')}` ({imp.get('type')}) imported in `{imp.get('from_file')}`"
            )
            parts.append(f"  Source from `{imp.get('path')}`:")
            imp_source = (imp.get("source") or "")[:1500]
            if imp_source:
                parts.append(f"  ```\n  {imp_source}\n  ```")
            elif imp.get("docstring"):
                parts.append(f"  ```\n  {imp.get('docstring')}\n  ```")

    dependencies = graph_context.get("dependencies", [])
    if dependencies:
        parts.append("\n**Dependencies (what changed functions call):**")
        for dep in dependencies[:10]:
            parts.append(f"- `{dep['symbol']}` calls:")
            for d in dep.get("dependencies", [])[:5]:
                parts.append(f"  - `{d.get('name')}` in `{d.get('path')}`")

    callers = graph_context.get("callers", [])
    if callers:
        parts.append("\n**Downstream Callers:**")
        for entry in callers[:10]:
            parts.append(f"- `{entry['symbol']}` ({entry['symbol_type']}) is called by:")
            for c in entry.get("callers", [])[:5]:
                caller_info = f"  - `{c.get('name')}` in `{c.get('path')}`"
                if c.get("call_line"):
                    caller_info += f" (line {c.get('call_line')})"
                parts.append(caller_info)

    hierarchy = graph_context.get("class_hierarchy", [])
    if hierarchy:
        parts.append("\n**Class Hierarchy:**")
        for entry in hierarchy[:5]:
            parents = entry.get("parents", [])
            if parents:
                parent_names = " -> ".join(p.get("parent_class", "?") for p in parents[:3])
                parts.append(f"- `{entry['class']}` inherits from: {parent_names}")
            children = entry.get("children", [])
            if children:
                child_names = ", ".join(c.get("child_class", "?") for c in children[:3])
                parts.append(f"  Inherited by: {child_names}")

    return "\n".join(parts) if parts else "No graph context available."
