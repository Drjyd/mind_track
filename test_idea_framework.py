import tempfile
import unittest
from pathlib import Path

from idea_framework import (
    TOOL_LAYERS,
    Idea,
    export_obsidian_vault,
    framework_markdown,
    load_meta,
    mermaid_source,
    new_idea,
    normalize_tags,
    onenote_capture_markdown,
    save_meta,
)


class KnowledgeFrameworkTests(unittest.TestCase):
    def sample_ideas(self):
        return [
            new_idea(
                title="温漂现象",
                summary="连续工作后基线抬升",
                knowledge_type="事实",
                thinking_mode="第一性原理",
                relation_type="证据",
                tool_layer=TOOL_LAYERS[0],
                source="实验日志",
                evidence="三轮曲线",
                confidence="高",
            ),
            new_idea(
                title="探测器增益假设",
                summary="温度升高可能改变探测器增益",
                mechanism="增益随温度变化",
                validation="恒温对照",
                risk="环境温度与设备自热混杂",
                knowledge_type="假设",
                thinking_mode="反向思维",
                relation_type="因果",
                tool_layer=TOOL_LAYERS[1],
                confidence="待验证",
                next_action="恒温条件重复三轮",
            ),
        ]

    def test_legacy_record_gets_safe_defaults(self):
        idea = Idea.from_record({"content": "旧版记录"})
        self.assertEqual(idea.knowledge_type, "未知问题")
        self.assertEqual(idea.confidence, "待验证")
        self.assertEqual(idea.tool_layer, TOOL_LAYERS[0])

    def test_report_contains_all_required_sections_and_markers(self):
        report = framework_markdown(self.sample_ideas())
        for number in range(1, 16):
            self.assertIn(f"## {number}.", report)
        self.assertIn("【待验证】", report)
        self.assertIn("[因果]", report)
        self.assertIn("费曼检验", report)

    def test_report_supports_selective_section_and_line_removal(self):
        ideas = self.sample_ideas()
        report = framework_markdown(
            ideas,
            excluded_sections=[5],
            excluded_lines=["- 一句话解释：连续工作后基线抬升"],
        )
        self.assertNotIn("## 5. 失败模式与预警信号", report)
        self.assertNotIn("- 一句话解释：连续工作后基线抬升", report)
        self.assertIn("## 6. 专家默会知识", report)

    def test_mermaid_is_relationship_first(self):
        source = mermaid_source(self.sample_ideas(), 0.18)
        self.assertTrue(source.startswith("mindmap\n"))
        self.assertIn("因果", source)
        self.assertIn("工具工作流", source)

    def test_tool_exports(self):
        ideas = self.sample_ideas()
        with tempfile.TemporaryDirectory() as folder:
            paths = export_obsidian_vault(ideas, Path(folder))
            self.assertEqual(len(paths), 3)
            self.assertTrue(any(path.name.startswith("MOC-") for path in paths))
            note_text = paths[0].read_text(encoding="utf-8")
            self.assertIn("thinking_mode:", note_text)
            self.assertIn("status:", note_text)
        self.assertIn("OneNote 原始捕捉清单", onenote_capture_markdown(ideas))

    def test_metadata_roundtrip_keeps_capture_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "meta.json"
            save_meta({
                "trunk_names": {},
                "idea_assignments": {},
                "pinned_ids": ["I1"],
                "capture_draft": {"quick": "尚未保存的灵感"},
                "excluded_report_sections": [5],
                "report_exclusions": ["一行不需要的内容"],
            }, path)
            loaded = load_meta(path)
            self.assertEqual(loaded["capture_draft"]["quick"], "尚未保存的灵感")
            self.assertEqual(loaded["pinned_ids"], ["I1"])
            self.assertEqual(loaded["excluded_report_sections"], [5])
            self.assertEqual(loaded["report_exclusions"], ["一行不需要的内容"])
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_tag_normalization_supports_common_separators(self):
        self.assertEqual(normalize_tags("#实验，温漂; 实验；传感器"), ["实验", "温漂", "传感器"])


if __name__ == "__main__":
    unittest.main()
