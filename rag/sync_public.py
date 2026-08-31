"""Download a bounded ROS 2 docs slice (CC-BY 4.0) into data/corpus/public/."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from rag.settings import S

REF = "humble"
BASE = f"https://raw.githubusercontent.com/ros2/ros2_documentation/{REF}"
BLOB = f"https://github.com/ros2/ros2_documentation/blob/{REF}"

# Skip Topics/Services/Nodes/Launch/QoS/TF/Domain/Executors/Security — those
# collide with internal SOP pages used by the eval set.
PAGES: list[tuple[str, str, str]] = [
    ("ros2-doc-actions", "Actions", "source/Concepts/Basic/About-Actions.rst"),
    ("ros2-doc-parameters", "Parameters", "source/Concepts/Basic/About-Parameters.rst"),
    ("ros2-doc-interfaces", "Interfaces", "source/Concepts/Basic/About-Interfaces.rst"),
    ("ros2-doc-client-libraries", "Client libraries", "source/Concepts/Basic/About-Client-Libraries.rst"),
    ("ros2-doc-cli", "Command line tools", "source/Concepts/Basic/About-Command-Line-Tools.rst"),
    ("ros2-doc-discovery", "Discovery", "source/Concepts/Basic/About-Discovery.rst"),
    ("ros2-doc-composition", "Composition", "source/Concepts/Intermediate/About-Composition.rst"),
    ("ros2-doc-cross-compile", "Cross compilation", "source/Concepts/Intermediate/About-Cross-Compilation.rst"),
    ("ros2-doc-rmw", "Middleware vendors", "source/Concepts/Intermediate/About-Different-Middleware-Vendors.rst"),
    ("ros2-doc-logging", "Logging", "source/Concepts/Intermediate/About-Logging.rst"),
    ("ros2-doc-rqt", "RQt", "source/Concepts/Intermediate/About-RQt.rst"),
    ("ros2-doc-topic-stats", "Topic statistics", "source/Concepts/Intermediate/About-Topic-Statistics.rst"),
]


def rst_to_markdown(rst: str) -> str:
    rst = rst.replace("\r\n", "\n")
    rst = re.sub(r"\.\. toctree::.*?(?=\n\S|\Z)", "", rst, flags=re.S)
    rst = re.sub(r"\.\. image::[^\n]*(?:\n[ \t]+[^\n]*)*", "", rst)
    rst = re.sub(r"\.\. figure::[^\n]*(?:\n[ \t]+[^\n]*)*", "", rst)
    rst = re.sub(r":(?:ref|doc|term):`([^`]+)`", r"\1", rst)
    rst = re.sub(r"``([^`]+)``", r"`\1`", rst)

    def fence(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        body = re.sub(r"^   ", "", m.group(2), flags=re.M).rstrip()
        return f"\n```{lang}\n{body}\n```\n"

    rst = re.sub(
        r"\.\. code-block::[ \t]*([^\n]*)\n\n((?:[ \t].*\n)+)",
        fence,
        rst,
    )
    rst = re.sub(r"^\.\. [a-z-]+::.*$", "", rst, flags=re.M)
    lines = rst.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and lines[i] and set(lines[i + 1]) <= set("=-~") and len(lines[i + 1]) >= 3:
            bar = lines[i + 1][0]
            title = line.strip()
            if bar == "=":
                out.append(f"# {title}")
            elif bar == "-":
                out.append(f"## {title}")
            else:
                out.append(f"### {title}")
            i += 2
            continue
        if line.startswith("   ") and (not out or not out[-1].startswith("```")):
            out.append(line[3:])
        else:
            out.append(line)
        i += 1
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def wrap(doc_id: str, title: str, rel: str, body: str) -> str:
    url = f"{BLOB}/{rel}"
    return (
        "---\n"
        f"doc_id: {doc_id}\n"
        f'title: "ROS 2 docs · {title}"\n'
        "dept: engineering\n"
        "acl: [engineer, ops, intern]\n"
        "classification: public\n"
        "version: humble\n"
        "expires: null\n"
        "license: CC-BY-4.0\n"
        f"upstream: {url}\n"
        "---\n\n"
        f"> 摘自 ROS 2 Documentation（Humble），[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原文：<{url}>\n\n"
        f"{body}\n"
    )


def sync(dest: Path | None = None) -> list[Path]:
    dest = dest or (S.corpus_dir / "public")
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc_id, title, rel in PAGES:
        url = f"{BASE}/{rel}"
        path = dest / f"{doc_id}.md"
        if path.exists() and path.stat().st_size > 200:
            print(f"skip {path.name}")
            written.append(path)
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "WikiRAG-sync/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            rst = r.read().decode("utf-8")
        path = dest / f"{doc_id}.md"
        path.write_text(wrap(doc_id, title, rel, rst_to_markdown(rst)), encoding="utf-8")
        written.append(path)
        print(f"wrote {path.name}  from {rel}")
    return written


if __name__ == "__main__":
    sync()
