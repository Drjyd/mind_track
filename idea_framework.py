"""Ideas Framework - local-first idea capture and relationship organizer.

The module intentionally uses only the Python standard library so it can run on
Windows with a normal Python installation.  Every write rebuilds the complete
framework from the local history; unrelated ideas remain independent trunks.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


APP_DIR = Path(__file__).resolve().parent
DEFAULT_STORE = APP_DIR / "ideas.jsonl"
DEFAULT_MARKDOWN = APP_DIR / "framework.md"
DEFAULT_META = APP_DIR / "idea_framework_meta.json"
FIELD_ORDER = ("summary", "innovation", "mechanism", "scene", "validation", "risk")
FIELD_LABELS = {
    "summary": "一句话想法",
    "innovation": "创新点",
    "mechanism": "核心机制",
    "scene": "应用场景",
    "validation": "验证方法",
    "risk": "风险/限制",
}
SECTION_LABELS = {
    "summary": "目标/价值",
    "innovation": "创新点",
    "mechanism": "核心机制",
    "scene": "应用场景",
    "validation": "验证/指标",
    "risk": "待澄清要点与风险",
}
STOP_WORDS = {
    "可以", "通过", "根据", "进行", "实现", "一个", "这个", "用户", "系统", "功能", "方案",
    "我们", "以及", "能够", "需要", "使用", "对于", "相关", "提高", "建立", "提供", "支持",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[,，;；\n]", str(value or ""))
    result: list[str] = []
    for item in raw:
        tag = clean_text(item).lstrip("#")
        if tag and tag not in result:
            result.append(tag)
    return result


@dataclass
class Idea:
    id: str
    created_at: str
    title: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    innovation: str = ""
    mechanism: str = ""
    scene: str = ""
    validation: str = ""
    risk: str = ""
    updated_at: str = ""

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "Idea":
        # Compatibility with the earlier, simpler JSONL format.
        legacy_text = clean_text(record.get("content") or record.get("text") or record.get("idea"))
        title = clean_text(record.get("title")) or legacy_text[:26] or "未命名想法"
        created = clean_text(record.get("created_at") or record.get("timestamp")) or now_iso()
        return cls(
            id=clean_text(record.get("id")) or f"I{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}",
            created_at=created,
            title=title,
            tags=normalize_tags(record.get("tags")),
            summary=clean_text(record.get("summary")) or legacy_text,
            innovation=clean_text(record.get("innovation")),
            mechanism=clean_text(record.get("mechanism")),
            scene=clean_text(record.get("scene")),
            validation=clean_text(record.get("validation")),
            risk=clean_text(record.get("risk")),
            updated_at=clean_text(record.get("updated_at")),
        )

    def to_record(self) -> dict[str, Any]:
        result = asdict(self)
        return {key: value for key, value in result.items() if value not in ("", [], None)}

    def field_items(self) -> list[tuple[str, str]]:
        return [(key, clean_text(getattr(self, key))) for key in FIELD_ORDER if clean_text(getattr(self, key))]

    def searchable_text(self) -> str:
        return " ".join([self.title, *self.tags, *(text for _, text in self.field_items())])

    def preview(self, limit: int = 84) -> str:
        text = clean_text(self.summary or self.innovation or self.title)
        return text if len(text) <= limit else f"{text[:limit - 1]}…"


def new_idea(**values: Any) -> Idea:
    summary = clean_text(values.get("summary"))
    innovation = clean_text(values.get("innovation"))
    title = clean_text(values.get("title")) or (summary or innovation)[:26] or "未命名想法"
    stamp = now_iso()
    return Idea(
        id=f"I{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}",
        created_at=stamp,
        updated_at=stamp,
        title=title,
        tags=normalize_tags(values.get("tags")),
        summary=summary,
        innovation=innovation,
        mechanism=clean_text(values.get("mechanism")),
        scene=clean_text(values.get("scene")),
        validation=clean_text(values.get("validation")),
        risk=clean_text(values.get("risk")),
    )


def load_ideas(path: Path = DEFAULT_STORE) -> list[Idea]:
    if not path.exists():
        return []
    ideas: list[Idea] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = Idea.from_record(json.loads(line))
            except (json.JSONDecodeError, TypeError) as error:
                print(f"跳过第 {line_no} 行损坏记录：{error}", file=sys.stderr)
                continue
            ideas.append(item)
    return sorted(ideas, key=lambda item: item.created_at)


def save_ideas(ideas: Iterable[Idea], path: Path = DEFAULT_STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for idea in ideas:
            handle.write(json.dumps(idea.to_record(), ensure_ascii=False) + "\n")
    temporary.replace(path)


def load_meta(path: Path = DEFAULT_META) -> dict[str, Any]:
    defaults: dict[str, Any] = {"trunk_names": {}, "idea_assignments": {}, "pinned_ids": []}
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    for key, default in defaults.items():
        value = raw.get(key, default) if isinstance(raw, dict) else default
        if isinstance(default, dict) and not isinstance(value, dict):
            value = {}
        if isinstance(default, list) and not isinstance(value, list):
            value = []
        defaults[key] = value
    return defaults


def save_meta(meta: dict[str, Any], path: Path = DEFAULT_META) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def tokens(text: str) -> set[str]:
    plain = clean_text(text).lower()
    words = set(re.findall(r"[a-z0-9][a-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}", plain))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", plain))
    for size in (2, 3):
        words.update(chinese[index:index + size] for index in range(max(0, len(chinese) - size + 1)))
    return {word for word in words if word not in STOP_WORDS and len(word) >= 2}


def relevance(left: Idea, right: Idea) -> float:
    left_tokens, right_tokens = tokens(left.searchable_text()), tokens(right.searchable_text())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    title_overlap = len(tokens(left.title) & tokens(right.title)) / max(1, len(tokens(left.title) | tokens(right.title)))
    tag_overlap = len(set(left.tags) & set(right.tags)) / max(1, len(set(left.tags) | set(right.tags)))
    return min(1.0, overlap * 0.62 + title_overlap * 0.23 + tag_overlap * 0.30)


def automatic_components(ideas: list[Idea], threshold: float) -> list[list[Idea]]:
    if not ideas:
        return []
    parents = list(range(len(ideas)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(ideas)):
        for right in range(left + 1, len(ideas)):
            if relevance(ideas[left], ideas[right]) >= threshold:
                union(left, right)
    grouped: dict[int, list[Idea]] = defaultdict(list)
    for index, idea in enumerate(ideas):
        grouped[root(index)].append(idea)
    return sorted(grouped.values(), key=lambda group: max(item.created_at for item in group), reverse=True)


def cluster_ideas_with_assignments(
    ideas: list[Idea], threshold: float, assignments: dict[str, str] | None = None
) -> list[list[Idea]]:
    """Build automatic clusters, respecting user-fixed trunks where present."""
    assignments = {str(key): str(value) for key, value in (assignments or {}).items()}
    by_id = {idea.id: idea for idea in ideas}
    fixed_targets = {target for target in assignments.values() if target in by_id}
    components: list[list[Idea]] = []
    fixed_ids: set[str] = set()
    for target in fixed_targets:
        member_ids = {item_id for item_id, assigned_target in assignments.items() if assigned_target == target and item_id in by_id}
        member_ids.add(target)
        fixed = [idea for idea in ideas if idea.id in member_ids]
        if fixed:
            components.append(fixed)
            fixed_ids.update(member_ids)
    remaining = [idea for idea in ideas if idea.id not in fixed_ids]
    components.extend(automatic_components(remaining, threshold))
    return sorted(components, key=lambda group: max(item.created_at for item in group), reverse=True)


def component_key(component: list[Idea]) -> str:
    return min(component, key=lambda item: item.created_at).id


def topic_name(component: list[Idea], names: dict[str, str] | None = None) -> str:
    key = component_key(component)
    custom = clean_text((names or {}).get(key))
    if custom:
        return custom
    tag_counts = Counter(tag for item in component for tag in item.tags)
    if tag_counts:
        return tag_counts.most_common(1)[0][0]
    return min(component, key=lambda item: item.created_at).title


def component_keywords(component: list[Idea], count: int = 8) -> list[str]:
    frequencies = Counter()
    for idea in component:
        frequencies.update(tokens(idea.searchable_text()))
        frequencies.update(idea.tags)
    return [term for term, _ in frequencies.most_common(count)]


def matching_ideas(ideas: list[Idea], query: str, components: list[list[Idea]] | None = None) -> list[tuple[Idea, float]]:
    query_tokens = tokens(query)
    if not query_tokens:
        return [(idea, 0.0) for idea in reversed(ideas)]
    result: list[tuple[Idea, float]] = []
    for idea in ideas:
        idea_tokens = tokens(idea.searchable_text())
        score = len(query_tokens & idea_tokens) / max(1, len(query_tokens))
        if clean_text(query).lower() in idea.searchable_text().lower():
            score += 0.35
        if score > 0:
            result.append((idea, min(score, 1.0)))
    return sorted(result, key=lambda pair: (pair[1], pair[0].created_at), reverse=True)


def topic_for_idea(idea_id: str, components: list[list[Idea]], names: dict[str, str] | None = None) -> str:
    for component in components:
        if any(item.id == idea_id for item in component):
            return topic_name(component, names)
    return "未归类"


def framework_markdown(
    ideas: list[Idea],
    threshold: float = 0.18,
    name_overrides: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> str:
    components = cluster_ideas_with_assignments(ideas, threshold, assignments)
    lines = [
        "# 想法与创新点逻辑框架",
        "",
        f"- 生成时间：{now_iso()}",
        f"- 历史想法数量：{len(ideas)}",
        f"- 关联阈值：{threshold:.2f}",
        "- 生成规则：每次新增后重新读取全部历史记录，重新检索相关内容，再重建逻辑树。",
        "",
        "## 总览",
        "",
    ]
    if not components:
        lines.append("- 暂无记录。请通过界面或命令行写入第一条想法。")
        return "\n".join(lines) + "\n"
    for index, component in enumerate(components, start=1):
        kind = "关联主题" if len(component) > 1 else "独立树干"
        lines.append(f"- 树干 {index}：{topic_name(component, name_overrides)}（{kind}，{len(component)} 条）")
    for index, component in enumerate(components, start=1):
        title = topic_name(component, name_overrides)
        kind = "关联主题" if len(component) > 1 else "独立树干"
        lines.extend(["", f"## 树干 {index}：{title}", "", f"- 类型：{kind}", f"- 关键词：{'、'.join(component_keywords(component)) or '暂无'}"])
        for field_name in FIELD_ORDER:
            entries = []
            seen: set[str] = set()
            for idea in component:
                value = clean_text(getattr(idea, field_name))
                if value and value not in seen:
                    entries.append((value, idea.id))
                    seen.add(value)
            if entries:
                lines.extend(["", f"### {SECTION_LABELS[field_name]}", ""])
                lines.extend(f"- {value}（来源：{idea_id}）" for value, idea_id in entries)
        lines.extend(["", "### 来源索引", ""])
        for idea in sorted(component, key=lambda item: item.created_at):
            tag_text = f"｜标签：{', '.join(idea.tags)}" if idea.tags else ""
            lines.append(f"- {idea.id}｜{idea.created_at}｜{idea.title}{tag_text}")
    return "\n".join(lines) + "\n"


def write_framework(
    ideas: list[Idea], path: Path = DEFAULT_MARKDOWN, threshold: float = 0.18,
    names: dict[str, str] | None = None, assignments: dict[str, str] | None = None,
) -> str:
    content = framework_markdown(ideas, threshold, names, assignments)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return content


def mermaid_source(
    ideas: list[Idea], threshold: float, names: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> str:
    def label(value: str) -> str:
        return re.sub(r'["\n\r]', " ", value)[:44]
    lines = ["mindmap", "  root((想法逻辑框架))"]
    for index, component in enumerate(cluster_ideas_with_assignments(ideas, threshold, assignments), 1):
        trunk = f"T{index}"
        lines.append(f"    {trunk}({label(topic_name(component, names))})")
        for idea_index, idea in enumerate(component, 1):
            node = f"{trunk}I{idea_index}"
            lines.append(f"      {node}[{label(idea.title)}]")
            for field, value in idea.field_items():
                if field == "summary":
                    continue
                lines.append(f"        {node}{field}[{label(FIELD_LABELS[field] + '：' + value)}]")
    return "\n".join(lines) + "\n"


def visual_payload(
    ideas: list[Idea], threshold: float, names: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    payload = []
    for component in cluster_ideas_with_assignments(ideas, threshold, assignments):
        payload.append({
            "key": component_key(component),
            "name": topic_name(component, names),
            "keywords": component_keywords(component, 5),
            "ideas": [{
                "id": item.id, "title": item.title, "preview": item.preview(54),
                "tags": item.tags, "fields": dict(item.field_items()),
            } for item in component],
        })
    return payload


def html_visual_export(
    ideas: list[Idea], threshold: float, names: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> str:
    data = json.dumps(visual_payload(ideas, threshold, names, assignments), ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>想法逻辑框架</title>
<style>body{{margin:0;background:#f5f7fb;color:#172033;font:15px 'Microsoft YaHei',sans-serif}}header{{padding:22px 5%;background:#172033;color:white}}h1{{margin:0;font-size:24px}}#map{{padding:24px 5%;display:grid;gap:18px}}.topic{{background:#fff;border-left:5px solid #246bce;padding:16px;border-radius:8px;box-shadow:0 2px 8px #17203312}}.idea{{margin:12px 0 0 18px;padding:12px;border:1px solid #d8e1f0;border-radius:6px}}.meta{{color:#58708f;font-size:13px}}.fields{{margin:8px 0 0;padding-left:18px}}li{{margin:4px 0}}</style></head>
<body><header><h1>想法与创新点逻辑框架</h1><div>共 {len(ideas)} 条想法，阈值 {threshold:.2f}</div></header><main id=\"map\"></main>
<script>const data={data}; const esc=s=>String(s).replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;'}}[c]));
document.getElementById('map').innerHTML=data.map((t,i)=>`<section class=\"topic\"><h2>${{i+1}}. ${{esc(t.name)}}</h2><div class=\"meta\">${{esc(t.keywords.join('、'))}} · ${{t.ideas.length}} 条想法</div>${{t.ideas.map(x=>`<article class=\"idea\"><strong>${{esc(x.title)}}</strong><div>${{esc(x.preview)}}</div><ul class=\"fields\">${{Object.entries(x.fields).filter(([k])=>k!=='summary').map(([k,v])=>`<li>${{esc(k)}}：${{esc(v)}}</li>`).join('')}}</ul></article>`).join('')}}</section>`).join('');</script></body></html>"""


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except OSError:
                pass


def command_add(args: argparse.Namespace) -> int:
    ideas = load_ideas(args.store)
    idea = new_idea(title=args.title, tags=args.tags, summary=args.summary, innovation=args.innovation,
                    mechanism=args.mechanism, scene=args.scene, validation=args.validation, risk=args.risk)
    if not any(value for _, value in idea.field_items()):
        print("至少需要填写一项想法内容。", file=sys.stderr)
        return 2
    ideas.append(idea)
    save_ideas(ideas, args.store)
    meta = load_meta(args.meta)
    write_framework(ideas, args.output, args.threshold, meta["trunk_names"], meta["idea_assignments"])
    print(f"已写入：{idea.id}｜{idea.title}")
    print(f"框架已重建：{args.output}")
    return 0


def command_list(args: argparse.Namespace) -> int:
    ideas = load_ideas(args.store)
    for idea in reversed(ideas):
        print(f"{idea.id}\t{idea.created_at}\t{idea.title}\t{', '.join(idea.tags)}")
    print(f"共 {len(ideas)} 条")
    return 0


def command_search(args: argparse.Namespace) -> int:
    ideas = load_ideas(args.store)
    for idea, score in matching_ideas(ideas, args.query):
        print(f"{score:.0%}\t{idea.id}\t{idea.title}\t{idea.preview(100)}")
    return 0


def command_framework(args: argparse.Namespace) -> int:
    ideas, meta = load_ideas(args.store), load_meta(args.meta)
    write_framework(ideas, args.output, args.threshold, meta["trunk_names"], meta["idea_assignments"])
    print(f"已生成：{args.output}")
    return 0


def command_ui(args: argparse.Namespace) -> int:
    from idea_framework_ui import main as ui_main
    return ui_main(["--store", str(args.store), "--output", str(args.output), "--meta", str(args.meta)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="想法与创新点逻辑框架工具")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help="想法 JSONL 文件")
    parser.add_argument("--output", type=Path, default=DEFAULT_MARKDOWN, help="Markdown 框架文件")
    parser.add_argument("--meta", type=Path, default=DEFAULT_META, help="主题设置文件")
    parser.add_argument("--threshold", type=float, default=0.18, help="关联阈值，0-1")
    subparsers = parser.add_subparsers(dest="command")
    add = subparsers.add_parser("add", help="写入一条想法并重建框架")
    add.add_argument("--title", default="")
    add.add_argument("--tags", default="")
    for field in FIELD_ORDER:
        add.add_argument(f"--{field}", default="", help=FIELD_LABELS[field])
    add.set_defaults(handler=command_add)
    listing = subparsers.add_parser("list", help="列出历史想法")
    listing.set_defaults(handler=command_list)
    search = subparsers.add_parser("search", help="检索历史想法")
    search.add_argument("query")
    search.set_defaults(handler=command_search)
    framework = subparsers.add_parser("framework", help="重建 Markdown 框架")
    framework.set_defaults(handler=command_framework)
    ui = subparsers.add_parser("ui", help="启动图形界面")
    ui.set_defaults(handler=command_ui)
    return parser


def interactive_add(parser: argparse.ArgumentParser) -> int:
    print("想法与创新点逻辑框架｜直接回车可跳过字段，输入 :ui 打开界面。")
    summary = input("一句话想法：").strip()
    if summary == ":ui":
        return command_ui(parser.parse_args(["ui"]))
    innovation = input("创新点：").strip()
    tags = input("标签（逗号分隔）：").strip()
    return command_add(parser.parse_args(["add", "--summary", summary, "--innovation", innovation, "--tags", tags]))


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        return interactive_add(parser)
    if not 0 <= args.threshold <= 1:
        parser.error("关联阈值必须在 0 到 1 之间")
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
