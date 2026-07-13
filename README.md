# 想法与创新点逻辑框架

一个只依赖 Python 标准库的本地工具。每次写入想法后，它都会重新读取全部历史记录，检索关联内容并生成：

- 可追溯的 Markdown 逻辑框架；
- 可点击查看节点的图像化框架；
- 可人工修正的主题树干。

## 启动

在本目录打开 PowerShell 后执行：

```powershell
python .\idea_framework.py ui
```

也可以直接运行：

```powershell
python .\idea_framework.py
```

后者进入快速命令行输入；输入 `:ui` 可立即转到图形界面。

## 建议使用流程

1. 在“快速输入”中记录突发想法，或在“结构化输入”中分别填写创新点、应用场景、验证方法和风险。
2. 点击“写入并重建框架”。左下角会显示它和历史想法的关联结果。
3. 在“图像化框架”中点击主题或想法节点，快速确认关系与来源。
4. 在“主题管理”中固定已确认的主题；把历史列表中的记录移动到目标主题，或用一条记录新建独立树干。
5. 在“历史列表”中检索、编辑、收藏或删除记录。编辑和删除都会重新生成全部框架。

## 生成的本地文件

- `ideas.jsonl`：原始想法数据，每行一条记录。
- `framework.md`：完整文字逻辑框架。
- `idea_framework_meta.json`：人工重命名、固定主题和收藏状态；不改写原始想法内容。
- `framework_visual.mmd`：可导入 Mermaid 的思维图。
- `framework_visual.html`：可以直接用浏览器打开的简约图像化框架。

## 关联阈值

界面上方的“关联阈值”控制自动归类的严格程度：数值低时更容易归为同一主题，数值高时更保守。默认 `0.18` 适合从零开始记录的中文想法库；对已经有明确标签的记录，可以调高到 `0.22` 或 `0.28`。

## 命令行备用方式

```powershell
python .\idea_framework.py add --summary "根据分数与专业意向生成高考志愿组合" --innovation "按冲稳保风险分层" --tags "高考,志愿,教育"
python .\idea_framework.py search 志愿
python .\idea_framework.py framework
python .\idea_framework.py list
```
