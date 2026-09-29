#!/usr/bin/env python3
"""Translates only what changed in site/content/en.json since the last commit, into every language.

    GEMINI_API_KEY=... python3 site/translate_changes.py [lang ...]

Existing translations stay as they are; new and edited English strings are sent to Gemini with the same
instructions as site/translate.py, and the results are written into each language file.
"""
import concurrent.futures
import copy
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import translate  # noqa: E402  (reads GEMINI_API_KEY)

SKIP = re.compile(r"\.slug$|^works_with\.apps|^stats\.items\[\d+\]\.value$")


def flatten(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten(item, f"{path}[{index}]")
    else:
        yield path, value


def parse(path):
    return [int(part) if part.isdigit() else part for part in re.findall(r"[^.\[\]]+", path)]


def put(root, path, value):
    parts = parse(path)
    node = root
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value


def fill_missing(target, english):
    """Gives `target` every key and list item `english` has, with the English value, keeping what exists."""
    if isinstance(english, dict):
        for key, item in english.items():
            if key not in target:
                target[key] = copy.deepcopy(item)
            else:
                fill_missing(target[key], item)
    elif isinstance(english, list):
        for index, item in enumerate(english):
            if index >= len(target):
                target.append(copy.deepcopy(item))
            else:
                fill_missing(target[index], item)


def changed_paths():
    old = json.loads(subprocess.run(["git", "show", "HEAD:site/content/en.json"], cwd=os.path.dirname(HERE),
                                    capture_output=True, text=True, check=True).stdout)
    new = json.load(open(os.path.join(HERE, "content", "en.json")))
    before = dict(flatten(old))
    return new, {path: value for path, value in flatten(new) if before.get(path) != value and not SKIP.search(path)}


def run(lang, english, changes):
    path = os.path.join(HERE, "content", f"{lang}.json")
    data = json.load(open(path))
    fill_missing(data, english)
    system = translate.instructions(lang) + "\n\nThe JSON keys are locations on the website; translate only the values."
    result = None
    for _ in range(4):
        try:
            candidate, usage = translate.call(system, changes)
        except (json.JSONDecodeError, KeyError, IndexError) as error:
            print(f"  {lang}: bad response ({error}), retrying", flush=True)
            continue
        if isinstance(candidate, dict) and candidate.keys() == changes.keys() and all(isinstance(v, str) and v.strip() for v in candidate.values()):
            result = translate.clean(candidate)
            break
        print(f"  {lang}: keys didn't match, retrying", flush=True)
    if result is None:
        raise RuntimeError(f"{lang}: no matching translation")
    for location, text in result.items():
        put(data, location, text)
    ordered = {key: data[key] for key in english}
    with open(path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
    return usage.get("totalTokenCount", 0)


def main():
    english, changes = changed_paths()
    print(f"{len(changes)} changed string(s)")
    if not changes:
        return
    languages = sys.argv[1:] or [code for code in translate.LANGUAGES]
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "8"))) as pool:
        futures = {pool.submit(run, lang, english, changes): lang for lang in languages}
        for future in concurrent.futures.as_completed(futures):
            lang = futures[future]
            try:
                tokens = future.result()
                total += tokens
                print(f"{lang}: done ({tokens} tokens)", flush=True)
            except Exception as error:
                print(f"{lang}: FAILED {error}", flush=True)
    print(f"total tokens: {total}")


if __name__ == "__main__":
    main()
