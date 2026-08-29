# IB DP 平台 — 扩展功能清单 & 数据(JSON)样例

> **状态：仅方案 + 样例，未实现、未出题。** 供你审阅后确认要落地的功能与字段。
> 当前已具备：题目检索/筛选、在线练习(判对错+计分)、批量导入(CLI+网页)、导出错题本(自动收纳)、进度统计。
> 本文在现有能力之上，补齐你提到的「收藏」「题目↔知识点/课本关联」等扩展，并给出对应的 JSON 样例。

---

## 1. 建议新增的功能（按优先级）

### ★ 核心（你明确提到）
| # | 功能 | 说明 | 数据变化 |
|---|------|------|----------|
| F1 | **收藏夹 Favorites** | 任意题目一键收藏(★)，独立「Favorites」筛选/页面，导航角标显示数量。纯本地、按用户。 | 新表 `favorites(question_id, added_at)` |
| F2 | **知识点库 Knowledge Points** | 以官方考纲子主题为节点的「知识点」库（如 `A1.1 Computer hardware and operation`）。每个知识点带**描述 + 课本页码 + 公式表页码**引用。可直接从你提供的三科 Guide 播种。 | 新表 `knowledge_points(...)` |
| F3 | **题目 ↔ 知识点 双向关联** | 每道题关联 1..n 个 `knowledge_point_id`；题目卡片显示知识点 chip，点 chip 跳到知识点详情(含阅读指引)；知识点详情列出全部关联题目。实现「题目链接到对应知识点」。 | `questions` 加列 `knowledge_point_ids TEXT(JSON)` |

### ★ 高价值（强烈建议本轮一起做）
| # | 功能 | 说明 | 数据变化 |
|---|------|------|----------|
| F4 | **课本 / 公式表 页码引用** | 在知识点（或题目）上挂载结构化引用数组：`{type:"textbook"|"formula"|"guide", label, chapter, pages, note}`。实现「题目链接到课本」。点击直接看到「读 MacKenty 2025 第 X 页」「查公式表 p.Y」。 | 落在 `knowledge_points.references` |
| F5 | **自定义题集 Collections** | 在「收藏(二元)」之外，把题目归入命名题集（如「2025 模拟 Paper1」「薄弱点集训」），支持导出/练习整集。 | 新表 `collections(id,name)` + `collection_items(collection_id,question_id)` |
| F6 | **按主题/知识点的进度分析** | 现有进度按「题」统计；扩展为按 `topic` / `knowledge_point` 拆解正确率，直观看到哪些考纲区块最弱。 | 查询层扩展（复用 `progress`+`questions`） |

### ○ 可选（后续迭代）
| # | 功能 | 说明 |
|---|------|------|
| F7 | 错题本间隔复习(Spaced repetition) | 依据 `times_wrong`/`last_wrong_at` 排复习计划。 |
| F8 | 题目级笔记/批注 | 现有 `note` 只在错题本；推广为任意题目可写 note。 |
| F9 | 按知识点生成测验 | 练习模式支持「从选定知识点随机抽 N 题」。 |

---

## 2. 数据模型变更（汇总）

```sql
-- F2 知识点库（考纲子主题节点）
CREATE TABLE knowledge_points (
  id          TEXT PRIMARY KEY,   -- 如 "CS-A1.1"
  subject     TEXT NOT NULL,      -- CS / Math / Physics
  code        TEXT,               -- "A1.1"
  theme       TEXT,               -- "A: Concepts of computer science"
  title       TEXT NOT NULL,      -- "Computer hardware and operation"
  description TEXT,               -- 知识点简述
  references  TEXT                -- JSON 数组: 课本/公式表/考纲页码
);

-- F1 收藏夹（用户态，本地）
CREATE TABLE favorites (
  question_id TEXT PRIMARY KEY,
  added_at    TEXT
);

-- F3 题目关联知识点（在 questions 表加一列，向后兼容）
ALTER TABLE questions ADD COLUMN knowledge_point_ids TEXT; -- JSON 数组, 如 ["CS-A1.1","CS-A1.2"]

-- F5 自定义题集
CREATE TABLE collections (
  id    TEXT PRIMARY KEY,
  name  TEXT NOT NULL
);
CREATE TABLE collection_items (
  collection_id TEXT,
  question_id   TEXT,
  PRIMARY KEY (collection_id, question_id)
);
```

> 说明：收藏(F1)、题集(F5) 是**用户态数据**，不入「题目导入 JSON」；只有 F3 的 `knowledge_point_ids` 是**内容级字段**，随题目一起导入。

---

## 3. JSON 样例

### 3.1 知识点库 `knowledge_points`（播种自 IB CS Guide 2025）
> 这棵树即你的「按主题分类」骨架。课本页码为占位，待抽取 MacKenty 2025 目录后补全。

```json
{
  "knowledge_points": [
    { "id": "CS-A1.1", "subject": "CS", "code": "A1.1",
      "theme": "A: Concepts of computer science",
      "title": "Computer hardware and operation",
      "description": "CPU, memory, storage, buses, and how a computer executes instructions.",
      "references": [
        { "type": "textbook", "label": "MacKenty & Stephenson (Oxford 2025)", "chapter": 2, "pages": "40-58" },
        { "type": "guide", "label": "CS Guide 2025", "pages": "35" }
      ] },
    { "id": "CS-A1.2", "subject": "CS", "code": "A1.2",
      "theme": "A: Concepts of computer science",
      "title": "Data representation and computer logic",
      "description": "Number systems, character sets, bit operations, logic gates.",
      "references": [
        { "type": "textbook", "label": "MacKenty & Stephenson (Oxford 2025)", "chapter": 3, "pages": "60-82" }
      ] },
    { "id": "CS-A1.3", "subject": "CS", "code": "A1.3",
      "theme": "A: Concepts of computer science",
      "title": "Operating systems and control systems",
      "description": "OS roles, scheduling, interrupts, real-time control.",
      "references": [ { "type": "textbook", "label": "MacKenty & Stephenson (Oxford 2025)", "chapter": 4, "pages": "84-104" } ] },
    { "id": "CS-A1.4", "subject": "CS", "code": "A1.4", "theme": "A: Concepts of computer science",
      "title": "Translation (HL only)", "description": "Assemblers, compilers, interpreters, linkers.",
      "references": [ { "type": "textbook", "label": "MacKenty & Stephenson (Oxford 2025)", "chapter": 5, "pages": "106-120" } ] },

    { "id": "CS-A2.1", "subject": "CS", "code": "A2.1", "theme": "A: Concepts of computer science",
      "title": "Network fundamentals", "description": "Topologies, protocols, IP addressing, DNS.",
      "references": [ { "type": "textbook", "label": "MacKenty & Stephenson (Oxford 2025)", "chapter": 6, "pages": "122-140" } ] },
    { "id": "CS-A2.2", "subject": "CS", "code": "A2.2", "theme": "A: Concepts of computer science",
      "title": "Network architecture", "description": "OSI/TCP-IP models, layering.", "references": [] },
    { "id": "CS-A2.3", "subject": "CS", "code": "A2.3", "theme": "A: Concepts of computer science",
      "title": "Data transmissions", "description": "Serial/parallel, simplex/duplex, error detection.", "references": [] },
    { "id": "CS-A2.4", "subject": "CS", "code": "A2.4", "theme": "A: Concepts of computer science",
      "title": "Network security", "description": "Encryption, firewalls, attacks, mitigation.", "references": [] },

    { "id": "CS-A3.1", "subject": "CS", "code": "A3.1", "theme": "A: Concepts of computer science",
      "title": "Database fundamentals", "description": "Entities, attributes, relationships, keys.", "references": [] },
    { "id": "CS-A3.2", "subject": "CS", "code": "A3.2", "theme": "A: Concepts of computer science",
      "title": "Database design", "description": "ER modelling, normalization to 3NF.", "references": [] },
    { "id": "CS-A3.3", "subject": "CS", "code": "A3.3", "theme": "A: Concepts of computer science",
      "title": "Database programming (HL only)", "description": "SQL DML/DDL, joins.", "references": [] },
    { "id": "CS-A3.4", "subject": "CS", "code": "A3.4", "theme": "A: Concepts of computer science",
      "title": "Alternative databases and data warehouses (HL only)", "description": "NoSQL, distributed stores.", "references": [] },

    { "id": "CS-A4.1", "subject": "CS", "code": "A4.1", "theme": "A: Concepts of computer science",
      "title": "Machine learning fundamentals", "description": "Supervised/unsupervised, training/test.", "references": [] },
    { "id": "CS-A4.2", "subject": "CS", "code": "A4.2", "theme": "A: Concepts of computer science",
      "title": "Data preprocessing (HL only)", "description": "Cleaning, normalization, feature scaling.", "references": [] },
    { "id": "CS-A4.3", "subject": "CS", "code": "A4.3", "theme": "A: Concepts of computer science",
      "title": "Machine learning approaches (HL only)", "description": "Regression, classification, clustering.", "references": [] },
    { "id": "CS-A4.4", "subject": "CS", "code": "A4.4", "theme": "A: Concepts of computer science",
      "title": "Ethical considerations", "description": "Bias, privacy, accountability in ML.", "references": [] },

    { "id": "CS-B1.1", "subject": "CS", "code": "B1.1", "theme": "B: Computational thinking and problem-solving",
      "title": "Approaches to computational thinking", "description": "Abstraction, decomposition, pattern recognition.", "references": [] },
    { "id": "CS-B2.1", "subject": "CS", "code": "B2.1", "theme": "B: Computational thinking and problem-solving",
      "title": "Programming fundamentals", "description": "Variables, types, I/O, operators.", "references": [] },
    { "id": "CS-B2.2", "subject": "CS", "code": "B2.2", "theme": "B: Computational thinking and problem-solving",
      "title": "Data structures", "description": "Arrays, lists, stacks, queues, trees, graphs.", "references": [] },
    { "id": "CS-B2.3", "subject": "CS", "code": "B2.3", "theme": "B: Computational thinking and problem-solving",
      "title": "Programming constructs", "description": "Selection, iteration, recursion.", "references": [] },
    { "id": "CS-B2.4", "subject": "CS", "code": "B2.4", "theme": "B: Computational thinking and problem-solving",
      "title": "Programming algorithms", "description": "Searching, sorting, complexity.", "references": [] },
    { "id": "CS-B2.5", "subject": "CS", "code": "B2.5", "theme": "B: Computational thinking and problem-solving",
      "title": "File processing", "description": "Read/write, record handling.", "references": [] },
    { "id": "CS-B3.1", "subject": "CS", "code": "B3.1", "theme": "B: Computational thinking and problem-solving",
      "title": "Fundamentals of OOP for a single class", "description": "Classes, objects, methods, attributes.", "references": [] },
    { "id": "CS-B3.2", "subject": "CS", "code": "B3.2", "theme": "B: Computational thinking and problem-solving",
      "title": "Fundamentals of OOP for multiple classes", "description": "Inheritance, composition, polymorphism.", "references": [] },
    { "id": "CS-B4.1", "subject": "CS", "code": "B4.1", "theme": "B: Computational thinking and problem-solving",
      "title": "Fundamentals of ADTs (HL only)", "description": "Stacks, queues, lists, trees as ADTs.", "references": [] }
  ]
}
```

### 3.2 扩展后的题目导入 JSON（新增 `knowledge_point_ids`）
> 在现有字段上**仅增加可选字段 `knowledge_point_ids`**，其余不变；旧导入文件继续兼容。

```json
{
  "questions": [
    {
      "id": "cs-a1-1-001",
      "subject": "CS",
      "level": "HL",
      "topic": "Computer fundamentals",
      "subtopic": "Computer hardware and operation",
      "paper_type": "Paper 1",
      "command_term": "Outline",
      "marks": 4,
      "difficulty": 2,
      "question": "Outline the role of the control unit and the ALU within the CPU.",
      "figure": "",
      "answer": "The control unit fetches/decodes/executes instructions and coordinates components; the ALU performs arithmetic and logic operations.",
      "explanation": "The CPU partitions control (CU) and computation (ALU); understanding this separation is core to A1.1.",
      "source": "original (IB-style, modelled on CS Guide 2025 A1.1)",
      "tags": ["CPU", "hardware", "HL"],
      "knowledge_point_ids": ["CS-A1.1"]
    },
    {
      "id": "cs-a2-3-001",
      "subject": "CS",
      "level": "HL",
      "topic": "Networks",
      "subtopic": "Data transmissions",
      "paper_type": "Paper 1",
      "command_term": "Explain",
      "marks": 6,
      "difficulty": 3,
      "question": "Explain the difference between serial and parallel data transmission, and give one advantage of each.",
      "figure": "",
      "answer": "Serial sends bits one after another over a single channel (cheaper, fewer crosstalk errors over distance); parallel sends multiple bits simultaneously (faster short-distance, e.g. internal buses) but risks skew.",
      "explanation": "A2.3 contrasts transmission modes; mention cost, distance, and timing skew.",
      "source": "original (IB-style, modelled on CS Guide 2025 A2.3)",
      "tags": ["transmission", "serial", "parallel"],
      "knowledge_point_ids": ["CS-A2.3"]
    }
  ]
}
```

### 3.3 收藏夹 `favorites`（用户态，API 形态，非导入）
```json
{ "question_id": "cs-a1-1-001", "added_at": "2026-08-20T09:30:25Z" }
```

### 3.4 自定义题集 `collections`（用户态）
```json
{
  "id": "col-mock-p1-2025",
  "name": "Mock Paper 1 (2025-style)",
  "question_ids": ["cs-a1-1-001", "cs-a2-3-001"]
}
```

### 3.5 错题本 `wrong_notebook`（已实现，列出供完整参考）
```json
{
  "question_id": "cs-a1-1-001",
  "added_at": "2026-08-20T10:01:00Z",
  "last_wrong_at": "2026-08-20T10:01:00Z",
  "times_wrong": 1,
  "mastered": 0,
  "note": "Confused CU vs ALU — re-read MacKenty p.42."
}
```

---

## 4. 与「按主题分类」「链接课本」的对应

- **按主题分类** → 由 `knowledge_points` 的 `code/theme/title` 提供官方考纲骨架（上表 23 个 CS 节点），题目通过 `knowledge_point_ids` 挂接；筛选/进度均可按此聚合。
- **链接课本/公式表** → 每个知识点带 `references`（textbook chapter/page、guide page、formula page）。Math 可用 `公示表.pdf`、Physics 可用 `物理DataBooklet2025.pdf`、CS 用 MacKenty 2025 页码（待抽取目录补全）。
- **双向导航** → 题目卡片 chip → 知识点详情(阅读指引)；知识点详情 → 关联题目列表。

---

## 5. 待你确认

请圈定本轮要落地的功能（建议至少 F1–F3，最好带上 F4 课本引用）：
- [ ] F1 收藏夹
- [ ] F2 知识点库
- [ ] F3 题目↔知识点关联
- [ ] F4 课本/公式表页码引用
- [ ] F5 自定义题集
- [ ] F6 按主题进度分析
- [ ] （后续）F7–F9

确认后我再：① 改 `db.js`/`questionRepo.js`/`api.js` 落地表与字段；② 抽三科 Guide 目录补全 `references` 页码；③ 开始按 `knowledge_points` 编写 CS 原创题并导入。
