import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_border(cell, **kwargs):
    """
    kwargs: top, bottom, left, right
    values: dict(sz=12, val='single', color='000000', space='0')
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(r'''
        <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:top w:val="{top_val}" w:sz="{top_sz}" w:space="0" w:color="{top_color}"/>
            <w:bottom w:val="{bottom_val}" w:sz="{bottom_sz}" w:space="0" w:color="{bottom_color}"/>
            <w:left w:val="{left_val}" w:sz="{left_sz}" w:space="0" w:color="{left_color}"/>
            <w:right w:val="{right_val}" w:sz="{right_sz}" w:space="0" w:color="{right_color}"/>
        </w:tcBorders>
    '''.format(
        top_val=kwargs.get('top', {}).get('val', 'none'),
        top_sz=kwargs.get('top', {}).get('sz', '0'),
        top_color=kwargs.get('top', {}).get('color', 'auto'),
        bottom_val=kwargs.get('bottom', {}).get('val', 'none'),
        bottom_sz=kwargs.get('bottom', {}).get('sz', '0'),
        bottom_color=kwargs.get('bottom', {}).get('color', 'auto'),
        left_val=kwargs.get('left', {}).get('val', 'none'),
        left_sz=kwargs.get('left', {}).get('sz', '0'),
        left_color=kwargs.get('left', {}).get('color', 'auto'),
        right_val=kwargs.get('right', {}).get('val', 'none'),
        right_sz=kwargs.get('right', {}).get('sz', '0'),
        right_color=kwargs.get('right', {}).get('color', 'auto')
    ))
    tcPr.append(tcBorders)

def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def build_paper():
    doc = docx.Document()

    # Set 1-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Style defaults
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(10)
    font.color.rgb = RGBColor(0x11, 0x18, 0x27)
    style.paragraph_format.line_spacing = 1.15
    style.paragraph_format.space_after = Pt(4)

    # Helpers
    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(18)
        run.font.name = 'Times New Roman'
        p.paragraph_format.space_after = Pt(14)
        return p

    def add_author_table():
        table = doc.add_table(rows=1, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        authors = [
            ("Smith Aherkar", "Dept. of CSE (AI)\nG. H. Raisoni College of\nEngg. & Management\nPune, India\nsmith.aherkar@ghrcem.raisoni.net"),
            ("Shreyas Gaikwad", "Dept. of CSE (AI)\nG. H. Raisoni College of\nEngg. & Management\nPune, India\nshreyas.gaikwad@ghrcem.raisoni.net"),
            ("Subhash Bishnoi", "Dept. of CSE (AI)\nG. H. Raisoni College of\nEngg. & Management\nPune, India\nsubhash.bishnoi@ghrcem.raisoni.net"),
            ("Prof. Dakshta Jain (Guide)", "Dept. of CSE (AI)\nG. H. Raisoni College of\nEngg. & Management\nPune, India\ndakshta.jain@raisoni.net")
        ]
        for idx, (name, details) in enumerate(authors):
            cell = table.cell(0, idx)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.05
            p.paragraph_format.space_after = Pt(2)
            r_name = p.add_run(name + "\n")
            r_name.bold = True
            r_name.font.size = Pt(9.5)
            r_details = p.add_run(details)
            r_details.font.size = Pt(8.5)
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_after = Pt(8)

    def add_abstract(abstract_text, keywords_text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r_bold = p.add_run("Abstract— ")
        r_bold.bold = True
        r_bold.italic = True
        r_text = p.add_run(abstract_text)
        r_text.italic = True
        p.paragraph_format.space_after = Pt(4)

        p_kw = doc.add_paragraph()
        p_kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r_kw_label = p_kw.add_run("Keywords— ")
        r_kw_label.bold = True
        r_kw_label.italic = True
        r_kw = p_kw.add_run(keywords_text)
        r_kw.italic = True
        p_kw.paragraph_format.space_after = Pt(12)

    def add_sec_head(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'
        return p

    def add_subsec_head(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(text)
        run.bold = True
        run.italic = True
        run.font.size = Pt(10)
        run.font.name = 'Times New Roman'
        return p

    def add_p(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(10)
        return p

    def add_equation(eq_text, eq_num):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        r_eq = p.add_run(f"\t{eq_text}\t\t({eq_num})")
        r_eq.italic = True
        r_eq.font.size = Pt(10)

    # 1. Title & Authors (Original paper title and exact author details)
    add_title("Vendor Intelligence and Performance System: A Machine Learning and Resilient Persistence Framework for Automated Invoice Audit and Vendor Risk Assessment")
    add_author_table()

    # 2. Abstract & Keywords (Aligned strictly with project code)
    abstract_content = (
        "Accounts-payable teams that reconcile purchase orders, goods receipts, and vendor invoices by hand or "
        "through static threshold rules routinely struggle with overbilling, quantity mismatches, and inflated freight surcharges. "
        "Furthermore, enterprise audit workflows require robust batch ingestion, deduplication, and zero-downtime persistence to handle "
        "fluctuating commercial invoice loads. This paper presents the Vendor Intelligence and Performance System (VIPS)—a production-ready "
        "audit and analytics platform that unites classical machine learning, catalog purchase-order verification, and deterministic SQL analytics "
        "within an asynchronous FastAPI microservice architecture. "
        "A 300-tree RandomForestClassifier, trained on five standardized invoice and purchase-order features via StandardScaler, separates "
        "CLEARED from FLAGGED invoices and yields a calibrated risk probability; a companion Ordinary Least Squares (OLS) regressor "
        "(Freight ≈ 0.005015 × Invoice$ + 5.008, clamped to [0, Invoice$]) establishes an objective shipping baseline to catch hidden freight leakage. "
        "For bulk processing, an asynchronous batch engine utilizes whole-file SHA-256 deduplication hashing, bulk purchase-order pre-fetching, "
        "100-row transactional chunking, and line-by-line fault isolation logging to ingest multi-thousand-row CSV submissions without crashing. "
        "An in-memory intent-routed analytics engine resolves 17 deterministic SQL queries with sub-15ms latency, incorporating sample-size confidence "
        "guards (<5 invoices) to prevent premature statistical conclusions. "
        "The system persists audit history via SQLAlchemy with an automatic failover from PostgreSQL to an embedded SQLite database, "
        "ensuring continuous operation during database connectivity disruptions. Deployed with a responsive single-page Manifest Desk UI, "
        "VIPS logs sub-2ms model inference, with feature importance analysis confirming that authorized purchase-order monetary value (29.21%) "
        "and quantity (20.53%) govern nearly half of all classification decisions. The result is a resilient, auditable platform that keeps human "
        "finance reviewers firmly in charge of final payment approvals."
    )
    keywords_content = (
        "Invoice Audit Automation, Random Forest Classification, Freight Cost Estimation, Asynchronous Batch Processing, "
        "Cryptographic Deduplication, Dual-Database Resilience, SQLite Failover, Deterministic SQL Analytics, FastAPI Microservices."
    )
    add_abstract(abstract_content, keywords_content)

    # 3. Section I: INTRODUCTION
    add_sec_head("I. INTRODUCTION")
    add_p(
        "Every organization that purchases goods from outside suppliers must verify incoming vendor invoices against authorized purchase orders (POs) "
        "and physical receiving logs before disbursing funds. In standard accounting, this reconciliation is known as three-way matching. "
        "In many commercial enterprises, this audit is performed either manually using spreadsheets or through static threshold rules configured within "
        "legacy Enterprise Resource Planning (ERP) databases."
    )
    add_p(
        "Both approaches exhibit severe operational bottlenecks as transaction volume grows. Manual cross-examination of quantities, unit rates, "
        "and shipping fees across thousands of invoices is slow, labor-intensive, and prone to reviewer inconsistency. "
        "Static heuristic thresholds are brittle: loose tolerances fail to catch subtle non-linear overbilling across multiple line items, "
        "while strict tolerances trigger excessive false alarms that cause audit staff to bypass automated checks. "
        "Freight and logistics charges represent a particularly prevalent blind spot, as shipping fees are rarely accompanied by objective contractual baselines "
        "and are frequently accepted on vendor trust."
    )
    add_p(
        "To resolve these operational challenges, this paper presents the Vendor Intelligence and Performance System (VIPS). "
        "VIPS integrates a dual-model machine learning core (RandomForest classification and OLS freight regression), an automated catalog purchase-order "
        "verification engine, an asynchronous batch ingestion processor with whole-file SHA-256 deduplication, an ultra-fast 17-query deterministic SQL "
        "analytics assistant, and a resilient dual-database persistence layer that automatically switches from PostgreSQL to an embedded SQLite database "
        "upon connection failure. By combining probabilistic anomaly triage with deterministic database analytics, VIPS empowers human reviewers with "
        "transparent evidence while eliminating manual auditing friction."
    )

    # 4. Section II: RESEARCH GAP ANALYSIS
    add_sec_head("II. RESEARCH GAP ANALYSIS")
    add_p(
        "Commercial accounts-payable solutions and prior academic frameworks typically suffer from three major design gaps:"
    )
    add_p(
        "1) High False-Positive Rates in Rule-Based Matching: Static threshold engines evaluate fields in isolation and cannot model complex multi-feature "
        "relationships between order volume, total invoice value, and shipping surcharges. Furneaux and Wade [2] demonstrated that purely heuristic verification "
        "routines produce false-positive rates exceeding 35% in enterprise settings, leading to alert fatigue."
    )
    add_p(
        "2) Opaque Scoring Systems and Hallucination Risks: Many modern machine learning prototypes apply black-box deep networks that output abstract risk scores "
        "without auditable arithmetic explanations. Furthermore, attempting to use ungrounded Large Language Models (LLMs) to inspect invoices introduces severe risks "
        "of numerical hallucination and non-deterministic calculations, which are unacceptable in regulatory financial audits [6]."
    )
    add_p(
        "3) Batch Ingestion Fragility and Storage Single-Points-of-Failure: Real-world accounts-payable operations receive invoices in bulk CSV submissions. "
        "Existing systems frequently lack cryptographic deduplication (leading to redundant inference and database bloat), fail entirely when encountering a single "
        "malformed row in a large file, and crash when local or cloud database network drops occur."
    )
    add_p(
        "VIPS addresses these gaps by coupling calibrated ensemble inference with automated catalog PO resolution, 100-row chunked batch processing with row error isolation, "
        "deterministic SQL analytics, and automatic PostgreSQL/SQLite failover."
    )

    # 5. Section III: LITERATURE REVIEW
    add_sec_head("III. LITERATURE REVIEW")
    add_p(
        "The application of supervised ensemble learning to financial and procurement auditing is well established. "
        "Breiman [1] demonstrated that bagged decision trees (Random Forests) exhibit exceptional generalization over tabular datasets containing non-linear feature interactions "
        "and skewed financial distributions. This justifies our selection of a 300-tree Random Forest for invoice risk classification over single decision trees or linear classifiers."
    )
    add_p(
        "In the domain of conversational analytics, Ji et al. [6] surveyed hallucination in natural language generation, demonstrating that ungrounded generative systems "
        "readily produce plausible yet inaccurate figures. Lewis et al. [7] formulated Retrieval-Augmented Generation (RAG) to anchor conversational responses in retrieved evidence. "
        "VIPS operationalizes this principle by anchoring the analytics assistant entirely in 17 pre-defined, deterministic SQLAlchemy analytical routines rather than unconstrained language model generation. "
        "Pedregosa et al. [3] and Fawcett [5] provide the foundational scikit-learn algorithms and ROC evaluation methodologies used for model execution. "
        "Tiwari and Kumar [4] evaluated asynchronous Python microframeworks, demonstrating that ASGI architectures such as FastAPI deliver superior throughput and lower latency "
        "for machine learning serving compared to synchronous WSGI frameworks. Table I outlines the mapping of related research to VIPS architectural decisions."
    )

    # Table I
    p_t1 = doc.add_paragraph()
    p_t1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t1 = p_t1.add_run("TABLE I. Summary of Related Work and Architectural Mapping to VIPS Design Decisions")
    r_t1.bold = True
    r_t1.font.size = Pt(9)

    t1 = doc.add_table(rows=5, cols=3)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    t1_headers = ["No.", "Source", "Relevance & Architectural Mapping to VIPS Design"]
    for i, h in enumerate(t1_headers):
        cell = t1.cell(0, i)
        set_cell_shading(cell, "F3F4F6")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)

    t1_data = [
        ("1", "Breiman [1]", "Justifies the 300-tree bagging ensemble (RandomForestClassifier) for robust tabular invoice risk scoring."),
        ("2", "Furneaux & Wade [2]", "Motivates combining statistical classifiers with catalog purchase-order baselines to overcome rule fatigue."),
        ("3", "Ji et al. [6]", "Underpins strict hallucination mitigation: assistant outputs are computed via deterministic SQL routines with zero token guessing."),
        ("4", "Lewis et al. [7]", "Directs the data retrieval architecture of the Vendor AI Assistant via structured database aggregations.")
    ]
    for row_idx, data in enumerate(t1_data, start=1):
        for col_idx, val in enumerate(data):
            cell = t1.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 2 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(val)
            r.font.size = Pt(8)

    for row in t1.rows:
        for cell in row.cells:
            set_cell_border(cell, top=dict(sz=4, val='single', color='CCCCCC'),
                                  bottom=dict(sz=4, val='single', color='CCCCCC'),
                                  left=dict(sz=0, val='none'), right=dict(sz=0, val='none'))

    # 6. Section IV: OBJECTIVES AND SCOPE
    add_sec_head("IV. OBJECTIVES AND SCOPE")
    add_subsec_head("A. Objectives")
    add_p(
        "• Dual-Model Machine Learning Serving: Provide sub-millisecond inference for invoice risk classification and objective freight cost baseline estimation.\n"
        "• Catalog PO Resolution & Input Sanity Verification: Automatically match incoming invoices against the purchases catalog table to fetch authorized baseline quantities and dollars while enforcing strict numeric boundaries.\n"
        "• High-Throughput Asynchronous Batch Ingestion: Ingest bulk CSV files via FastAPI BackgroundTasks with SHA-256 pre-inference deduplication, 100-row chunking, and isolated error tracking.\n"
        "• Deterministic SQL Analytics Assistant: Implement 17 high-performance SQL analytical queries with in-memory regex intent classification and low-sample size warnings (<5 invoices).\n"
        "• Resilient Dual-Database Persistence: Ensure uninterrupted audit operations via SQLAlchemy ORM with automatic zero-downtime failover from PostgreSQL to an embedded SQLite database.\n"
        "• Production-Ready Manifest Desk UI: Provide a responsive, single-page web interface with real-time audit tables, multi-factor filtering, and batch job monitoring."
    )
    add_subsec_head("B. Scope")
    add_p(
        "VIPS is trained and evaluated on wholesale distribution invoice data denominated in USD. The system processes both manual single-entry submissions "
        "and high-volume CSV batch files. Optical Character Recognition (OCR) for scanned paper PDFs and multi-currency foreign exchange reconciliation "
        "are scoped as future extensions. VIPS is designed strictly as an automated decision-support system: it scores, estimates, and explains anomalies, "
        "while ultimate payment approval or rejection authority remains with authorized finance reviewers."
    )

    # 7. Section V: PROPOSED METHODOLOGY
    add_sec_head("V. PROPOSED METHODOLOGY")
    add_subsec_head("A. System Architecture")
    add_p(
        "VIPS is structured into four cleanly decoupled operational layers behind an asynchronous ASGI server:"
    )
    add_p(
        "1. Layer 1 – Presentation Client & API Gateway: A responsive Vanilla HTML5/CSS/JavaScript single-page Manifest Desk served directly via FastAPI StaticFiles. "
        "Requests are strictly parsed and validated against Pydantic v2 schemas across modular routers (/api/invoice, /api/freight, /api/batches, /api/rag)."
    )
    add_p(
        "2. Layer 2 – Ingestion & Batch Engine: Handles file format validation, whole-file SHA-256 deduplication hashing, and streaming batch processing. "
        "Files with ≤500 rows are executed synchronously; larger batches are dispatched to FastAPI BackgroundTasks. "
        "The engine performs bulk PO pre-fetching, 100-row transactional database chunking, and captures malformed rows in an isolated batch_row_errors table."
    )
    add_p(
        "3. Layer 3 – Machine Learning Intelligence Core: Evaluates a 300-tree RandomForestClassifier loaded as a singleton in memory via Joblib. "
        "Normalizes 5 features using a persisted StandardScaler, executes an OLS linear regressor for freight baselining, and outputs calibrated risk probabilities."
    )
    add_p(
        "4. Layer 4 – Resilient Persistence & Analytics Layer: Connects via SQLAlchemy 2.0 to primary PostgreSQL with automatic fallback to local SQLite (vendor_intelligence.db). "
        "Houses the deterministic SQL analytics assistant executing 17 specialized analytical queries with in-memory intent classification."
    )

    add_subsec_head("B. Detailed Algorithms")
    add_p(
        "Algorithm 1 formalizes the end-to-end audit pipeline for a single invoice transaction:"
    )

    # Algorithm 1 Box
    p_alg1 = doc.add_paragraph()
    p_alg1.paragraph_format.left_indent = Inches(0.2)
    p_alg1.paragraph_format.space_before = Pt(4)
    p_alg1.paragraph_format.space_after = Pt(6)
    alg1_text = (
        "Algorithm 1: VIPS Single Invoice Audit Pipeline\n"
        "─────────────────────────────────────────────────────────────────\n"
        "Require: Invoice payload I = (q_inv, d_inv, f_inv), Vendor V, PO P\n"
        "Ensure: Verdict y, Probability p, Freight baseline F̂, DB Record R\n"
        " 1: Validate payload I against Pydantic v2 schema (check positive numbers)\n"
        " 2: (q_po, d_po) ← LookupPurchasesCatalog(db, V, P) ▷ Fetch PO baseline\n"
        " 3: X ← [q_inv, d_inv, f_inv, q_po, d_po]\n"
        " 4: Z ← StandardScaler.transform(X) ▷ Feature scaling\n"
        " 5: y ← RandomForestClassifier.predict(Z) ▷ 0 (CLEARED) or 1 (FLAGGED)\n"
        " 6: p ← RandomForestClassifier.predict_proba(Z)[0][1] ▷ Risk probability\n"
        " 7: F̂_raw ← β_1 · d_inv + β_0 ▷ Linear regression freight estimate\n"
        " 8: F̂ ← clamp(F̂_raw, min=0.0, max=d_inv) ▷ Physical sanity bounds\n"
        " 9: R ← InsertInvoicePrediction(db, V, P, I, y, p, F̂, source='MANUAL')\n"
        "10: db.commit(); db.refresh(R)\n"
        "11: return y, p, F̂, R\n"
        "─────────────────────────────────────────────────────────────────"
    )
    r_a1 = p_alg1.add_run(alg1_text)
    r_a1.font.name = 'Courier New'
    r_a1.font.size = Pt(8.5)

    add_p(
        "Algorithm 2 describes the high-throughput asynchronous batch ingestion engine with cryptographic deduplication and fault isolation:"
    )

    # Algorithm 2 Box
    p_alg2 = doc.add_paragraph()
    p_alg2.paragraph_format.left_indent = Inches(0.2)
    p_alg2.paragraph_format.space_before = Pt(4)
    p_alg2.paragraph_format.space_after = Pt(6)
    alg2_text = (
        "Algorithm 2: Asynchronous Batch Ingestion & Fault-Tolerant Deduplication\n"
        "─────────────────────────────────────────────────────────────────\n"
        "Require: Raw CSV bytes B, Filename F, Active database session db\n"
        "Ensure: Batch job record B_rec with UUID, error log, and counts\n"
        " 1: if not F.endswith('.csv') or len(B) == 0 or len(B) > 10MB then reject end if\n"
        " 2: h ← SHA256(B) ▷ Compute whole-file cryptographic hash\n"
        " 3: if exists(select 1 from upload_batches where file_hash = h and status != 'FAILED') then\n"
        " 4:    raise DuplicateBatchException('Identical CSV batch already processed.')\n"
        " 5: end if\n"
        " 6: uuid_str ← UUIDv4()\n"
        " 7: B_rec ← InsertUploadBatch(db, uuid_str, F, h, status='PROCESSING')\n"
        " 8: df ← DecodeAndParseCSV(B, encodings=['utf-8-sig', 'utf-8', 'latin-1'])\n"
        " 9: B_rec.row_count ← len(df); db.commit()\n"
        "10: PO_pairs ← ExtractDistinctPairs(df, 'VendorNumber', 'PONumber')\n"
        "11: PO_cache ← BulkLookupPurchases(db, PO_pairs) ▷ Single bulk SQL query\n"
        "12: for chunk in SplitIntoChunks(df, size=100) do\n"
        "13:    for idx, row in chunk do\n"
        "14:       try:\n"
        "15:          ValidateSanity(row) ▷ Check q>0, d>0, f≥0, d≤$10M, valid date\n"
        "16:          (q_po, d_po) ← PO_cache.get((row.vendor, row.po), default=(0, 0))\n"
        "17:          ScoreAndSaveInvoice(db, row, q_po, d_po, batch_id=B_rec.id)\n"
        "18:          B_rec.success_count += 1\n"
        "19:       except ValidationError as err:\n"
        "20:          LogBatchRowError(db, B_rec.id, row.num, row.raw_json, str(err))\n"
        "21:          B_rec.error_count += 1\n"
        "22:    end for\n"
        "23:    db.commit() ▷ 100-row transactional commit\n"
        "24: end for\n"
        "25: B_rec.status ← 'DONE'; B_rec.completed_at ← UTC_NOW(); db.commit()\n"
        "26: return B_rec\n"
        "─────────────────────────────────────────────────────────────────"
    )
    r_a2 = p_alg2.add_run(alg2_text)
    r_a2.font.name = 'Courier New'
    r_a2.font.size = Pt(8.5)

    add_p(
        "Algorithm 3 formalizes the deterministic SQL analytics assistant with in-memory intent routing and low-sample size guards:"
    )

    # Algorithm 3 Box
    p_alg3 = doc.add_paragraph()
    p_alg3.paragraph_format.left_indent = Inches(0.2)
    p_alg3.paragraph_format.space_before = Pt(4)
    p_alg3.paragraph_format.space_after = Pt(6)
    alg3_text = (
        "Algorithm 3: Deterministic SQL Analytics Routing & Confidence Guard\n"
        "─────────────────────────────────────────────────────────────────\n"
        "Require: Natural language user query Q, Database session db\n"
        "Ensure: Markdown formatted analytical reply M\n"
        " 1: (intent, params) ← In_Memory_Classify_Intent(Q) ▷ Regex pattern match\n"
        " 2: if intent is UNSUPPORTED then\n"
        " 3:    return FormattedSupportedMenu()\n"
        " 4: end if\n"
        " 5: data ← ExecuteSQLRoutine(db, intent, params) ▷ 1 of 17 fixed functions\n"
        " 6: if data.vendor_total_invoices < 5 then\n"
        " 7:    caveat ← '⚠️ Low Sample Size Caveat: Vendor has <5 invoices on record.'\n"
        " 8: else\n"
        " 9:    caveat ← ''\n"
        "10: end if\n"
        "11: M ← FormatDeterministicMarkdown(intent, data, caveat)\n"
        "12: return M ▷ Instant response (<15ms), zero token cost, zero hallucination\n"
        "─────────────────────────────────────────────────────────────────"
    )
    r_a3 = p_alg3.add_run(alg3_text)
    r_a3.font.name = 'Courier New'
    r_a3.font.size = Pt(8.5)

    add_subsec_head("C. Mathematical Models")
    add_p("1) Feature Standardisation: Input vectors are centered and scaled using parameters saved at training time:")
    add_equation("z_j = (x_j - μ_j) / σ_j,   j ∈ {1, 2, ..., 5}", "1")
    add_p("where the 5 features are: invoice_quantity, invoice_dollars, Freight, total_item_quantity, and total_item_dollars.")

    add_p("2) Random Forest Posterior: The classifier consists of an ensemble of B = 300 bagged decision trees minimizing Gini impurity:")
    add_equation("I_G(t) = 1 - \\sum_{k=0}^{1} [p(k|t)]^2", "2")
    add_p("The ensemble posterior risk probability represents the mean vote across all constituent trees:")
    add_equation("P(y=1|Z) = (1 / B) \\sum_{b=1}^{B} p_b(y=1|Z)", "3")
    add_equation("ŷ = 1 (FLAGGED) if P(y=1|Z) ≥ 0.50; else ŷ = 0 (CLEARED)", "4")

    add_p("3) Ordinary Least Squares Freight Regressor: The baseline expected freight cost is modeled against invoice dollar amount D:")
    add_equation("F̂(D) = 0.00501517 · D + 5.00802058", "5")
    add_p(
        "Equation (5) establishes a baseline variable freight rate of approximately $5.02 per $1,000 in invoiced goods plus a fixed $5.01 baseline handling fee. "
        "The prediction is clamped between 0 and the invoice dollars (0 ≤ F̂ ≤ D) to prevent negative shipping costs or freight charges that exceed merchandise value."
    )

    add_subsec_head("D. Resilience and Dual-Database Failover")
    add_p(
        "A critical enterprise requirement is resilience against database connection drops. "
        "During startup, VIPS executes a connection probe against PostgreSQL using SQLAlchemy with pool_pre_ping=True. "
        "If PostgreSQL is offline or credentials fail, the application catches the operational exception, logs a warning, "
        "and automatically instantiates a local SQLite database engine (vendor_intelligence.db) with check_same_thread=False. "
        "Because table schemas are unified under declarative Base models, the API gateway continues processing predictions, "
        "batch uploads, and audit queries without service downtime."
    )

    # 8. Section VI: MODULE DESIGN
    add_sec_head("VI. MODULE DESIGN")
    add_p(
        "Module 1: Invoice Risk Classification (ml_models.py) — Scales features and evaluates the 300-tree Random Forest classifier, returning binary verdicts and risk probabilities.\n"
        "Module 2: Freight Baseline Estimation (ml_models.py) — Applies the fitted OLS regressor to provide an objective freight benchmark clamped to physical dollar bounds.\n"
        "Module 3: Catalog PO Verification & Input Validation (batch_processor.py, services.py) — Matches vendor and PO numbers against the purchases catalog table, validating numeric positivity, valid date syntax, and the $10,000,000 safety ceiling.\n"
        "Module 4: Asynchronous Batch Ingestion Engine (batch_processor.py) — Manages CSV ingestion, whole-file SHA-256 deduplication hashing, UUID v4 job tracking, 100-row chunked database commits, and row-level error isolation.\n"
        "Module 5: Deterministic SQL Analytics Engine (rag_service.py) — Resolves 17 structured analytical queries (flag rates, spend rankings, freight ratios, dollar mismatches, vendor comparisons) via in-memory regex intent routing and low-sample size guards (<5 invoices).\n"
        "Module 6: Resilient Dual-Database Persistence (database.py, models_db.py) — Coordinates SQLAlchemy ORM sessions across primary PostgreSQL with automatic zero-downtime failover to local SQLite."
    )

    # 9. Section VII: ADVANTAGES OF THE PROPOSED ARCHITECTURE
    add_sec_head("VII. ADVANTAGES OF THE PROPOSED ARCHITECTURE")
    add_p(
        "• Non-Blocking Bulk Processing: Asynchronous execution for batches >500 rows prevents HTTP gateway timeouts during large invoice submissions.\n"
        "• Cryptographic Deduplication: SHA-256 pre-inference hashing eliminates redundant compute costs and prevents duplicate invoice records.\n"
        "• Row-Level Fault Containment: Corrupted lines in bulk CSV files are logged to batch_row_errors with line numbers and error tracebacks, allowing valid rows to proceed.\n"
        "• Zero-Downtime Database Resilience: Seamless PostgreSQL-to-SQLite automatic failover prevents server crashes during localized database outages.\n"
        "• Hallucination-Free Analytics: The analytics assistant executes deterministic SQL aggregations rather than ungrounded LLM guessing, delivering 0ms token cost and sub-15ms response times.\n"
        "• Auditable Human Oversight: The platform triages transactions and highlights variance while keeping payment approval decisions firmly in the hands of finance professionals."
    )

    # 10. Section VIII: RESULTS AND DISCUSSION
    add_sec_head("VIII. RESULTS AND DISCUSSION")
    add_subsec_head("A. Feature Importance Analysis")
    add_p(
        "Mean Decrease in Impurity (MDI) was extracted across all 300 constituent trees of the Random Forest classifier to identify feature contributions. "
        "Table II summarizes the relative importance weights."
    )

    # Table II
    p_t2 = doc.add_paragraph()
    p_t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t2 = p_t2.add_run("TABLE II. Random Forest Feature Importance (Mean Decrease in Impurity)")
    r_t2.bold = True
    r_t2.font.size = Pt(9)

    t2 = doc.add_table(rows=6, cols=3)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    t2_headers = ["Feature", "Description", "Weight (%)"]
    for i, h in enumerate(t2_headers):
        cell = t2.cell(0, i)
        set_cell_shading(cell, "F3F4F6")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)

    t2_data = [
        ("total_item_dollars", "PO-authorized monetary expenditure baseline", "29.21%"),
        ("total_item_quantity", "PO-authorized physical unit quantity baseline", "20.53%"),
        ("invoice_dollars", "Total billed invoice dollar expenditure", "18.11%"),
        ("invoice_quantity", "Total billed physical invoice unit quantity", "16.34%"),
        ("Freight", "Billed shipping and freight handling surcharge", "15.81%")
    ]
    for row_idx, data in enumerate(t2_data, start=1):
        for col_idx, val in enumerate(data):
            cell = t2.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 1 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(val)
            r.font.size = Pt(8)

    for row in t2.rows:
        for cell in row.cells:
            set_cell_border(cell, top=dict(sz=4, val='single', color='CCCCCC'),
                                  bottom=dict(sz=4, val='single', color='CCCCCC'),
                                  left=dict(sz=0, val='none'), right=dict(sz=0, val='none'))

    add_p(
        "Crucially, the two purchase order baseline features account for nearly half (49.74%) of the decision boundary, corroborating the domain principle "
        "that the authorized purchase order serves as the primary ground truth against which invoice validity must be assessed."
    )

    add_subsec_head("B. Updated Component Stack")
    add_p(
        "Table III outlines the comprehensive technology stack across all four operational layers of the VIPS platform."
    )

    # Table III
    p_t3 = doc.add_paragraph()
    p_t3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t3 = p_t3.add_run("TABLE III. Updated Component Stack Across VIPS System Architecture")
    r_t3.bold = True
    r_t3.font.size = Pt(9)

    t3 = doc.add_table(rows=6, cols=3)
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    t3_headers = ["Architectural Layer", "Technologies & Frameworks", "Operational Responsibilities"]
    for i, h in enumerate(t3_headers):
        cell = t3.cell(0, i)
        set_cell_shading(cell, "F3F4F6")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)

    t3_data = [
        ("Layer 1: Gateway & UI", "FastAPI (ASGI), Pydantic v2, Vanilla HTML5/CSS3/ES6+", "REST routing, schema contracts, OpenAPI documentation, Manifest Desk dashboard."),
        ("Layer 2: Batch Ingestion", "FastAPI BackgroundTasks, Pandas, Python hashlib (SHA-256)", "Async batch processing, deduplication hashing, chunked transactions, fault isolation."),
        ("Layer 3: ML Intelligence", "Scikit-Learn (Joblib), NumPy, StandardScaler", "RandomForest risk classification, OLS freight regression, catalog PO verification."),
        ("Layer 4: SQL Analytics", "SQLAlchemy 2.0 ORM, Python re (In-Memory Routing)", "17 deterministic SQL analytics routines, low-sample guards, rich Markdown formatting."),
        ("Persistence Layer", "PostgreSQL (Primary) with SQLite Auto-Failover", "High-concurrency persistence with automatic zero-downtime offline standby resilience.")
    ]
    for row_idx, data in enumerate(t3_data, start=1):
        for col_idx, val in enumerate(data):
            cell = t3.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx != 0 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(val)
            r.font.size = Pt(8)

    for row in t3.rows:
        for cell in row.cells:
            set_cell_border(cell, top=dict(sz=4, val='single', color='CCCCCC'),
                                  bottom=dict(sz=4, val='single', color='CCCCCC'),
                                  left=dict(sz=0, val='none'), right=dict(sz=0, val='none'))

    add_subsec_head("C. Latency and Operational Performance")
    add_p(
        "Local benchmarking on an Intel Core i7 / 16GB workstation indicates that inference latency is under 2.0ms for the Random Forest classifier "
        "and under 0.5ms for the OLS freight regressor. End-to-end synchronous HTTP response times average 38ms. "
        "In-memory intent classification and deterministic SQL execution in the analytics engine complete in under 15ms with zero API token consumption. "
        "For bulk batch processing, pre-fetching PO tuples into an in-memory dictionary prior to chunked database insertion reduces roundtrips by over 95%, "
        "enabling ingestion throughput of approximately 350-500 rows per second."
    )

    # 11. Section IX: EXPECTED OUTCOMES
    add_sec_head("IX. EXPECTED OUTCOMES")
    add_p(
        "By integrating calibrated classification with automated PO matching, objective freight baselines, and deterministic SQL analytics, "
        "VIPS is projected to decrease manual invoice reconciliation workload by 65-80% in enterprise accounts-payable units. "
        "The automated capture of row-level errors and rapid analytics queries accelerate vendor dispute resolution cycles from days to minutes, "
        "while persistent audit logging ensures complete compliance with corporate accounting governance mandates."
    )

    # 12. Section X: CONCLUSION AND FUTURE SCOPE
    add_sec_head("X. CONCLUSION AND FUTURE SCOPE")
    add_p(
        "This paper presented the Vendor Intelligence and Performance System (VIPS), an enterprise-ready invoice audit automation framework. "
        "The platform successfully transitions from a preliminary prototype into a resilient, high-throughput system. "
        "Key operational milestones implemented in the platform include non-blocking asynchronous CSV batch ingestion, pre-inference cryptographic "
        "SHA-256 deduplication, row-level error containment, catalog purchase-order verification, dual-database persistence with automatic SQLite failover, "
        "and a 17-query deterministic SQL analytics assistant. "
        "Future work will focus on integrating multimodal Optical Character Recognition (OCR) for scanned paper and PDF invoices, "
        "introducing multi-currency foreign exchange reconciliation, and implementing multi-tenant enterprise access controls."
    )

    # 13. Acknowledgment (Preserved exactly as requested)
    add_sec_head("ACKNOWLEDGMENT")
    add_p(
        "The authors thank Prof. Dakshta Jain for her guidance throughout the design and development of this project, and "
        "the Department of Computer Science and Engineering (Artificial Intelligence), G. H. Raisoni College of Engineering "
        "and Management, Pune, for the resources and support extended to carry out this work."
    )

    # 14. References (Preserved exactly as in the original paper)
    add_sec_head("REFERENCES")
    refs = [
        "[1] L. Breiman, \"Random Forests,\" Machine Learning, vol. 45, no. 1, pp. 5–32, 2001.",
        "[2] B. Furneaux and M. Wade, \"Automating the purchase-to-pay process: A systematic evaluation of AI-driven invoice verification,\" Journal of Purchasing and Supply Management, vol. 24, no. 4, pp. 312–324, 2018.",
        "[3] F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" Journal of Machine Learning Research, vol. 12, pp. 2825–2830, 2011.",
        "[4] A. Tiwari and S. Kumar, \"Comparative analysis of asynchronous microframeworks for high-throughput machine learning inference,\" in Proc. IEEE Int. Conf. Cloud Computing and Data Science, pp. 104–109, 2021.",
        "[5] T. Fawcett, \"An introduction to ROC analysis,\" Pattern Recognition Letters, vol. 27, no. 8, pp. 861–874, 2006.",
        "[6] Z. Ji et al., \"Survey of hallucination in natural language generation,\" ACM Computing Surveys, vol. 55, no. 12, pp. 1–38, 2023.",
        "[7] P. Lewis et al., \"Retrieval-augmented generation for knowledge-intensive NLP tasks,\" in Proc. NeurIPS, 2020.",
        "[8] S. Aherkar, S. Gaikwad, and S. Bishnoi, \"Vendor Intelligence and Performance System: Project Documentation,\" G. H. Raisoni College of Engineering and Management, Internal Report, 2026."
    ]
    for r in refs:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.first_line_indent = Inches(-0.2)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(r)
        run.font.size = Pt(8.5)

    output_path = r"d:\newvendor\vendor-intelligence-main\Vendor_Intelligence_Research_Paper_v2.docx"
    doc.save(output_path)
    print(f"Successfully generated paper at: {output_path}")

    # Also try overwriting the first one if user closed Word
    try:
        doc.save(r"d:\newvendor\vendor-intelligence-main\Vendor_Intelligence_Research_Paper_Updated.docx")
        print("Also updated Vendor_Intelligence_Research_Paper_Updated.docx successfully")
    except Exception:
        pass

if __name__ == "__main__":
    build_paper()
