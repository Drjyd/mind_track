"""Tkinter desktop interface for Ideas Framework.

This module is deliberately dependency-free.  It is meant for repeated daily
use: capture a thought quickly, inspect what it relates to, then correct the
automatic structure when your own judgement is better than keyword matching.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, Canvas, StringVar, Text, Tk, Toplevel
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from idea_framework import (
    DEFAULT_MARKDOWN,
    DEFAULT_META,
    DEFAULT_STORE,
    FIELD_LABELS,
    FIELD_ORDER,
    Idea,
    clean_text,
    cluster_ideas_with_assignments,
    component_key,
    html_visual_export,
    load_ideas,
    load_meta,
    matching_ideas,
    mermaid_source,
    new_idea,
    save_ideas,
    save_meta,
    topic_for_idea,
    topic_name,
    visual_payload,
    write_framework,
)


COLORS = {
    "ink": "#182235", "muted": "#63718a", "line": "#d8e1ef", "bg": "#f4f7fb",
    "panel": "#ffffff", "blue": "#2166c2", "blue_soft": "#eaf2ff", "green": "#138a57",
    "green_soft": "#e7f7ef", "orange": "#c56a10", "orange_soft": "#fff0df", "purple": "#7a45c6",
    "purple_soft": "#f2eafe", "red": "#c23a3a", "red_soft": "#fff0f0",
}
NODE_COLORS = [(COLORS["blue"], COLORS["blue_soft"]), (COLORS["green"], COLORS["green_soft"]),
               (COLORS["orange"], COLORS["orange_soft"]), (COLORS["purple"], COLORS["purple_soft"])]


class IdeaFrameworkApp:
    def __init__(self, root: Tk, store_path: Path, output_path: Path, meta_path: Path) -> None:
        self.root = root
        self.store_path = store_path
        self.output_path = output_path
        self.meta_path = meta_path
        self.ideas: list[Idea] = []
        self.meta: dict[str, Any] = {}
        self.components: list[list[Idea]] = []
        self.selected_idea_id = ""
        self.current_topic_key = ""
        self.visual_nodes: dict[str, Idea] = {}
        self.status_var = StringVar(value="正在读取本地想法库…")
        self.search_var = StringVar()
        self.threshold_var = StringVar(value="0.18")
        self.pinned_only_var = StringVar(value="0")
        self._configure_window()
        self._configure_style()
        self._build_layout()
        self.refresh_all(keep_selection=False)

    def _configure_window(self) -> None:
        self.root.title("想法与创新点逻辑框架")
        self.root.geometry("1450x880")
        self.root.minsize(1100, 700)
        self.root.configure(bg=COLORS["bg"])
        try:
            self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        except Exception:
            pass

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Header.TFrame", background=COLORS["ink"])
        style.configure("Header.TLabel", background=COLORS["ink"], foreground="#ffffff", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("HeaderSub.TLabel", background=COLORS["ink"], foreground="#c7d4ea")
        style.configure("Title.TLabel", background=COLORS["panel"], foreground=COLORS["ink"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Body.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("Status.TLabel", background=COLORS["ink"], foreground="#dce7fa")
        style.configure("Accent.TButton", background=COLORS["blue"], foreground="#ffffff", borderwidth=0, padding=(12, 7))
        style.map("Accent.TButton", background=[("active", "#1754a5")])
        style.configure("Success.TButton", background=COLORS["green"], foreground="#ffffff", borderwidth=0, padding=(12, 7))
        style.map("Success.TButton", background=[("active", "#0e7046")])
        style.configure("Danger.TButton", background=COLORS["red"], foreground="#ffffff", borderwidth=0, padding=(10, 6))
        style.map("Danger.TButton", background=[("active", "#a52c2c")])
        style.configure("TButton", padding=(9, 6), background="#ffffff", foreground=COLORS["ink"], borderwidth=1)
        style.map("TButton", background=[("active", COLORS["blue_soft"])])
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 9), background="#e9eef7", foreground=COLORS["muted"])
        style.map("TNotebook.Tab", background=[("selected", COLORS["panel"])], foreground=[("selected", COLORS["blue"])])
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground=COLORS["ink"], rowheight=29, bordercolor=COLORS["line"], borderwidth=1)
        style.configure("Treeview.Heading", background="#edf2fa", foreground=COLORS["ink"], font=("Microsoft YaHei UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", COLORS["ink"])])
        style.configure("TLabelframe", background=COLORS["panel"], bordercolor=COLORS["line"])
        style.configure("TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["ink"], font=("Microsoft YaHei UI", 10, "bold"))

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(22, 14))
        header.pack(fill=X)
        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(title_box, text="想法与创新点逻辑框架", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="从快速记录到可演化的主题知识库", style="HeaderSub.TLabel").pack(anchor="w", pady=(2, 0))
        actions = ttk.Frame(header, style="Header.TFrame")
        actions.pack(side=RIGHT)
        ttk.Button(actions, text="刷新", command=self.refresh_all).pack(side=LEFT, padx=3)
        ttk.Button(actions, text="导出 Markdown", command=self.export_markdown).pack(side=LEFT, padx=3)
        ttk.Button(actions, text="导出 Mermaid", command=self.export_mermaid).pack(side=LEFT, padx=3)
        ttk.Button(actions, text="导出网页", command=self.export_html).pack(side=LEFT, padx=3)
        ttk.Button(actions, text="备份数据", command=self.backup_data).pack(side=LEFT, padx=3)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill=BOTH, expand=True, padx=12, pady=12)
        left = ttk.Frame(body, style="Panel.TFrame", padding=14, width=365)
        right = ttk.Frame(body, style="App.TFrame")
        body.add(left, weight=1)
        body.add(right, weight=4)
        self._build_capture_panel(left)
        self._build_right_area(right)

        footer = ttk.Frame(self.root, style="Header.TFrame", padding=(14, 6))
        footer.pack(fill=X, side="bottom")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w")

    def _build_capture_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="写入想法", style="Title.TLabel").pack(anchor="w")
        ttk.Label(parent, text="保存后会重新检索全部历史内容，并更新文字与图像框架。", style="Body.TLabel", wraplength=320).pack(anchor="w", pady=(2, 10))
        form = ttk.Frame(parent, style="Panel.TFrame")
        form.pack(fill=BOTH, expand=True)

        ttk.Label(form, text="标题（可留空，自动从想法中提取）", style="Body.TLabel").pack(anchor="w")
        self.title_entry = ttk.Entry(form)
        self.title_entry.pack(fill=X, pady=(3, 8))
        ttk.Label(form, text="标签（逗号分隔，用于更准确关联）", style="Body.TLabel").pack(anchor="w")
        self.tags_entry = ttk.Entry(form)
        self.tags_entry.pack(fill=X, pady=(3, 8))

        self.input_tabs = ttk.Notebook(form)
        self.input_tabs.pack(fill=BOTH, expand=True)
        quick = ttk.Frame(self.input_tabs, style="Panel.TFrame", padding=(4, 8))
        structured = ttk.Frame(self.input_tabs, style="Panel.TFrame", padding=(4, 8))
        self.input_tabs.add(quick, text="快速输入")
        self.input_tabs.add(structured, text="结构化输入")
        ttk.Label(quick, text="把尚未整理的想法直接写下来。", style="Body.TLabel").pack(anchor="w")
        self.quick_text = Text(quick, height=13, wrap="word", relief="solid", borderwidth=1, highlightthickness=0, font=("Microsoft YaHei UI", 10))
        self.quick_text.pack(fill=BOTH, expand=True, pady=(5, 4))
        self.quick_text.bind("<KeyRelease>", lambda _event: self.refresh_draft_matches())
        self.quick_count_var = StringVar(value="0 字")
        ttk.Label(quick, textvariable=self.quick_count_var, style="Body.TLabel").pack(anchor="e")

        # Structured capture contains more fields than a compact left panel can
        # show at once, so it scrolls instead of hiding lower fields.
        structured_canvas = Canvas(structured, bg=COLORS["panel"], highlightthickness=0)
        structured_scroll = ttk.Scrollbar(structured, orient=VERTICAL, command=structured_canvas.yview)
        structured_canvas.configure(yscrollcommand=structured_scroll.set)
        structured_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        structured_scroll.pack(side=RIGHT, fill=Y)
        structured_inner = ttk.Frame(structured_canvas, style="Panel.TFrame")
        structured_window = structured_canvas.create_window((0, 0), window=structured_inner, anchor="nw")
        structured_inner.bind("<Configure>", lambda _event: structured_canvas.configure(scrollregion=structured_canvas.bbox("all")))
        structured_canvas.bind("<Configure>", lambda event: structured_canvas.itemconfigure(structured_window, width=event.width))
        self.structured_texts: dict[str, Text] = {}
        for field in FIELD_ORDER:
            ttk.Label(structured_inner, text=FIELD_LABELS[field], style="Body.TLabel").pack(anchor="w", pady=(2, 0))
            widget = Text(structured_inner, height=3 if field != "summary" else 2, wrap="word", relief="solid", borderwidth=1, highlightthickness=0, font=("Microsoft YaHei UI", 9))
            widget.pack(fill=X, pady=(2, 5))
            widget.bind("<KeyRelease>", lambda _event: self.refresh_draft_matches())
            self.structured_texts[field] = widget

        controls = ttk.Frame(parent, style="Panel.TFrame")
        controls.pack(fill=X, pady=(10, 0))
        ttk.Button(controls, text="写入并重建框架", style="Success.TButton", command=self.save_new_idea).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(controls, text="清空", command=self.clear_capture).pack(side=LEFT, padx=(8, 0))

        search_box = ttk.LabelFrame(parent, text="输入时的历史关联", padding=8)
        search_box.pack(fill=BOTH, expand=True, pady=(12, 0))
        self.draft_matches = ttk.Treeview(search_box, columns=("score", "topic", "title"), show="headings", height=7)
        self.draft_matches.heading("score", text="关联")
        self.draft_matches.heading("topic", text="主题")
        self.draft_matches.heading("title", text="历史想法")
        self.draft_matches.column("score", width=50, anchor="center", stretch=False)
        self.draft_matches.column("topic", width=95, stretch=False)
        self.draft_matches.column("title", width=180)
        self.draft_matches.pack(fill=BOTH, expand=True)
        self.draft_matches.bind("<<TreeviewSelect>>", self.on_draft_match_select)

    def _build_right_area(self, parent: ttk.Frame) -> None:
        search_row = ttk.Frame(parent, style="App.TFrame")
        search_row.pack(fill=X, pady=(0, 8))
        ttk.Label(search_row, text="检索历史", foreground=COLORS["ink"]).pack(side=LEFT)
        search = ttk.Entry(search_row, textvariable=self.search_var)
        search.pack(side=LEFT, fill=X, expand=True, padx=(8, 6))
        search.bind("<KeyRelease>", lambda _event: self.refresh_history())
        ttk.Button(search_row, text="清除", command=lambda: (self.search_var.set(""), self.refresh_history())).pack(side=LEFT)
        ttk.Label(search_row, text="关联阈值", foreground=COLORS["ink"]).pack(side=LEFT, padx=(16, 5))
        threshold = ttk.Combobox(search_row, textvariable=self.threshold_var, values=("0.10", "0.14", "0.18", "0.22", "0.28", "0.35"), state="readonly", width=6)
        threshold.pack(side=LEFT)
        threshold.bind("<<ComboboxSelected>>", lambda _event: self.rebuild_from_threshold())

        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill=BOTH, expand=True)
        preview_tab = ttk.Frame(self.tabs, style="Panel.TFrame", padding=10)
        visual_tab = ttk.Frame(self.tabs, style="Panel.TFrame", padding=8)
        history_tab = ttk.Frame(self.tabs, style="Panel.TFrame", padding=10)
        topics_tab = ttk.Frame(self.tabs, style="Panel.TFrame", padding=10)
        self.tabs.add(preview_tab, text="文本框架")
        self.tabs.add(visual_tab, text="图像化框架")
        self.tabs.add(history_tab, text="历史列表")
        self.tabs.add(topics_tab, text="主题管理")
        self._build_preview(preview_tab)
        self._build_visual(visual_tab)
        self._build_history(history_tab)
        self._build_topics(topics_tab)

    def _build_preview(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.pack(fill=X, pady=(0, 6))
        self.framework_summary_var = StringVar()
        ttk.Label(top, textvariable=self.framework_summary_var, style="Body.TLabel").pack(side=LEFT)
        ttk.Button(top, text="打开 Markdown 文件", command=self.open_markdown).pack(side=RIGHT)
        holder = ttk.Frame(parent, style="Panel.TFrame")
        holder.pack(fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(holder, orient=VERTICAL)
        self.markdown_text = Text(holder, wrap="word", bg="#fbfcff", fg=COLORS["ink"], relief="solid", borderwidth=1, highlightthickness=0, padx=16, pady=12, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.markdown_text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.markdown_text.pack(side=LEFT, fill=BOTH, expand=True)
        self.markdown_text.tag_configure("h1", foreground=COLORS["blue"], font=("Microsoft YaHei UI", 16, "bold"), spacing1=8, spacing3=6)
        self.markdown_text.tag_configure("h2", foreground=COLORS["ink"], font=("Microsoft YaHei UI", 13, "bold"), spacing1=13, spacing3=5)
        self.markdown_text.tag_configure("h3", foreground=COLORS["purple"], font=("Microsoft YaHei UI", 11, "bold"), spacing1=9, spacing3=3)
        self.markdown_text.tag_configure("bullet", foreground="#314564", lmargin1=12, lmargin2=28, spacing1=2)

    def _build_visual(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="点击主题或想法节点可查看摘要；此视图用简约结构突出关系，而不是重复 Markdown 长文。", style="Body.TLabel").pack(anchor="w", pady=(0, 6))
        visual_holder = ttk.Frame(parent, style="Panel.TFrame")
        visual_holder.pack(fill=BOTH, expand=True)
        ybar = ttk.Scrollbar(visual_holder, orient=VERTICAL)
        xbar = ttk.Scrollbar(visual_holder, orient="horizontal")
        self.visual_canvas = Canvas(visual_holder, bg="#fbfcff", highlightthickness=0, yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.config(command=self.visual_canvas.yview)
        xbar.config(command=self.visual_canvas.xview)
        self.visual_canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        visual_holder.grid_columnconfigure(0, weight=1)
        visual_holder.grid_rowconfigure(0, weight=1)
        detail = ttk.LabelFrame(parent, text="节点详情", padding=8)
        detail.pack(fill=X, pady=(8, 0))
        self.visual_detail_var = StringVar(value="选择一个节点查看内容与来源。")
        ttk.Label(detail, textvariable=self.visual_detail_var, style="Body.TLabel", wraplength=900, justify=LEFT).pack(anchor="w")

    def _build_history(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.pack(fill=X, pady=(0, 8))
        ttk.Button(toolbar, text="编辑选中想法", command=self.edit_selected_idea).pack(side=LEFT)
        ttk.Button(toolbar, text="收藏/取消收藏", command=self.toggle_pin).pack(side=LEFT, padx=5)
        ttk.Button(toolbar, text="删除选中想法", style="Danger.TButton", command=self.delete_selected_idea).pack(side=LEFT, padx=5)
        self.pinned_check = ttk.Checkbutton(toolbar, text="只看收藏", variable=self.pinned_only_var, onvalue="1", offvalue="0", command=self.refresh_history)
        self.pinned_check.pack(side=RIGHT)
        holder = ttk.Frame(parent, style="Panel.TFrame")
        holder.pack(fill=BOTH, expand=True)
        scroll = ttk.Scrollbar(holder, orient=VERTICAL)
        self.history_tree = ttk.Treeview(holder, columns=("pin", "time", "topic", "title", "tags"), show="headings", yscrollcommand=scroll.set, selectmode="browse")
        scroll.config(command=self.history_tree.yview)
        for column, text, width in (("pin", "收藏", 52), ("time", "写入时间", 132), ("topic", "当前主题", 150), ("title", "标题", 220), ("tags", "标签", 180)):
            self.history_tree.heading(column, text=text)
            self.history_tree.column(column, width=width, anchor="center" if column in {"pin", "time"} else "w", stretch=column == "title")
        self.history_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)
        self.history_tree.bind("<<TreeviewSelect>>", self.on_history_select)
        detail = ttk.LabelFrame(parent, text="完整内容", padding=8)
        detail.pack(fill=X, pady=(8, 0))
        self.history_detail_var = StringVar(value="从列表中选择一条历史想法。")
        ttk.Label(detail, textvariable=self.history_detail_var, style="Body.TLabel", justify=LEFT, wraplength=1000).pack(anchor="w")

    def _build_topics(self, parent: ttk.Frame) -> None:
        explanation = ttk.Label(parent, text="自动归类始终存在；当你确认一个主题或移动记录后，它会被固定，后续重新生成不会改变该人工判断。", style="Body.TLabel", wraplength=980)
        explanation.pack(anchor="w", pady=(0, 7))
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.pack(fill=X, pady=(0, 8))
        ttk.Button(toolbar, text="重命名主题", command=self.rename_topic).pack(side=LEFT)
        ttk.Button(toolbar, text="固定选中主题", command=self.lock_selected_topic).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="用历史选中想法新建树干", command=self.create_trunk_from_selected).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="移动历史选中想法到此主题", style="Accent.TButton", command=self.move_selected_idea_to_topic).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="合并选中主题", command=self.merge_selected_topics).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="恢复自动归类", command=self.unlock_selected_topic).pack(side=LEFT, padx=4)
        holder = ttk.Frame(parent, style="Panel.TFrame")
        holder.pack(fill=BOTH, expand=True)
        scroll = ttk.Scrollbar(holder, orient=VERTICAL)
        self.topic_tree = ttk.Treeview(holder, columns=("count", "mode", "keywords"), show="tree headings", yscrollcommand=scroll.set, selectmode="extended")
        scroll.config(command=self.topic_tree.yview)
        self.topic_tree.heading("#0", text="主题")
        self.topic_tree.heading("count", text="想法数")
        self.topic_tree.heading("mode", text="组织方式")
        self.topic_tree.heading("keywords", text="关键词")
        self.topic_tree.column("#0", width=240, stretch=True)
        self.topic_tree.column("count", width=72, anchor="center", stretch=False)
        self.topic_tree.column("mode", width=94, anchor="center", stretch=False)
        self.topic_tree.column("keywords", width=360, stretch=True)
        self.topic_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)
        self.topic_tree.bind("<<TreeviewSelect>>", self.on_topic_select)
        self.topic_detail_var = StringVar(value="选择主题查看整理状态。")
        ttk.Label(parent, textvariable=self.topic_detail_var, style="Body.TLabel", wraplength=1000).pack(anchor="w", pady=(8, 0))

    @property
    def threshold(self) -> float:
        try:
            return float(self.threshold_var.get())
        except ValueError:
            return 0.18

    @property
    def names(self) -> dict[str, str]:
        return self.meta.get("trunk_names", {})

    @property
    def assignments(self) -> dict[str, str]:
        return self.meta.get("idea_assignments", {})

    @property
    def pinned_ids(self) -> set[str]:
        return set(self.meta.get("pinned_ids", []))

    def refresh_all(self, keep_selection: bool = True) -> None:
        selected = self.selected_idea_id if keep_selection else ""
        self.ideas = load_ideas(self.store_path)
        self.meta = load_meta(self.meta_path)
        existing = {item.id for item in self.ideas}
        self.meta["pinned_ids"] = [item_id for item_id in self.pinned_ids if item_id in existing]
        self.meta["idea_assignments"] = {item_id: target for item_id, target in self.assignments.items() if item_id in existing and target in existing}
        self.components = cluster_ideas_with_assignments(self.ideas, self.threshold, self.assignments)
        self._write_framework()
        self.render_markdown()
        self.draw_visual()
        self.refresh_history()
        self.refresh_topics()
        if selected and any(item.id == selected for item in self.ideas):
            self.select_history_item(selected)
        self.refresh_draft_matches()
        self.status_var.set(f"已加载 {len(self.ideas)} 条想法，形成 {len(self.components)} 个主题；所有框架已同步更新。")

    def _write_framework(self) -> str:
        return write_framework(self.ideas, self.output_path, self.threshold, self.names, self.assignments)

    def rebuild_from_threshold(self) -> None:
        self.refresh_all()
        self.status_var.set(f"关联阈值已改为 {self.threshold:.2f}，自动主题已重新计算。")

    def save_metadata(self) -> None:
        self.meta["trunk_names"] = self.names
        self.meta["idea_assignments"] = self.assignments
        self.meta["pinned_ids"] = sorted(self.pinned_ids)
        save_meta(self.meta, self.meta_path)

    def capture_values(self) -> dict[str, str]:
        quick = clean_text(self.quick_text.get("1.0", END))
        structured = {field: clean_text(widget.get("1.0", END)) for field, widget in self.structured_texts.items()}
        if quick:
            structured["summary"] = clean_text(" ".join(part for part in (quick, structured.get("summary", "")) if part))
        return {
            "title": clean_text(self.title_entry.get()), "tags": clean_text(self.tags_entry.get()),
            **structured,
        }

    def save_new_idea(self) -> None:
        values = self.capture_values()
        if not any(values.get(field) for field in FIELD_ORDER):
            messagebox.showwarning("尚未填写", "请至少填写“快速输入”或任意一个结构化字段。", parent=self.root)
            return
        idea = new_idea(**values)
        self.ideas.append(idea)
        save_ideas(self.ideas, self.store_path)
        self.clear_capture()
        self.selected_idea_id = idea.id
        self.refresh_all()
        self.tabs.select(0)
        self.status_var.set(f"已写入“{idea.title}”。已基于全部历史内容重新检索并生成框架。")

    def clear_capture(self) -> None:
        self.title_entry.delete(0, END)
        self.tags_entry.delete(0, END)
        self.quick_text.delete("1.0", END)
        for widget in self.structured_texts.values():
            widget.delete("1.0", END)
        self.quick_count_var.set("0 字")
        self.refresh_draft_matches()

    def refresh_draft_matches(self) -> None:
        draft = " ".join(value for value in self.capture_values().values() if value)
        self.quick_count_var.set(f"{len(clean_text(self.quick_text.get('1.0', END)))} 字")
        for item in self.draft_matches.get_children():
            self.draft_matches.delete(item)
        if not draft or not self.ideas:
            return
        for idea, score in matching_ideas(self.ideas, draft)[:8]:
            topic = topic_for_idea(idea.id, self.components, self.names)
            self.draft_matches.insert("", END, iid=idea.id, values=(f"{score:.0%}", topic, idea.title))

    def on_draft_match_select(self, _event: object = None) -> None:
        selected = self.draft_matches.selection()
        if selected:
            self.selected_idea_id = selected[0]
            self.show_idea_detail(selected[0])
            self.tabs.select(2)
            self.select_history_item(selected[0])

    def render_markdown(self) -> None:
        content = self._write_framework()
        self.markdown_text.config(state="normal")
        self.markdown_text.delete("1.0", END)
        for line in content.splitlines(True):
            tag = ""
            if line.startswith("# "):
                tag = "h1"
            elif line.startswith("## "):
                tag = "h2"
            elif line.startswith("### "):
                tag = "h3"
            elif line.startswith("- "):
                tag = "bullet"
            self.markdown_text.insert(END, line, tag)
        self.markdown_text.config(state="disabled")
        self.framework_summary_var.set(f"{len(self.ideas)} 条历史想法 · {len(self.components)} 个树干 · 当前自动关联阈值 {self.threshold:.2f}")

    def draw_visual(self) -> None:
        canvas = self.visual_canvas
        canvas.delete("all")
        self.visual_nodes = {idea.id: idea for idea in self.ideas}
        canvas.create_rectangle(28, 24, 272, 76, fill=COLORS["ink"], outline="")
        canvas.create_text(150, 44, text="想法逻辑框架", fill="#ffffff", font=("Microsoft YaHei UI", 14, "bold"))
        canvas.create_text(150, 63, text=f"{len(self.ideas)} 条想法 · {len(self.components)} 个主题", fill="#dce7fa", font=("Microsoft YaHei UI", 9))
        y = 110
        min_width = 1030
        for index, component in enumerate(self.components):
            color, soft = NODE_COLORS[index % len(NODE_COLORS)]
            name = topic_name(component, self.names)
            top = y
            node_height = 66
            idea_height = max(72, 42 * len(component))
            total_height = max(node_height, idea_height + 24)
            canvas.create_line(272, 50, 330, top + total_height / 2, fill=COLORS["line"], width=2)
            tag = f"topic:{component_key(component)}"
            canvas.create_rectangle(330, top, 575, top + total_height, fill=soft, outline=color, width=2, tags=(tag, "clickable"))
            canvas.create_text(350, top + 20, text=f"主题 {index + 1}", anchor="w", fill=color, font=("Microsoft YaHei UI", 9, "bold"), tags=(tag, "clickable"))
            canvas.create_text(350, top + 42, text=self._short(name, 22), anchor="w", fill=COLORS["ink"], font=("Microsoft YaHei UI", 12, "bold"), tags=(tag, "clickable"))
            keywords = "、".join(self._component_keywords(component)[:4]) or "独立想法"
            canvas.create_text(350, top + 62, text=self._short(keywords, 34), anchor="w", fill=COLORS["muted"], font=("Microsoft YaHei UI", 9), tags=(tag, "clickable"))
            idea_y = top + 12
            for idea in component:
                idea_tag = f"idea:{idea.id}"
                canvas.create_line(575, top + total_height / 2, 625, idea_y + 22, fill=COLORS["line"], width=2, tags=(idea_tag, "clickable"))
                canvas.create_rectangle(625, idea_y, 1010, idea_y + 48, fill="#ffffff", outline=COLORS["line"], width=1, tags=(idea_tag, "clickable"))
                canvas.create_text(640, idea_y + 16, text=self._short(idea.title, 34), anchor="w", fill=COLORS["ink"], font=("Microsoft YaHei UI", 10, "bold"), tags=(idea_tag, "clickable"))
                canvas.create_text(640, idea_y + 34, text=self._short(idea.preview(60), 58), anchor="w", fill=COLORS["muted"], font=("Microsoft YaHei UI", 9), tags=(idea_tag, "clickable"))
                idea_y += 60
            y += total_height + 34
        canvas.tag_bind("clickable", "<Button-1>", self.on_visual_click)
        canvas.config(scrollregion=(0, 0, min_width, max(380, y + 20)))

    def _component_keywords(self, component: list[Idea]) -> list[str]:
        from idea_framework import component_keywords
        return component_keywords(component)

    def on_visual_click(self, event: object) -> None:
        current = self.visual_canvas.find_withtag("current")
        if not current:
            return
        tags = self.visual_canvas.gettags(current[0])
        for tag in tags:
            if tag.startswith("idea:"):
                item_id = tag.split(":", 1)[1]
                self.selected_idea_id = item_id
                self.show_idea_detail(item_id)
                self.select_history_item(item_id)
                return
            if tag.startswith("topic:"):
                key = tag.split(":", 1)[1]
                component = next((group for group in self.components if component_key(group) == key), [])
                if component:
                    self.current_topic_key = key
                    self.visual_detail_var.set(f"主题：{topic_name(component, self.names)}｜{len(component)} 条想法｜关键词：{'、'.join(self._component_keywords(component)[:8])}")
                    self.tabs.select(3)
                    self.select_topic_item(key)
                return

    def _short(self, text: str, length: int) -> str:
        text = clean_text(text)
        return text if len(text) <= length else f"{text[:length - 1]}…"

    def refresh_history(self) -> None:
        query = clean_text(self.search_var.get())
        candidates = matching_ideas(self.ideas, query) if query else [(idea, 0.0) for idea in reversed(self.ideas)]
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        pins = self.pinned_ids
        for idea, _score in candidates:
            if self.pinned_only_var.get() == "1" and idea.id not in pins:
                continue
            timestamp = idea.created_at.replace("T", " ")[:16]
            self.history_tree.insert("", END, iid=idea.id, values=("★" if idea.id in pins else "", timestamp, topic_for_idea(idea.id, self.components, self.names), idea.title, "、".join(idea.tags)))

    def on_history_select(self, _event: object = None) -> None:
        selected = self.history_tree.selection()
        if selected:
            self.selected_idea_id = selected[0]
            self.show_idea_detail(selected[0])

    def select_history_item(self, item_id: str) -> None:
        if self.history_tree.exists(item_id):
            self.history_tree.selection_set(item_id)
            self.history_tree.focus(item_id)
            self.history_tree.see(item_id)
        self.show_idea_detail(item_id)

    def show_idea_detail(self, item_id: str) -> None:
        idea = next((item for item in self.ideas if item.id == item_id), None)
        if not idea:
            return
        field_text = "\n".join(f"{FIELD_LABELS[field]}：{value}" for field, value in idea.field_items())
        prefix = f"{idea.title}\n主题：{topic_for_idea(idea.id, self.components, self.names)}｜ID：{idea.id}\n"
        self.history_detail_var.set(prefix + field_text)
        self.visual_detail_var.set(prefix + idea.preview(220))

    def refresh_topics(self) -> None:
        for item in self.topic_tree.get_children():
            self.topic_tree.delete(item)
        fixed = set(self.assignments.values())
        for component in self.components:
            key = component_key(component)
            mode = "人工固定" if key in fixed else "自动归类"
            name = topic_name(component, self.names)
            topic_item = self.topic_tree.insert("", END, iid=key, text=name, values=(len(component), mode, "、".join(self._component_keywords(component)[:7])), open=True)
            for idea in sorted(component, key=lambda item: item.created_at):
                suffix = " [收藏]" if idea.id in self.pinned_ids else ""
                self.topic_tree.insert(topic_item, END, iid=f"{key}|{idea.id}", text=idea.title + suffix, values=("", "", idea.preview(80)))

    def on_topic_select(self, _event: object = None) -> None:
        selected = self.topic_tree.selection()
        if not selected:
            return
        item = selected[0].split("|", 1)[0]
        component = next((group for group in self.components if component_key(group) == item), None)
        if component:
            self.current_topic_key = item
            count_fixed = sum(1 for idea in component if self.assignments.get(idea.id) == item)
            self.topic_detail_var.set(f"当前主题：{topic_name(component, self.names)}｜{len(component)} 条想法｜固定 {count_fixed} 条。可重命名、固定、合并或恢复为自动归类。")

    def select_topic_item(self, key: str) -> None:
        if self.topic_tree.exists(key):
            self.topic_tree.selection_set(key)
            self.topic_tree.focus(key)
            self.topic_tree.see(key)

    def selected_topic_key(self) -> str:
        selected = self.topic_tree.selection()
        if selected:
            return selected[0].split("|", 1)[0]
        return self.current_topic_key

    def _selected_component(self) -> list[Idea] | None:
        key = self.selected_topic_key()
        return next((group for group in self.components if component_key(group) == key), None)

    def lock_selected_topic(self) -> None:
        component = self._selected_component()
        if not component:
            messagebox.showinfo("选择主题", "请先在“主题管理”中选择一个主题。", parent=self.root)
            return
        target = component_key(component)
        for idea in component:
            self.assignments[idea.id] = target
        self.save_metadata()
        self.refresh_all()
        self.select_topic_item(target)
        self.status_var.set("主题已固定。后续新增或重建不会打散这组人工确认的想法。")

    def rename_topic(self) -> None:
        component = self._selected_component()
        if not component:
            messagebox.showinfo("选择主题", "请先选择一个主题。", parent=self.root)
            return
        key = component_key(component)
        name = simpledialog.askstring("重命名主题", "主题名称：", initialvalue=topic_name(component, self.names), parent=self.root)
        if name is None:
            return
        name = clean_text(name)
        if not name:
            self.names.pop(key, None)
        else:
            self.names[key] = name
        self.save_metadata()
        self.refresh_all()
        self.select_topic_item(key)

    def create_trunk_from_selected(self) -> None:
        idea = self.get_selected_idea()
        if not idea:
            messagebox.showinfo("选择历史想法", "请先在“历史列表”中选中一条想法。", parent=self.root)
            return
        name = simpledialog.askstring("新建独立树干", "主题名称（可留空自动使用想法标题）：", initialvalue=idea.title, parent=self.root)
        if name is None:
            return
        self.assignments[idea.id] = idea.id
        if clean_text(name):
            self.names[idea.id] = clean_text(name)
        self.save_metadata()
        self.refresh_all()
        self.select_topic_item(idea.id)
        self.status_var.set("已为所选想法建立独立且固定的树干。")

    def move_selected_idea_to_topic(self) -> None:
        idea = self.get_selected_idea()
        component = self._selected_component()
        if not idea or not component:
            messagebox.showinfo("需要两项选择", "先在“历史列表”选中一条想法，再在“主题管理”选择目标主题。", parent=self.root)
            return
        target = component_key(component)
        for member in component:
            self.assignments[member.id] = target
        self.assignments[idea.id] = target
        self.save_metadata()
        self.refresh_all()
        self.select_topic_item(target)
        self.status_var.set(f"已将“{idea.title}”移动至“{topic_name(component, self.names)}”。")

    def merge_selected_topics(self) -> None:
        keys: list[str] = []
        for item in self.topic_tree.selection():
            key = item.split("|", 1)[0]
            if key not in keys:
                keys.append(key)
        if len(keys) < 2:
            messagebox.showinfo("选择主题", "按住 Ctrl 选择至少两个主题；第一个选中的主题将作为合并目标。", parent=self.root)
            return
        target = keys[0]
        target_component = next((group for group in self.components if component_key(group) == target), None)
        if not target_component:
            return
        for key in keys:
            component = next((group for group in self.components if component_key(group) == key), [])
            for idea in component:
                self.assignments[idea.id] = target
            if key != target:
                self.names.pop(key, None)
        self.save_metadata()
        self.refresh_all()
        self.select_topic_item(target)
        self.status_var.set(f"已将 {len(keys)} 个主题合并到“{topic_name(target_component, self.names)}”。")

    def unlock_selected_topic(self) -> None:
        component = self._selected_component()
        if not component:
            messagebox.showinfo("选择主题", "请先选择需要恢复自动归类的主题。", parent=self.root)
            return
        if not messagebox.askyesno("恢复自动归类", "将移除此主题中的人工固定关系，内容会在下一次重建时按关联度重新组织。", parent=self.root):
            return
        key = component_key(component)
        for idea in component:
            self.assignments.pop(idea.id, None)
        self.names.pop(key, None)
        self.save_metadata()
        self.refresh_all()
        self.status_var.set("已恢复自动归类。")

    def get_selected_idea(self) -> Idea | None:
        item_id = self.selected_idea_id
        selection = self.history_tree.selection()
        if selection:
            item_id = selection[0]
        return next((item for item in self.ideas if item.id == item_id), None)

    def toggle_pin(self) -> None:
        idea = self.get_selected_idea()
        if not idea:
            messagebox.showinfo("选择想法", "请先在历史列表中选择一条想法。", parent=self.root)
            return
        pins = self.pinned_ids
        if idea.id in pins:
            pins.remove(idea.id)
            action = "已取消收藏"
        else:
            pins.add(idea.id)
            action = "已收藏"
        self.meta["pinned_ids"] = sorted(pins)
        self.save_metadata()
        self.refresh_history()
        self.refresh_topics()
        self.status_var.set(f"{action}：{idea.title}")

    def delete_selected_idea(self) -> None:
        idea = self.get_selected_idea()
        if not idea:
            messagebox.showinfo("选择想法", "请先选择一条想法。", parent=self.root)
            return
        if not messagebox.askyesno("删除想法", f"确定删除“{idea.title}”？\n删除后会重建框架，但不会影响其他历史记录。", parent=self.root):
            return
        self.ideas = [item for item in self.ideas if item.id != idea.id]
        save_ideas(self.ideas, self.store_path)
        self.meta["pinned_ids"] = [item_id for item_id in self.pinned_ids if item_id != idea.id]
        self.meta["idea_assignments"].pop(idea.id, None)
        for item_id, target in list(self.assignments.items()):
            if target == idea.id:
                self.assignments.pop(item_id, None)
        self.names.pop(idea.id, None)
        self.save_metadata()
        self.selected_idea_id = ""
        self.refresh_all(keep_selection=False)
        self.status_var.set(f"已删除“{idea.title}”。")

    def edit_selected_idea(self) -> None:
        idea = self.get_selected_idea()
        if not idea:
            messagebox.showinfo("选择想法", "请先选择一条想法。", parent=self.root)
            return
        dialog = Toplevel(self.root)
        dialog.title("编辑想法")
        dialog.geometry("680x720")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=16)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="标题", style="Body.TLabel").pack(anchor="w")
        title = ttk.Entry(frame)
        title.insert(0, idea.title)
        title.pack(fill=X, pady=(2, 7))
        ttk.Label(frame, text="标签（逗号分隔）", style="Body.TLabel").pack(anchor="w")
        tags = ttk.Entry(frame)
        tags.insert(0, ", ".join(idea.tags))
        tags.pack(fill=X, pady=(2, 7))
        editors: dict[str, Text] = {}
        for field in FIELD_ORDER:
            ttk.Label(frame, text=FIELD_LABELS[field], style="Body.TLabel").pack(anchor="w")
            widget = Text(frame, height=3 if field != "summary" else 2, wrap="word", relief="solid", borderwidth=1, highlightthickness=0)
            widget.insert("1.0", getattr(idea, field))
            widget.pack(fill=X, pady=(2, 6))
            editors[field] = widget

        def commit() -> None:
            idea.title = clean_text(title.get()) or idea.title
            idea.tags = [item.strip() for item in re.split(r"[,，;；]", tags.get()) if item.strip()]
            for field, widget in editors.items():
                setattr(idea, field, clean_text(widget.get("1.0", END)))
            idea.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
            save_ideas(self.ideas, self.store_path)
            dialog.destroy()
            self.selected_idea_id = idea.id
            self.refresh_all()
            self.status_var.set(f"已更新“{idea.title}”，并重建主题关联。")

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(8, 0))
        ttk.Button(buttons, text="保存修改并重建", style="Success.TButton", command=commit).pack(side=LEFT)
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side=LEFT, padx=8)

    def export_markdown(self) -> None:
        self._write_framework()
        self.status_var.set(f"Markdown 已更新：{self.output_path.name}")
        messagebox.showinfo("已导出", f"已生成 Markdown 框架：\n{self.output_path}", parent=self.root)

    def export_mermaid(self) -> None:
        destination = self.output_path.with_name("framework_visual.mmd")
        destination.write_text(mermaid_source(self.ideas, self.threshold, self.names, self.assignments), encoding="utf-8")
        self.status_var.set(f"Mermaid 思维图已导出：{destination.name}")
        messagebox.showinfo("已导出", f"已生成 Mermaid 文件：\n{destination}", parent=self.root)

    def export_html(self) -> None:
        destination = self.output_path.with_name("framework_visual.html")
        destination.write_text(html_visual_export(self.ideas, self.threshold, self.names, self.assignments), encoding="utf-8")
        self.status_var.set(f"交互网页已导出：{destination.name}")
        messagebox.showinfo("已导出", f"已生成可在浏览器打开的图像框架：\n{destination}", parent=self.root)

    def open_markdown(self) -> None:
        self._write_framework()
        try:
            os.startfile(self.output_path)  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror("无法打开", str(error), parent=self.root)

    def backup_data(self) -> None:
        destination = self.store_path.with_name(f"ideas_backup_{datetime.now():%Y%m%d_%H%M%S}.json")
        destination.write_text(json.dumps([idea.to_record() for idea in self.ideas], ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set(f"已创建数据备份：{destination.name}")
        messagebox.showinfo("备份完成", f"备份已保存至：\n{destination}", parent=self.root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="想法逻辑框架图形界面")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except OSError:
                pass
    args = build_parser().parse_args(argv)
    root = Tk()
    IdeaFrameworkApp(root, args.store, args.output, args.meta)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
