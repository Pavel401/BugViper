"""Build markdown graph-context sections for the LLM prompt."""


def build_graph_context_section(graph_context: dict) -> str:
    """Build a markdown section from graph context for the LLM prompt."""
    parts: list[str] = []

    affected = graph_context.get("affected_symbols", [])
    if affected:
        parts.append("**Affected Symbols:**")
        parts.append(f"*{len(affected)} symbols modified in this PR*")
        parts.append("")
        
        for sym in affected[:20]:  # Limit to top 20 to avoid overwhelming context
            # Full source, not truncated - we need complete context
            source = sym.get("source") or ""
            
            parts.append(
                f"### `{sym.get('name')}` ({sym.get('type')})"
            )
            parts.append(f"**File:** `{sym.get('change_file')}` (lines {sym.get('start_line')}-{sym.get('end_line')})")
            
            # Add docstring if available
            if sym.get("docstring"):
                parts.append(f"**Doc:** {sym.get('docstring')[:200]}...")
            
            # Show full source with reasonable limit (10K chars max per symbol)
            if source:
                if len(source) > 10000:
                    source = source[:10000] + "\n# ... (source truncated - function too large)"
                parts.append("```python")
                parts.append(source)
                parts.append("```")
            parts.append("")

    imports = graph_context.get("imports", [])
    if imports:
        parts.append("**Imported Functions (used in changes):**")
        parts.append(f"*{len(imports)} imports found*")
        parts.append("")
        for imp in imports[:10]:  # Limit to 10 most relevant
            parts.append(f"### `{imp.get('name')}` ({imp.get('type')})")
            parts.append(f"**Imported in:** `{imp.get('from_file')}`")
            parts.append(f"**Source:** `{imp.get('path')}`")
            
            imp_source = imp.get("source") or ""
            if imp_source:
                if len(imp_source) > 5000:
                    imp_source = imp_source[:5000] + "\n# ... (truncated)"
                parts.append("```python")
                parts.append(imp_source)
                parts.append("```")
            elif imp.get("docstring"):
                parts.append(f"```\n{imp.get('docstring')}\n```")
            parts.append("")

    dependencies = graph_context.get("dependencies", [])
    if dependencies:
        parts.append("**Dependencies (what changed functions call):**")
        for dep in dependencies[:10]:
            parts.append(f"- **`{dep['symbol']}`** calls:")
            for d in dep.get("dependencies", [])[:5]:
                parts.append(f"  - `{d.get('name')}` in `{d.get('path')}`")
        parts.append("")

    callers = graph_context.get("callers", [])
    if callers:
        parts.append("**Downstream Callers:**")
        for entry in callers[:10]:
            parts.append(f"- **`{entry['symbol']}`** ({entry['symbol_type']}) is called by:")
            for c in entry.get("callers", [])[:5]:
                caller_info = f"  - `{c.get('name')}` in `{c.get('path')}`"
                if c.get("call_line"):
                    caller_info += f" (line {c.get('call_line')})"
                parts.append(caller_info)
        parts.append("")

    hierarchy = graph_context.get("class_hierarchy", [])
    if hierarchy:
        parts.append("**Class Hierarchy:**")
        for entry in hierarchy[:5]:
            parents = entry.get("parents", [])
            if parents:
                parent_names = " → ".join(p.get("parent_class", "?") for p in parents[:3])
                parts.append(f"- `{entry['class']}` inherits from: {parent_names}")
            children = entry.get("children", [])
            if children:
                child_names = ", ".join(c.get("child_class", "?") for c in children[:3])
                parts.append(f"  Inherited by: {child_names}")
        parts.append("")

    return "\n".join(parts) if parts else "No graph context available."
