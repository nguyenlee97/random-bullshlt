"""
Patch freeform.py: add setup sub-phase to workspace snapshot
so LLM knows which of the 3 Setup sub-steps the user is on.
"""
import pathlib, ast

fp = pathlib.Path(__file__).parent / "freeform.py"
text = fp.read_text(encoding="utf-8")

OLD = (
    '    # Setup\n'
    '    setup = workspace.get("setup", {})\n'
    '    selected_zone_ids = setup.get("selectedZoneIds", [])\n'
    '    if selected_zone_ids:\n'
    '        import json as _json2\n'
    '        lines.append("--- Setup ---")\n'
    '        lines.append(f"Zones \u0111\u00e3 ch\u1ecdn: {len(selected_zone_ids)}")\n'
    '        # Provide full list so LLM can modify without hallucinating zone IDs\n'
    '        lines.append("CURRENT_SELECTED_ZONES (d\u00f9ng l\u00e0m base khi g\u1ecdi update_workspace field=setup):")\n'
    '        lines.append(_json2.dumps(selected_zone_ids, ensure_ascii=False))\n'
    '        lines.append("")\n'
)

NEW = (
    '    # Setup\n'
    '    setup = workspace.get("setup", {})\n'
    '    selected_zone_ids = setup.get("selectedZoneIds", [])\n'
    '    setup_phase = setup.get("phase", "zones")\n'
    '    _PHASE_LABELS = {\n'
    '        "zones":  "1/3 \u2014 Ch\u1ecdn Ad Zones (user \u0111ang ch\u1ecdn zones)",\n'
    '        "assign": "2/3 \u2014 G\u1eafn Creative (user \u0111ang g\u00e1n creative v\u00e0o zones)",\n'
    '        "confirm":"3/3 \u2014 X\u00e1c nh\u1eadn & T\u1ea1o chi\u1ebfn d\u1ecbch",\n'
    '    }\n'
    '    if selected_zone_ids or setup_phase != "zones":\n'
    '        import json as _json2\n'
    '        lines.append("--- Setup Camp ---")\n'
    '        lines.append(f"Sub-step hi\u1ec7n t\u1ea1i: {_PHASE_LABELS.get(setup_phase, setup_phase)}")\n'
    '        lines.append(f"Zones \u0111\u00e3 ch\u1ecdn: {len(selected_zone_ids)}")\n'
    '        # Provide full list so LLM can modify without hallucinating zone IDs\n'
    '        lines.append("CURRENT_SELECTED_ZONES (d\u00f9ng l\u00e0m base khi g\u1ecdi update_workspace field=setup):")\n'
    '        lines.append(_json2.dumps(selected_zone_ids, ensure_ascii=False))\n'
    '        lines.append("")\n'
)

if OLD in text:
    text = text.replace(OLD, NEW, 1)
    print("Patched setup snapshot with sub-phase info")
else:
    print("ERROR: anchor not found")
    import sys; sys.exit(1)

fp.write_text(text, encoding="utf-8")

try:
    ast.parse(text)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax ERROR line {e.lineno}: {e.msg}")
