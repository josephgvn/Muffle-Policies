#!/usr/bin/env python3
"""Checks a translated content file against en.json.

    python3 site/check_content.py de      (or several: de fr it)

Errors: missing or extra keys, different list lengths, changed guide slugs, em/en dashes.
Warnings: page titles over 65 characters, descriptions over 160.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EN = json.load(open(os.path.join(HERE, "content", "en.json")))


def walk(en, tr, path, errors):
    if isinstance(en, dict):
        if not isinstance(tr, dict):
            errors.append(f"{path}: expected an object"); return
        for key in en:
            if key not in tr:
                errors.append(f"{path}.{key}: missing")
            else:
                walk(en[key], tr[key], f"{path}.{key}", errors)
        for key in tr:
            if key not in en:
                errors.append(f"{path}.{key}: not in English")
    elif isinstance(en, list):
        if not isinstance(tr, list) or len(tr) != len(en):
            errors.append(f"{path}: expected a list of {len(en)}"); return
        for i, (a, b) in enumerate(zip(en, tr)):
            walk(a, b, f"{path}[{i}]", errors)
    elif isinstance(en, str):
        if not isinstance(tr, str) or not tr.strip():
            errors.append(f"{path}: empty")
        elif "—" in tr or "–" in tr:
            errors.append(f"{path}: contains an em or en dash")


def check(lang):
    data = json.load(open(os.path.join(HERE, "content", f"{lang}.json")))
    errors, warnings = [], []
    walk(EN, data, lang, errors)
    for i, (g_en, g) in enumerate(zip(EN.get("guides", []), data.get("guides", []))):
        if g.get("slug") != g_en["slug"]:
            errors.append(f"{lang}.guides[{i}].slug must stay '{g_en['slug']}'")
    titles = [("meta.home_title", data["meta"]["home_title"]), ("guides_index.title", data["guides_index"]["title"])]
    titles += [(f"guides[{i}].title", g["title"]) for i, g in enumerate(data.get("guides", []))]
    descriptions = [("meta.home_description", data["meta"]["home_description"]), ("guides_index.description", data["guides_index"]["description"])]
    descriptions += [(f"guides[{i}].description", g["description"]) for i, g in enumerate(data.get("guides", []))]
    warnings += [f"{p}: title is {len(t)} characters (aim for 65 or fewer)" for p, t in titles if len(t) > 65]
    warnings += [f"{p}: description is {len(t)} characters (aim for 160 or fewer)" for p, t in descriptions if len(t) > 160]
    return errors, warnings


if __name__ == "__main__":
    failed = False
    for lang in sys.argv[1:]:
        errors, warnings = check(lang)
        status = "OK" if not errors else "FAIL"
        print(f"{lang}: {status}, {len(errors)} errors, {len(warnings)} warnings")
        for line in errors + warnings:
            print("   " + line)
        failed = failed or bool(errors)
    sys.exit(1 if failed else 0)
