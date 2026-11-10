#!/usr/bin/env python3
"""Publishes the baked circuit, if it changed.

The game's site is built by GitHub Actions, but its circuit is not: baking needs the car's model,
which Blender makes. So the circuit is baked on a PC, uploaded as a release of this repository,
and recorded in scene.txt as the release's tag and the file's SHA-256. Pushing that change makes
the Pages workflow download the file, check it, and serve it beside the page.

    python scripts/publish-circuit.py [--bake] [--check]

--bake bakes the circuit first (make the car and the track file before that: see the README).
--check only says whether there is anything to publish.
Needs the GitHub CLI, signed in with permission to create releases in the repository.
"""
import datetime
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "SamG-Coder/solstice-racing"
FILE = "coast.solstice"
BAKE = ["cargo", "run", "--release", "-p", "bake", "--", "--scene", "scenes/coast.txt",
        "--output", f"assets/{FILE}"]
HEADER = (
    "# The circuit this site serves: its file name, the release that holds it (OWNER/REPO@TAG,\n"
    "# or a tag of this repository) and its SHA-256. Written by scripts/publish-circuit.py;\n"
    "# pushing a change deploys the new circuit.\n"
)


def run(command, **kwargs):
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def output(command):
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def recorded():
    """What scene.txt says is published: (file, release, SHA-256), or None."""
    try:
        with open(os.path.join(ROOT, "scene.txt"), encoding="utf-8") as f:
            for line in f:
                words = line.split("#")[0].split()
                if len(words) == 3:
                    return tuple(words)
    except FileNotFoundError:
        pass
    return None


def main():
    args = sys.argv[1:]
    if any(a not in ("--bake", "--check") for a in args):
        sys.exit(__doc__)
    if "--bake" in args:
        os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
        run(BAKE)
    path = os.path.join(ROOT, "assets", FILE)
    if not os.path.exists(path):
        sys.exit(f"assets/{FILE} is not baked: run this with --bake")
    digest = sha256(path)
    before = recorded()
    if before and before[2] == digest:
        print(f"unchanged, in {before[1]}")
        return
    megabytes = os.path.getsize(path) / 1e6
    print(f"changed: {megabytes:.1f} MB, SHA-256 {digest}")
    if "--check" in args:
        return

    commit = output(["git", "rev-parse", "--short", "HEAD"])
    baking = ["git", "status", "--porcelain", "--", "apps", "crates", "scenes", "Cargo.lock"]
    dirty = " (with uncommitted changes)" if output(baking) else ""
    tag = "circuit-" + datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    notes = (f"{FILE}, baked from {REPO}@{commit}{dirty}.\n\n"
             f"{megabytes:.1f} MB, SHA-256 `{digest}`.")
    run(["gh", "release", "create", tag, "--repo", REPO, "--title", f"Circuit {tag[8:]}",
         "--notes", notes, path])
    with open(os.path.join(ROOT, "scene.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER + f"{FILE} {tag} {digest}\n")
    print(f"published as {REPO}@{tag}. To deploy it, commit scene.txt and push:")
    print(f'  git commit -m "Serve the circuit from {tag}" scene.txt && git push')


if __name__ == "__main__":
    main()
