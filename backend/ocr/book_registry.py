"""book_registry — verified per-book extraction configs (see extract_v3).

Patterns are matched against BOTH the space-stripped normalised heading and the
raw heading, because several PDFs insert stray spaces inside words.
"""
import os

ROOT = "/Users/lucas.ma/Downloads/dp learning"


def _c(**kw):
    kw.setdefault("scale", 1.8)
    kw.setdefault("head_ratio", 1.10)
    kw.setdefault("qnum_max", 200)
    kw.setdefault("qnum_min", 1)
    kw.setdefault("first_max", 3)
    kw.setdefault("min_sec_qs", 3)
    kw["path"] = os.path.join(ROOT, kw["rel"])
    return kw


BOOKS = [
    # ---------------- MATHEMATICS — TEXTBOOKS ----------------
    _c(id="MA-HAESE-CORE1", rel="HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - Haese 2019.pdf",
       subject="Mathematics", level="HL", title="Mathematics: Core Topics HL 1 (Haese)",
       publisher="Haese & Harris", edition="2019", tag="haese-core1", start_page=14,
       practice=r"exercise\d|reviewset\d",
       stop=r"example|investigation|activity|selftutor|discussion|summary|\(chapter|contents"),
    _c(id="MA-HAESE-AA2", rel="HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf",
       subject="Mathematics", level="HL", title="Mathematics: Analysis and Approaches HL 2 (Haese)",
       publisher="Haese & Harris", edition="2019", tag="haese-aa2", start_page=14,
       practice=r"exercise\d|reviewset\d",
       stop=r"example|investigation|activity|selftutor|discussion|summary|\(chapter|contents"),
    _c(id="MA-OXFORD-2019", rel="HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf",
       subject="Mathematics", level="HL", title="Mathematics: Analysis and Approaches HL (Oxford)",
       publisher="Oxford University Press", edition="2019", tag="oxford-aa", start_page=22,
       practice=r"exercise\d|chapterreview|practicequestions|reviewset\d",
       stop=r"example\d|investigation|activity|summary|discussion|contents"),
    _c(id="MA-HODDER-2019", rel="Mathematics - Analysis and Approaches HL - Hodder 2019.pdf",
       subject="Mathematics", level="HL", title="Mathematics for the IB Diploma: AA HL (Hodder)",
       publisher="Hodder Education", edition="2019", tag="hodder-aa", start_page=16,
       practice=r"^\d{1,2}[A-Z]",
       stop=r"workedexample|example\d|activity|investigation|summary|contents"),
    _c(id="MA-CAMBRIDGE-2012", rel="CAMBRIDGE/Mathematics HL - Fannon, Kadelburg, Woolley and Ward - Cambridge 2012.pdf",
       subject="Mathematics", level="HL", title="Mathematics for the IB Diploma HL (Cambridge)",
       publisher="Cambridge University Press", edition="2012", tag="cambridge-hl", start_page=18,
       practice=r"xerc",
       stop=r"workedexample|example\d|activity|investigation|summary|contents"),
    _c(id="MA-IBID-2017", rel="IBID/Mathematics HL Core - Buckle, Cirrito, Dunbar, Henry, Hung and McAuliffe - Fifth Edition - IBID 2017.pdf",
       subject="Mathematics", level="HL", title="Mathematics HL Core (IBID, 5th ed)",
       publisher="IBID Press", edition="2017", tag="ibid-2017", start_page=16,
       practice=r"exercise\d",
       stop=r"example\d|^chapter|activity|investigation|summary|contents"),
    _c(id="MA-IBID-2004", rel="IBID/Mathematics Higher Level (CORE) - Fabio Cirrito - Third Edition - IBID 2004.pdf",
       subject="Mathematics", level="HL", title="Mathematics Higher Level Core (IBID, 3rd ed)",
       publisher="IBID Press", edition="2004", tag="ibid-2004", start_page=24,
       practice=r"xercises?\d?$",
       stop=r"example\d|chapter\d|summary|contents"),
    # ---------------- MATHEMATICS — WORKBOOKS / PRACTICE ----------------
    _c(id="MA-HODDER-WB", rel="HL Workbook/Mathematics - Analysis and Approaches HL - Exam Practice Workbook - Hodder 2021.pdf",
       subject="Mathematics", level="HL", title="AA HL Exam Practice Workbook (Hodder)",
       publisher="Hodder Education", edition="2021", tag="hodder-wb", start_page=8,
       practice=r"^\d{1,2}(numberandalgebra|functions|geometry|trigonometry|statistics|probability|calculus|syllabusrevision)",
       stop=r"^(?!$)$", head_ratio=1.15, first_max=200, qnum_max=200),
    _c(id="MA-HAESE-REV", rel="HAESE Workbook/Mathematics - Analysis and Approaches HL 2 - REVISION GUIDE - Haese 2020.pdf",
       subject="Mathematics", level="HL", title="AA HL 2 Revision Guide (Haese)",
       publisher="Haese & Harris", edition="2020", tag="haese-rev", start_page=16,
       practice=r"^topic\d|mixedquestionsset|skillbuilder",
       stop=r"^(?!$)$", head_ratio=1.2, first_max=400, qnum_max=400),
    _c(id="MA-CAMB-EXAMPREP", rel="CAMBRIDGE/Mathematics HL - Exam Preparation Guide - Fannon, Kadelburg, Woolley and Ward - Cambridge 2015.pdf",
       subject="Mathematics", level="HL", title="Mathematics HL Exam Preparation Guide (Cambridge)",
       publisher="Cambridge University Press", edition="2015", tag="cambridge-examprep", start_page=10,
       practice=r"practicequestions|mixedpractice",
       stop=r"workedexample|example\d|answers|contents"),
    # ---------------- PHYSICS ----------------
    _c(id="PH-TSOKOS-CB", rel="Physics Coursebook- K.A. Tsokos - Seventh Edition - Cambridge （epub转化版）.pdf",
       subject="Physics", level="HL", title="Physics for the IB Diploma Coursebook (Tsokos, 7th ed)",
       publisher="Cambridge University Press", edition="2023", tag="tsokos-cb", start_page=18,
       practice=r"testyourunderstanding|exam-stylequestions|guidingquestions",
       stop=r"workedexample|example\d|investigation|activity|summary"),
    _c(id="PH-OXFORD-CB", rel="Physics-HLSL-Oxford Textbook(First exam 2025)/Physics - Course Companion - Homer, Piętka and Heathcote - Fifth Edition - Oxford 2023.pdf",
       subject="Physics", level="HL", title="Physics Course Companion (Oxford, 5th ed)",
       publisher="Oxford University Press", edition="2023", tag="oxford-phys", start_page=18,
       head_ratio=0.99,
       practice=r"practicequestions|data-basedquestions|dataquestions",
       stop=r"workedexample|example\d|activity|investigation"),
    _c(id="PH-CAMBRIDGE-WB", rel="Physics-HLSL-Cambridge-Workbook(First exam 2025)/CAMBRIDGE Physics for the IB Diploma WORKBOOK - Seventh Edition - Cambridge 2023 (Digital Edition).pdf",
       subject="Physics", level="HL", title="Physics for the IB Diploma Workbook (Cambridge)",
       publisher="Cambridge University Press", edition="2023", tag="cambridge-phys-wb", start_page=14,
       practice=r"xerc",
       stop=r"chapteroutline|summary|tip"),
    _c(id="PH-TSOKOS-WB", rel="Physics-HLSL-Cambridge-Workbook(First exam 2025)/Physics - WORKBOOK - K.A. Tsokos - Seventh Edition - Cambridge 2023（扫描版）.pdf",
       subject="Physics", level="HL", title="Physics Workbook (Tsokos, 7th ed)",
       publisher="Cambridge University Press", edition="2023", tag="tsokos-wb", start_page=14,
       practice=r"exam-stylequestions|multiplechoicequestions",
       stop=r"^(?!$)$", head_ratio=1.05),
    # ---------------- COMPUTER SCIENCE ----------------
    _c(id="CS-OXFORD-2025", rel="Computer Science - MacKenty and Stephenson - Oxford 2025.pdf",
       subject="Computer Science", level="HL", title="Computer Science for the IB Diploma (Oxford)",
       publisher="Oxford University Press", edition="2025", tag="oxford-cs", start_page=22,
       practice=r"practicequestions|end-of-topicquestions|linkingquestions|topicreview",
       stop=r"workedexample|example\d|activity|summary"),
    # ---------------- MATHEMATICS — OPTIONS (Cambridge 2012) ----------------
    _c(id="MA-CAMB-OPT7", rel="CAMBRIDGE/Mathematics HL - OPTION 7 Statistics and Probability - Fannon, Kadelburg, Woolley and Ward - Cambridge 2012.pdf",
       subject="Mathematics", level="HL", title="Math HL Option 7: Statistics and Probability (Cambridge)",
       publisher="Cambridge University Press", edition="2012", tag="cambridge-opt7", start_page=10,
       practice=r"xerc", stop=r"workedexample|example\d|summary|contents"),
    _c(id="MA-CAMB-OPT8", rel="CAMBRIDGE/Mathematics HL - OPTION 8 Sets, Relations and Groups - Fannon, Kadelburg, Woolley and Ward - Cambridge 2012.pdf",
       subject="Mathematics", level="HL", title="Math HL Option 8: Sets, Relations and Groups (Cambridge)",
       publisher="Cambridge University Press", edition="2012", tag="cambridge-opt8", start_page=10,
       practice=r"xerc", stop=r"workedexample|example\d|summary|contents"),
    _c(id="MA-CAMB-OPT9", rel="CAMBRIDGE/Mathematics HL - OPTION 9 Calculus - Fannon, Kadelburg, Woolley and Ward - Cambridge 2012.pdf",
       subject="Mathematics", level="HL", title="Math HL Option 9: Calculus (Cambridge)",
       publisher="Cambridge University Press", edition="2012", tag="cambridge-opt9", start_page=10,
       practice=r"xerc", stop=r"workedexample|example\d|summary|contents"),
    _c(id="MA-CAMB-OPT10", rel="CAMBRIDGE/Mathematics HL - OPTION 10 Discrete Mathematics - Fannon, Kadelburg, Woolley and Ward - Cambridge 2012.pdf",
       subject="Mathematics", level="HL", title="Math HL Option 10: Discrete Mathematics (Cambridge)",
       publisher="Cambridge University Press", edition="2012", tag="cambridge-opt10", start_page=10,
       practice=r"xerc", stop=r"workedexample|example\d|summary|contents"),
]

# image-only book — needs OCR before extraction (deferred)
DEFERRED = {
    "MA-PEARSON-2019": "Mathematics HL - Analysis and Approaches (Pearson 2019).pdf",
}

BY_ID = {b["id"]: b for b in BOOKS}
