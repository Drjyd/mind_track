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
DEFAULT_OBSIDIAN = APP_DIR / "obsidian_export"
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

KNOWLEDGE_TYPES = ("事实", "假设", "推论", "经验", "未知问题")
THINKING_MODES = ("第一性原理", "系统性思维", "过程思维", "反向思维", "默会知识", "高杠杆思考")
RELATION_TYPES = ("包含", "因果", "依赖", "对比", "时序", "反馈", "证据", "风险", "行动")
TOOL_LAYERS = ("OneNote原始捕捉层", "Obsidian知识沉淀层", "思维导图表达层")
CONFIDENCE_LEVELS = ("高", "中", "低", "待验证")
REPORT_SECTIONS = (
    (1, "一句话核心结论"),
    (2, "主题的系统边界"),
    (3, "第一性原理拆解"),
    (4, "可检查的分析步骤"),
    (5, "失败模式与预警信号"),
    (6, "专家默会知识"),
    (7, "第一序、第二序和第三序效应"),
    (8, "OneNote原始记录清单"),
    (9, "Obsidian永久笔记清单"),
    (10, "Obsidian属性字段建议"),
    (11, "推荐建立的双向链接"),
    (12, "缩进式思维导图"),
    (13, "Mermaid思维导图代码"),
    (14, "三个最高杠杆的行动"),
    (15, "一个最小可执行的下一步"),
)


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
    knowledge_type: str = "未知问题"
    thinking_mode: str = "过程思维"
    relation_type: str = "包含"
    tool_layer: str = "OneNote原始捕捉层"
    source: str = ""
    evidence: str = ""
    confidence: str = "待验证"
    next_action: str = ""
    links: list[str] = field(default_factory=list)
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
            knowledge_type=clean_text(record.get("knowledge_type")) or "未知问题",
            thinking_mode=clean_text(record.get("thinking_mode")) or "过程思维",
            relation_type=clean_text(record.get("relation_type")) or "包含",
            tool_layer=clean_text(record.get("tool_layer")) or "OneNote原始捕捉层",
            source=clean_text(record.get("source")),
            evidence=clean_text(record.get("evidence")),
            confidence=clean_text(record.get("confidence")) or "待验证",
            next_action=clean_text(record.get("next_action")),
            links=normalize_tags(record.get("links")),
            updated_at=clean_text(record.get("updated_at")),
        )

    def to_record(self) -> dict[str, Any]:
        result = asdict(self)
        return {key: value for key, value in result.items() if value not in ("", [], None)}

    def field_items(self) -> list[tuple[str, str]]:
        return [(key, clean_text(getattr(self, key))) for key in FIELD_ORDER if clean_text(getattr(self, key))]

    def searchable_text(self) -> str:
        return " ".join([
            self.title, *self.tags, self.knowledge_type, self.thinking_mode,
            self.relation_type, self.tool_layer, self.source, self.evidence,
            self.next_action, *self.links, *(text for _, text in self.field_items()),
        ])

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
        knowledge_type=clean_text(values.get("knowledge_type")) or "未知问题",
        thinking_mode=clean_text(values.get("thinking_mode")) or "过程思维",
        relation_type=clean_text(values.get("relation_type")) or "包含",
        tool_layer=clean_text(values.get("tool_layer")) or "OneNote原始捕捉层",
        source=clean_text(values.get("source")),
        evidence=clean_text(values.get("evidence")),
        confidence=clean_text(values.get("confidence")) or "待验证",
        next_action=clean_text(values.get("next_action")),
        links=normalize_tags(values.get("links")),
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
    defaults: dict[str, Any] = {
        "trunk_names": {},
        "idea_assignments": {},
        "pinned_ids": [],
        "capture_draft": {},
        "excluded_report_sections": [],
        "report_exclusions": [],
    }
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
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


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


def _topic_title(ideas: list[Idea], names: dict[str, str] | None = None) -> str:
    if not ideas:
        return "待定义主题"
    components = automatic_components(ideas, 0.18)
    if len(components) == 1:
        return topic_name(components[0], names)
    pinned_name = clean_text(next(iter((names or {}).values()), ""))
    return pinned_name or ideas[-1].title


def _idea_text(idea: Idea) -> str:
    return clean_text(idea.summary or idea.mechanism or idea.innovation or idea.title)


def _marked(idea: Idea, text: str | None = None) -> str:
    content = clean_text(text or _idea_text(idea)) or "待补充"
    verification = "【待验证】" if idea.knowledge_type in {"假设", "推论", "未知问题"} or idea.confidence in {"低", "待验证"} else ""
    source = f"；证据：{idea.evidence or idea.source}" if idea.evidence or idea.source else ""
    return f"[{idea.relation_type}] {content}{verification}{source}（{idea.id}）"


def _items_or_pending(items: list[str], pending: str = "待验证：尚无记录。") -> list[str]:
    return items or [pending]


def _append_bullets(lines: list[str], items: list[str]) -> None:
    lines.extend(f"- {item}" for item in items)


def _indent_map(ideas: list[Idea], topic: str) -> list[str]:
    """Create a relationship-first map with no more than five levels."""
    branches: list[tuple[str, tuple[str, ...]]] = [
        ("第一性原理", ("第一性原理",)),
        ("系统与反馈", ("系统性思维",)),
        ("可复核过程", ("过程思维",)),
        ("失败与专家判断", ("反向思维", "默会知识")),
        ("杠杆与效应", ("高杠杆思考",)),
    ]
    lines = [topic]
    used: set[str] = set()
    for branch, modes in branches:
        selected = [idea for idea in ideas if idea.thinking_mode in modes][:7]
        lines.append(f"  - [包含] {branch}")
        if not selected:
            lines.append("    - [行动] 待补充并验证")
        for idea in selected:
            used.add(idea.id)
            lines.append(f"    - [{idea.relation_type}] {idea.title}{'【待验证】' if idea.confidence == '待验证' else ''}")
            if idea.evidence or idea.source:
                lines.append(f"      - [证据] {clean_text(idea.evidence or idea.source)[:90]}")
            if idea.next_action:
                lines.append(f"      - [行动] {idea.next_action[:90]}")
    lines.append("  - [时序] 工具工作流")
    for layer in TOOL_LAYERS:
        count = sum(1 for idea in ideas if idea.tool_layer == layer)
        lines.append(f"    - [包含] {layer}（{count}）")
    lines.append("  - [行动] 下一步")
    actions = [idea.next_action for idea in ideas if idea.next_action][:3]
    for action in _items_or_pending(actions, "定义一个可验证的小步骤"):
        lines.append(f"    - [行动] {action}")
    return lines


def filter_report_sections(
    markdown: str,
    excluded_sections: Iterable[int | str] | None = None,
    excluded_lines: Iterable[str] | None = None,
) -> str:
    """Remove selected report sections or exact content lines from generated output."""
    excluded: set[int] = set()
    for value in excluded_sections or ():
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= len(REPORT_SECTIONS):
            excluded.add(number)
    line_exclusions = {clean_text(value) for value in (excluded_lines or ()) if clean_text(value)}
    if not excluded and not line_exclusions:
        return markdown
    output: list[str] = []
    skipping = False
    for line in markdown.splitlines(keepends=True):
        heading = re.match(r"^##\s+(\d+)\.\s+", line)
        if heading:
            skipping = int(heading.group(1)) in excluded
        if not skipping and clean_text(line) not in line_exclusions:
            output.append(line)
    return "".join(output).rstrip() + "\n"


def framework_markdown(
    ideas: list[Idea],
    threshold: float = 0.18,
    name_overrides: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
    excluded_sections: Iterable[int | str] | None = None,
    excluded_lines: Iterable[str] | None = None,
) -> str:
    components = cluster_ideas_with_assignments(ideas, threshold, assignments)
    topic = _topic_title(ideas, name_overrides)
    lines = [
        f"# {topic}｜知识处理方案",
        "",
        f"- 生成时间：{now_iso()}",
        f"- 知识条目数量：{len(ideas)}",
        f"- 关联阈值：{threshold:.2f}",
        "- 标注约定：假设、推论、未知问题及低置信度内容统一标记为“待验证”。",
        "",
        "## 1. 一句话核心结论",
        "",
    ]
    conclusion = next((_idea_text(item) for item in reversed(ideas) if item.summary), "待验证：先定义主题、目标与可观察结果。")
    lines.append(conclusion)

    lines.extend(["", "## 2. 主题的系统边界", ""])
    _append_bullets(lines, [
        f"系统目标：把“{topic}”的临时信息转化为可追溯、可复用、可验证的知识。",
        "系统边界：从原始捕捉开始，到形成永久笔记、关系图和下一步决策结束；真实实验执行与外部平台同步不在自动化边界内。",
        f"输入：{len(ideas)} 条记录、来源、证据和人工判断；输出：15 段分析报告、Obsidian 笔记、OneNote 清单和 Mermaid 导图。",
        "核心模块与依赖：第一性原理定义对象 → 系统思维连接变量 → 过程思维形成证据链 → 反向思维寻找反例 → 默会知识补足判断规则 → 高杠杆思考确定行动优先级。",
        "正反馈：高质量永久笔记增加可链接证据，更多可靠链接又提高后续分析的复用效率。负反馈：反例、失败记录和强制检查点会降低错误结论的置信度。",
        "时间延迟：原始记录不会立即成为永久知识，必须经过复盘、验证与关系确认。",
        "限制条件：本工具只组织用户提供的信息，不会把未提供的领域知识伪装成事实。",
        "风险传播：一个无来源的关键假设若被误标为事实，会沿因果、依赖和反馈关系传播到实验设计与技术决策。",
        "高杠杆点：知识状态、证据/来源、判断标准和下一步动作四项完整度。",
    ])

    lines.extend(["", "## 3. 第一性原理拆解", "", "这些主干分别承担‘确认现实、提出解释、形成判断、复用经验、暴露缺口’五种不同决策功能，因此应成为导图主干，而不是沿用普通资料分类。", ""])
    for knowledge_type in KNOWLEDGE_TYPES:
        lines.append(f"### {knowledge_type}")
        lines.append("")
        selected = [_marked(item) for item in ideas if item.knowledge_type == knowledge_type]
        _append_bullets(lines, _items_or_pending(selected))
        lines.append("")
    mechanisms = [_marked(item, item.mechanism) for item in ideas if item.mechanism]
    lines.extend(["### 底层变量、机制与必要条件", ""])
    _append_bullets(lines, _items_or_pending(mechanisms))

    lines.extend(["", "## 4. 可检查的分析步骤", ""])
    process_rows = [
        ("问题定义", [_idea_text(item) for item in ideas if item.summary]),
        ("已知信息", [_marked(item) for item in ideas if item.knowledge_type == "事实"]),
        ("缺失信息", [_marked(item) for item in ideas if item.knowledge_type == "未知问题"]),
        ("关键假设", [_marked(item) for item in ideas if item.knowledge_type == "假设"]),
        ("分析步骤", [item.mechanism for item in ideas if item.thinking_mode == "过程思维" and item.mechanism]),
        ("使用的证据", [f"{item.evidence or item.source}（{item.id}）" for item in ideas if item.evidence or item.source]),
        ("判断标准", [item.validation for item in ideas if item.validation]),
        ("不确定性", [_marked(item) for item in ideas if item.confidence in {"低", "待验证"}]),
        ("最终结论", [item.innovation for item in ideas if item.knowledge_type == "推论" and item.innovation]),
        ("下一步验证", [item.next_action or item.validation for item in ideas if item.next_action or item.validation]),
    ]
    for label, values in process_rows:
        lines.append(f"- **{label}**：{'；'.join(_items_or_pending(values, '待验证'))}")

    lines.extend(["", "## 5. 失败模式与预警信号", ""])
    risk_ideas = [item for item in ideas if item.risk]
    risks = [_marked(item, item.risk) for item in risk_ideas]
    hypotheses = [item for item in ideas if item.knowledge_type == "假设"]
    _append_bullets(lines, [
        f"会导致失败：{'；'.join(_items_or_pending(risks, '待验证：尚未登记失败模式'))}",
        f"相反假设：{'；'.join(_items_or_pending([f'“{item.title}”不成立或主因相反' for item in hypotheses], '待验证：尚未登记可证伪的相反假设'))}",
        "看似正确却可能适得其反：过早整理、只收集不验证、用链接数量代替证据质量、让导图分类掩盖真实因果。",
        f"难以及时发现的风险：{'；'.join(_items_or_pending([item.risk for item in risk_ideas if item.confidence in {'低', '待验证'}], '待验证：隐性混杂、时间延迟和选择性记录'))}",
        "早期预警信号：待验证条目持续增加、来源为空、同一结论没有反例、下一步动作长期为空、导图关系无法用一句话解释。",
    ])
    lines.append("- 强制检查点：任何‘假设/推论’在升级为‘事实’前，必须补充来源或证据、判断标准和验证结果。")

    lines.extend(["", "## 6. 专家默会知识", ""])
    tacit = [_marked(item) for item in ideas if item.thinking_mode == "默会知识" or item.knowledge_type == "经验"]
    tacit_text = "；".join(_items_or_pending(tacit, "待验证：尚未记录"))
    _append_bullets(lines, [
        f"论文/教材很少明说的经验：{tacit_text}",
        "新手常见误区：把摘录当理解、把共现当因果、把美观导图当知识体系、忽略失败记录。",
        f"专家优先观察的信号：{tacit_text}",
        "继续/调整/放弃规则：证据支持且风险可控则继续；关键假设动摇则调整；核心机制被反例否定且无替代解释则停止。",
        "异常现象的真实含义：先视为测量、边界条件或模型缺口的信号，不急于解释为新机制。【待验证】",
        "经验适用与失效条件：每条经验必须注明对象、环境、时间尺度和例外；边界变化时重新验证。",
    ])

    lines.extend(["", "## 7. 第一序、第二序和第三序效应", ""])
    first = [item.scene or item.mechanism for item in ideas if item.scene or item.mechanism]
    second = [item.innovation for item in ideas if item.innovation and item.relation_type in {"因果", "反馈", "时序"}]
    third = [item.risk for item in ideas if item.risk and item.thinking_mode == "高杠杆思考"]
    lines.append(f"- 第一序（直接结果）：{'；'.join(_items_or_pending(first, '待验证'))}")
    lines.append(f"- 第二序（后续结果）：{'；'.join(_items_or_pending(second, '待验证'))}")
    lines.append(f"- 第三序（长期结构性影响）：{'；'.join(_items_or_pending(third, '待验证'))}")
    gaps = [item.title for item in ideas if item.knowledge_type == "未知问题" or item.confidence == "待验证"]
    lines.extend(["", "### 费曼检验", ""])
    lines.append(f"- 一句话解释：{conclusion}")
    lines.append("- 生活化类比：OneNote 像收件箱，Obsidian 像经过编目的工具柜，思维导图像标出工具如何配合的施工图。")
    lines.append(f"- 难以解释的部分/理解缺口：{'；'.join(_items_or_pending(gaps, '待验证：尚未主动登记理解缺口'))}")

    lines.extend(["", "## 8. OneNote原始记录清单", ""])
    onenote = [_marked(item) for item in ideas if item.tool_layer == TOOL_LAYERS[0]]
    _append_bullets(lines, _items_or_pending(onenote, "待捕捉：手写记录、组会/导师意见、截图、实验现象、临时想法、报错与未验证假设。"))

    lines.extend(["", "## 9. Obsidian永久笔记清单", ""])
    obsidian_items = [item for item in ideas if item.tool_layer == TOOL_LAYERS[1]] or ideas
    _append_bullets(lines, _items_or_pending([f"[[{item.title}]]：{item.knowledge_type}／{item.thinking_mode}" for item in obsidian_items], "待沉淀：先把一条有来源的事实或可检验假设转为原子笔记。"))
    lines.append(f"- 主题索引页（MOC）：[[MOC-{topic}]]")
    lines.append("- Bases 建议：收录论文、数据集、实验、失败案例、判断规则与可复用流程，并按状态、置信度、来源和下一步筛选。")

    lines.extend(["", "## 10. Obsidian属性字段建议", ""])
    _append_bullets(lines, ["id", "type", "thinking_mode", "relation", "tool_layer", "status", "confidence", "source", "evidence", "tags", "created", "updated", "next_action", "links"])

    lines.extend(["", "## 11. 推荐建立的双向链接", ""])
    links = []
    by_id = {item.id: item for item in ideas}
    for item in ideas:
        for target in item.links:
            target_idea = by_id.get(target)
            links.append(f"[[{item.title}]] → [[{target_idea.title if target_idea else target}]]（{item.relation_type}）")
    if not links:
        for component in components:
            for left, right in zip(component, component[1:]):
                links.append(f"[[{left.title}]] ↔ [[{right.title}]]（待验证：自动关联）")
    _append_bullets(lines, _items_or_pending(links, "待验证：尚未指定笔记关系。"))

    map_lines = _indent_map(ideas, topic)
    lines.extend(["", "## 12. 缩进式思维导图", "", "```text", *map_lines, "```"])
    lines.extend(["", "## 13. Mermaid思维导图代码", "", "```mermaid", mermaid_source(ideas, threshold, name_overrides, assignments).rstrip(), "```"])

    lines.extend(["", "## 14. 三个最高杠杆的行动", ""])
    actions = [item.next_action for item in ideas if item.next_action]
    actions += [item.validation for item in ideas if item.validation and item.validation not in actions]
    actions += ["为所有待验证条目补齐证据与判断标准", "每周把 OneNote 原始记录提炼为原子笔记", "只在导图中保留能影响判断的真实关系"]
    _append_bullets(lines, [f"{index}. {action}" for index, action in enumerate(actions[:3], 1)])

    lines.extend(["", "## 15. 一个最小可执行的下一步", ""])
    next_step = next((item.next_action for item in ideas if item.next_action), "新增一条‘事实’记录，并填写来源、证据和它支持的判断。")
    lines.append(f"- {next_step}")
    return filter_report_sections("\n".join(lines) + "\n", excluded_sections, excluded_lines)


def write_framework(
    ideas: list[Idea], path: Path = DEFAULT_MARKDOWN, threshold: float = 0.18,
    names: dict[str, str] | None = None, assignments: dict[str, str] | None = None,
    excluded_sections: Iterable[int | str] | None = None,
    excluded_lines: Iterable[str] | None = None,
) -> str:
    content = framework_markdown(ideas, threshold, names, assignments, excluded_sections, excluded_lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return content


def mermaid_source(
    ideas: list[Idea], threshold: float, names: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> str:
    def label(value: str) -> str:
        return re.sub(r'["\n\r\[\](){}]', " ", clean_text(value))[:52]
    topic = _topic_title(ideas, names)
    lines = ["mindmap", f"  root(({label(topic)}))"]
    branch_specs: list[tuple[str, tuple[str, ...]]] = [
        ("[包含] 第一性原理", ("第一性原理",)),
        ("[包含] 系统与反馈", ("系统性思维",)),
        ("[包含] 可复核过程", ("过程思维",)),
        ("[包含] 失败与专家判断", ("反向思维", "默会知识")),
        ("[包含] 杠杆与效应", ("高杠杆思考",)),
    ]
    for branch_index, (branch, modes) in enumerate(branch_specs, 1):
        branch_id = f"B{branch_index}"
        lines.append(f"    {branch_id}({label(branch)})")
        selected = [idea for idea in ideas if idea.thinking_mode in modes][:7]
        if not selected:
            lines.append(f"      {branch_id}P[行动 待补充并验证]")
        for idea_index, idea in enumerate(selected, 1):
            node = f"{branch_id}I{idea_index}"
            pending = " 待验证" if idea.confidence == "待验证" else ""
            lines.append(f"      {node}[{label('[' + idea.relation_type + '] ' + idea.title + pending)}]")
            if idea.evidence or idea.source:
                lines.append(f"        {node}E[{label('[证据] ' + (idea.evidence or idea.source))}]")
            if idea.next_action:
                lines.append(f"        {node}A[{label('[行动] ' + idea.next_action)}]")
    lines.append("    TOOLS([时序] 工具工作流)")
    for index, layer in enumerate(TOOL_LAYERS, 1):
        count = sum(1 for idea in ideas if idea.tool_layer == layer)
        lines.append(f"      L{index}[{label('[包含] ' + layer + ' ' + str(count))}]")
    lines.append("    NEXT([行动] 下一步)")
    actions = [idea.next_action for idea in ideas if idea.next_action][:3] or ["定义一个可验证的小步骤"]
    for index, action in enumerate(actions, 1):
        lines.append(f"      A{index}[{label('[行动] ' + action)}]")
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
                "tags": item.tags,
                "fields": {
                    "知识状态": item.knowledge_type, "思维方式": item.thinking_mode,
                    "关系": item.relation_type, "工具层": item.tool_layer,
                    "置信度": item.confidence, **{FIELD_LABELS[key]: value for key, value in item.field_items()},
                    **({"来源": item.source} if item.source else {}),
                    **({"证据": item.evidence} if item.evidence else {}),
                    **({"下一步": item.next_action} if item.next_action else {}),
                },
            } for item in component],
        })
    return payload


def html_visual_export(
    ideas: list[Idea], threshold: float, names: dict[str, str] | None = None,
    assignments: dict[str, str] | None = None,
) -> str:
    data = json.dumps(visual_payload(ideas, threshold, names, assignments), ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>知识处理框架</title>
<style>body{{margin:0;background:#f5f7fb;color:#172033;font:15px 'Microsoft YaHei',sans-serif}}header{{padding:22px 5%;background:#172033;color:white}}h1{{margin:0;font-size:24px}}#map{{padding:24px 5%;display:grid;gap:18px}}.topic{{background:#fff;border-left:5px solid #246bce;padding:16px;border-radius:8px;box-shadow:0 2px 8px #17203312}}.idea{{margin:12px 0 0 18px;padding:12px;border:1px solid #d8e1f0;border-radius:6px}}.meta{{color:#58708f;font-size:13px}}.fields{{margin:8px 0 0;padding-left:18px}}li{{margin:4px 0}}</style></head>
<body><header><h1>{html.escape(_topic_title(ideas, names))}｜知识处理框架</h1><div>共 {len(ideas)} 条知识记录，阈值 {threshold:.2f}</div></header><main id=\"map\"></main>
<script>const data={data}; const esc=s=>String(s).replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;'}}[c]));
document.getElementById('map').innerHTML=data.map((t,i)=>`<section class=\"topic\"><h2>${{i+1}}. ${{esc(t.name)}}</h2><div class=\"meta\">${{esc(t.keywords.join('、'))}} · ${{t.ideas.length}} 条记录</div>${{t.ideas.map(x=>`<article class=\"idea\"><strong>${{esc(x.title)}}</strong><div>${{esc(x.preview)}}</div><ul class=\"fields\">${{Object.entries(x.fields).map(([k,v])=>`<li><b>${{esc(k)}}</b>：${{esc(v)}}</li>`).join('')}}</ul></article>`).join('')}}</section>`).join('');</script></body></html>"""


def safe_note_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "-", clean_text(value)).strip(" .")
    return cleaned[:90] or "未命名知识"


def obsidian_note(idea: Idea, topic: str) -> str:
    properties = {
        "id": idea.id,
        "type": idea.knowledge_type,
        "thinking_mode": idea.thinking_mode,
        "relation": idea.relation_type,
        "tool_layer": idea.tool_layer,
        "status": "待验证" if idea.confidence == "待验证" or idea.knowledge_type in {"假设", "推论", "未知问题"} else "已记录",
        "confidence": idea.confidence,
        "source": idea.source,
        "tags": idea.tags,
        "created": idea.created_at,
        "updated": idea.updated_at or idea.created_at,
        "next_action": idea.next_action,
    }
    lines = ["---"]
    for key, value in properties.items():
        if value in ("", []):
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", "", f"# {idea.title}", "", _idea_text(idea), "", "## 证据与来源", ""])
    lines.append(idea.evidence or idea.source or "待验证：尚未补充证据或来源。")
    lines.extend(["", "## 关系", "", f"- [[MOC-{topic}]]"])
    lines.extend(f"- [[{target}]]（{idea.relation_type}）" for target in idea.links)
    lines.extend(["", "## 判断与验证", "", f"- 验证标准：{idea.validation or '待验证'}", f"- 风险/反例：{idea.risk or '待验证'}", f"- 下一步：{idea.next_action or '待验证'}", ""])
    return "\n".join(lines)


def export_obsidian_vault(
    ideas: list[Idea], destination: Path = DEFAULT_OBSIDIAN,
    names: dict[str, str] | None = None,
) -> list[Path]:
    """Export atomic notes and a MOC without deleting existing user files."""
    destination.mkdir(parents=True, exist_ok=True)
    topic = safe_note_name(_topic_title(ideas, names))
    written: list[Path] = []
    note_names: dict[str, str] = {}
    for idea in ideas:
        note_name = safe_note_name(idea.title)
        if note_name in note_names.values():
            note_name = f"{note_name}-{idea.id[-6:]}"
        note_names[idea.id] = note_name
        path = destination / f"{note_name}.md"
        path.write_text(obsidian_note(idea, topic), encoding="utf-8")
        written.append(path)
    moc = destination / f"MOC-{topic}.md"
    moc_lines = [f"# MOC-{topic}", "", "## 知识条目", ""]
    for idea in ideas:
        moc_lines.append(f"- [[{note_names[idea.id]}]]｜{idea.knowledge_type}｜{idea.thinking_mode}｜{idea.confidence}")
    moc_lines.extend(["", "## Bases 建议筛选", "", "- type、thinking_mode、confidence、source、next_action、tags", ""])
    moc.write_text("\n".join(moc_lines), encoding="utf-8")
    written.append(moc)
    return written


def onenote_capture_markdown(ideas: list[Idea], names: dict[str, str] | None = None) -> str:
    topic = _topic_title(ideas, names)
    lines = [f"# {topic}｜OneNote 原始捕捉清单", "", "以下内容保持原貌；每周复盘时再决定是否沉淀到 Obsidian。", ""]
    selected = [idea for idea in ideas if idea.tool_layer == TOOL_LAYERS[0]]
    for idea in selected:
        lines.extend([f"- [ ] {idea.title}", f"  - 类型：{idea.knowledge_type}｜思维：{idea.thinking_mode}｜关系：{idea.relation_type}", f"  - 原文：{_idea_text(idea)}", f"  - 来源：{idea.source or '待补充'}", f"  - 下一步：{idea.next_action or '待判断'}"])
    if not selected:
        lines.append("- [ ] 捕捉一条手写记录、截图、实验现象、临时想法、报错或未验证假设。")
    return "\n".join(lines) + "\n"


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
                    mechanism=args.mechanism, scene=args.scene, validation=args.validation, risk=args.risk,
                    knowledge_type=args.knowledge_type, thinking_mode=args.thinking_mode,
                    relation_type=args.relation_type, tool_layer=args.tool_layer,
                    source=args.source, evidence=args.evidence, confidence=args.confidence,
                    next_action=args.next_action, links=args.links)
    if not any(value for _, value in idea.field_items()):
        print("至少需要填写一项想法内容。", file=sys.stderr)
        return 2
    ideas.append(idea)
    save_ideas(ideas, args.store)
    meta = load_meta(args.meta)
    write_framework(ideas, args.output, args.threshold, meta["trunk_names"], meta["idea_assignments"], meta["excluded_report_sections"], meta["report_exclusions"])
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
    write_framework(ideas, args.output, args.threshold, meta["trunk_names"], meta["idea_assignments"], meta["excluded_report_sections"], meta["report_exclusions"])
    print(f"已生成：{args.output}")
    return 0


def command_export(args: argparse.Namespace) -> int:
    ideas, meta = load_ideas(args.store), load_meta(args.meta)
    write_framework(ideas, args.output, args.threshold, meta["trunk_names"], meta["idea_assignments"], meta["excluded_report_sections"], meta["report_exclusions"])
    mermaid_path = args.output.with_name("framework_visual.mmd")
    html_path = args.output.with_name("framework_visual.html")
    onenote_path = args.output.with_name("onenote_capture.md")
    mermaid_path.write_text(mermaid_source(ideas, args.threshold, meta["trunk_names"], meta["idea_assignments"]), encoding="utf-8")
    html_path.write_text(html_visual_export(ideas, args.threshold, meta["trunk_names"], meta["idea_assignments"]), encoding="utf-8")
    onenote_path.write_text(onenote_capture_markdown(ideas, meta["trunk_names"]), encoding="utf-8")
    notes = export_obsidian_vault(ideas, args.obsidian, meta["trunk_names"])
    print(f"已导出报告、Mermaid、网页、OneNote 清单及 {len(notes)} 个 Obsidian 文件。")
    return 0


def command_ui(args: argparse.Namespace) -> int:
    from idea_framework_ui import main as ui_main
    return ui_main(["--store", str(args.store), "--output", str(args.output), "--meta", str(args.meta)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OneNote + Obsidian + 思维导图知识处理工具")
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
    add.add_argument("--knowledge-type", choices=KNOWLEDGE_TYPES, default="未知问题", help="事实/假设/推论/经验/未知问题")
    add.add_argument("--thinking-mode", choices=THINKING_MODES, default="过程思维", help="本条记录使用的思维方式")
    add.add_argument("--relation-type", choices=RELATION_TYPES, default="包含", help="与主题或链接目标的关系")
    add.add_argument("--tool-layer", choices=TOOL_LAYERS, default=TOOL_LAYERS[0], help="当前工具层")
    add.add_argument("--source", default="", help="来源")
    add.add_argument("--evidence", default="", help="证据")
    add.add_argument("--confidence", choices=CONFIDENCE_LEVELS, default="待验证", help="置信度")
    add.add_argument("--next-action", default="", help="下一步验证或行动")
    add.add_argument("--links", default="", help="关联条目 ID 或笔记名，逗号分隔")
    add.set_defaults(handler=command_add)
    listing = subparsers.add_parser("list", help="列出历史想法")
    listing.set_defaults(handler=command_list)
    search = subparsers.add_parser("search", help="检索历史想法")
    search.add_argument("query")
    search.set_defaults(handler=command_search)
    framework = subparsers.add_parser("framework", help="重建 Markdown 框架")
    framework.set_defaults(handler=command_framework)
    export = subparsers.add_parser("export", help="导出完整报告、OneNote、Obsidian、Mermaid 和网页")
    export.add_argument("--obsidian", type=Path, default=DEFAULT_OBSIDIAN, help="Obsidian 导出目录")
    export.set_defaults(handler=command_export)
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
