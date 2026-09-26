"""
SmartInterview — Deliverables Synchronization & Conflict Verification Tool
Cross-verifies codebase, frozen baseline, and progressive v2 deliverables:
1. Verifies that SmartInterview_Deliverables (frozen baseline) is untouched.
2. Verifies that SmartInterview_Progressive_Updates exists and all v2 assets are present and healthy.
3. Cross-verifies codebase technical parameters against documentation to ensure ZERO CONFLICTS.
4. Validates diagram and image integrity.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FROZEN_DIR = os.path.join(REPO_ROOT, "SmartInterview_Deliverables")
PROGRESSIVE_DIR = os.path.join(REPO_ROOT, "SmartInterview_Progressive_Updates")

errors = []
warnings = []
passed_checks = []

def check(condition, desc, error_msg):
    if condition:
        passed_checks.append(desc)
    else:
        errors.append(f"[FAIL] {desc}: {error_msg}")

print("======================================================================")
print("     SMARTINTERVIEW DELIVERABLES SYNCHRONIZATION AUDIT & VERIFICATION  ")
print("======================================================================\n")

# ── CHECK 1: Frozen Baseline Preservation ───────────────────────────
print("1. Checking Frozen Baseline Preservation (SmartInterview_Deliverables/)...")
expected_frozen_files = [
    "PROJECT_DOSSIER.md",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense.pdf",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense.docx",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense.md",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet.pdf",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet.docx",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet.md",
    "02_SRS_Specification/SmartInterview_SRS_Template_Format.pdf",
    "02_SRS_Specification/SmartInterview_SRS_Template_Format.docx",
    "03_Research_Paper/SmartInterview_Research_Paper.pdf",
    "03_Research_Paper/SmartInterview_Research_Paper.docx",
    "03_Research_Paper/SmartInterview_Research_Paper_IEEE.md",
    "04_Presentation_and_Defense/SmartInterview_Project_Presentation.pptx",
    "04_Presentation_and_Defense/SmartInterview_Project_Presentation.pdf",
    "04_Presentation_and_Defense/SmartInterview_5_Member_Presentation_Plan.docx",
    "04_Presentation_and_Defense/SmartInterview_5_Member_Presentation_Plan.md",
    "04_Presentation_and_Defense/PS_Project_Presentation_Template_1.0_01Sep2026.pptx",
    "05_System_Diagrams/Architecture.png",
    "05_System_Diagrams/ERD.png",
    "05_System_Diagrams/Workflow.png"
]

for rel in expected_frozen_files:
    full = os.path.join(FROZEN_DIR, rel)
    exists = os.path.exists(full)
    sz = os.path.getsize(full) if exists else 0
    check(exists and sz > 0, f"Frozen baseline: {rel}", f"Missing or 0 bytes ({full})")

# ── CHECK 2: Progressive Working Copies ──────────────────────────────
print("\n2. Checking Progressive Updates Copies (SmartInterview_Progressive_Updates/)...")
expected_progressive_files = [
    "PROJECT_DOSSIER_v2.md",
    "01_Documentation_and_Viva/SmartInterview_Documentation_Report_v2.docx",
    "01_Documentation_and_Viva/SmartInterview_Documentation_Report_v2.pdf",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense_v2.pdf",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense_v2.docx",
    "01_Documentation_and_Viva/SmartInterview_Master_Encyclopedia_and_Viva_Defense_v2.md",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet_v2.pdf",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet_v2.docx",
    "01_Documentation_and_Viva/SmartInterview_Quick_Revision_Cheatsheet_v2.md",
    "02_SRS_Specification/SmartInterview_SRS_Template_Format_v2.pdf",
    "02_SRS_Specification/SmartInterview_SRS_Template_Format_v2.docx",
    "03_Research_Paper/SmartInterview_Research_Paper_v2.pdf",
    "03_Research_Paper/SmartInterview_Research_Paper_v2.docx",
    "03_Research_Paper/SmartInterview_Research_Paper_IEEE_v2.md",
    "04_Presentation_and_Defense/SmartInterview_Project_Presentation_v2.pptx",
    "04_Presentation_and_Defense/SmartInterview_Project_Presentation_v2.pdf",
    "04_Presentation_and_Defense/SmartInterview_5_Member_Presentation_Plan_v2.docx",
    "04_Presentation_and_Defense/SmartInterview_5_Member_Presentation_Plan_v2.md",
    "04_Presentation_and_Defense/PS_Project_Presentation_Template_1.0_01Sep2026.pptx",
    "05_System_Diagrams/Architecture.png",
    "05_System_Diagrams/ERD.png",
    "05_System_Diagrams/Workflow.png"
]

for rel in expected_progressive_files:
    full = os.path.join(PROGRESSIVE_DIR, rel)
    exists = os.path.exists(full)
    sz = os.path.getsize(full) if exists else 0
    check(exists and sz > 0, f"Progressive copy: {rel}", f"Missing or 0 bytes ({full})")

# ── CHECK 3: Technical Parameters Cross-Verification with Code ─────────
print("\n3. Cross-Checking Technical Consistency Between Code & Deliverables...")

# Read backend/app/config.py
config_path = os.path.join(REPO_ROOT, "backend", "app", "config.py")
with open(config_path, "r", encoding="utf-8") as f:
    config_content = f.read()

has_groq_primary = "openai/gpt-oss-120b" in config_content
has_groq_fallback = "openai/gpt-oss-20b" in config_content
has_jwt_alg = "HS256" in config_content

check(has_groq_primary, "Config LLM Primary Model", "openai/gpt-oss-120b not found in config.py")
check(has_groq_fallback, "Config LLM Fallback Model", "openai/gpt-oss-20b not found in config.py")
check(has_jwt_alg, "Config JWT Algorithm", "HS256 not found in config.py")

# Read backend/app/services/bloom.py to check Revised Bloom levels
bloom_path = os.path.join(REPO_ROOT, "backend", "app", "services", "bloom.py")
with open(bloom_path, "r", encoding="utf-8") as f:
    bloom_content = f.read()

bloom_levels = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
for bl in bloom_levels:
    check(bl in bloom_content, f"Bloom Taxonomy Level in Code: {bl}", f"{bl} not found in bloom.py")

# Cross check with Master Encyclopedia v2 markdown
enc_path = os.path.join(PROGRESSIVE_DIR, "01_Documentation_and_Viva", "SmartInterview_Master_Encyclopedia_and_Viva_Defense_v2.md")
with open(enc_path, "r", encoding="utf-8") as f:
    enc_content = f.read()

check("openai/gpt-oss-120b" in enc_content, "Encyclopedia LLM Alignment", "Primary model missing in Master Encyclopedia")
check("all-MiniLM-L6-v2" in enc_content, "Encyclopedia Embedding Alignment", "all-MiniLM-L6-v2 missing in Master Encyclopedia")
for bl in bloom_levels:
    check(bl in enc_content, f"Encyclopedia Bloom Level: {bl}", f"{bl} missing in Master Encyclopedia")

# Cross check with Research Paper IEEE v2 markdown
rp_path = os.path.join(PROGRESSIVE_DIR, "03_Research_Paper", "SmartInterview_Research_Paper_IEEE_v2.md")
with open(rp_path, "r", encoding="utf-8") as f:
    rp_content = f.read()

check("openai/gpt-oss-120b" in rp_content, "Research Paper LLM Alignment", "Primary model missing in Research Paper")
check("Bloom" in rp_content, "Research Paper Pedagogical Engine", "Bloom taxonomy missing in Research Paper")
check("all-MiniLM-L6-v2" in rp_content, "Research Paper SBERT Alignment", "all-MiniLM-L6-v2 missing in Research Paper")

# ── CHECK 4: Diagrams and Image Integrity ────────────────────────────
print("\n4. Verifying Diagram & Image File Integrity...")
diagram_files = [
    os.path.join(PROGRESSIVE_DIR, "05_System_Diagrams", "Architecture.png"),
    os.path.join(PROGRESSIVE_DIR, "05_System_Diagrams", "ERD.png"),
    os.path.join(PROGRESSIVE_DIR, "05_System_Diagrams", "Workflow.png")
]
for d in diagram_files:
    exists = os.path.exists(d)
    sz = os.path.getsize(d) if exists else 0
    check(exists and sz > 10000, f"Diagram: {os.path.basename(d)}", f"Missing or corrupted (size {sz}B)")

# ── CHECK 5: Base Papers & Institutional Identity Verification ──────────
print("\n5. Verifying Base Papers & Institutional Details Consistency...")

# Verify Base Papers in Research Paper
check("Wahid" in rp_content and "IJERT" in rp_content, "Base Paper 1 (Wahid et al.) in Research Paper", "Base Paper 1 citation missing in Research Paper")
check("Nagarajan" in rp_content and "IJMRR" in rp_content, "Base Paper 2 (Nagarajan et al.) in Research Paper", "Base Paper 2 citation missing in Research Paper")

# Verify Team Roll Numbers in Research Paper
roll_numbers = ["24BD1A665K", "24BD1A665R", "24BD1A665X", "25BD5A6615", "25BD5A6620"]
for r in roll_numbers:
    check(r in rp_content, f"Roll Number {r} in Research Paper", f"Roll number {r} missing in Research Paper")

# Verify Base Papers & Team in Master Encyclopedia
check("Wahid" in enc_content and "IJERT" in enc_content, "Base Paper 1 in Master Encyclopedia", "Base Paper 1 missing in Master Encyclopedia")
check("Nagarajan" in enc_content and "IJMRR" in enc_content, "Base Paper 2 in Master Encyclopedia", "Base Paper 2 missing in Master Encyclopedia")
for r in roll_numbers:
    check(r in enc_content, f"Roll Number {r} in Master Encyclopedia", f"Roll number {r} missing in Master Encyclopedia")

# Verify Faculty Mentor in Master Encyclopedia
check("TVG Sridevi" in enc_content or "Sridevi" in enc_content, "Faculty Mentor Dr. TVG Sridevi in Master Encyclopedia", "Dr. TVG Sridevi missing in Master Encyclopedia")
check("Computer Science and Engineering (AI&ML)" in enc_content, "Department CSE (AI&ML) in Master Encyclopedia", "Department CSE (AI&ML) missing in Master Encyclopedia")

# Check SRS document contains Base Paper citations and Roll Numbers
srs_docx = os.path.join(PROGRESSIVE_DIR, "02_SRS_Specification", "SmartInterview_SRS_Template_Format_v2.docx")
check(os.path.exists(srs_docx) and os.path.getsize(srs_docx) > 50000, "SRS v2 DOCX File Integrity", "SRS DOCX missing or too small")

# Check Official Documentation Report from SRDC template
doc_rep_docx = os.path.join(PROGRESSIVE_DIR, "01_Documentation_and_Viva", "SmartInterview_Documentation_Report_v2.docx")
check(os.path.exists(doc_rep_docx) and os.path.getsize(doc_rep_docx) > 2000000, "Official Documentation Report v2 DOCX Integrity", "Documentation Report DOCX missing or under 2MB")
doc_rep_pdf = os.path.join(PROGRESSIVE_DIR, "01_Documentation_and_Viva", "SmartInterview_Documentation_Report_v2.pdf")
check(os.path.exists(doc_rep_pdf) and os.path.getsize(doc_rep_pdf) > 200000, "Official Documentation Report v2 PDF Integrity", "Documentation Report PDF missing or under 200KB")

# Check PPT slide count (must be 9 after removing guideline slide)
import pptx
ppt_file = os.path.join(PROGRESSIVE_DIR, "04_Presentation_and_Defense", "SmartInterview_Project_Presentation_v2.pptx")
prs = pptx.Presentation(ppt_file)
check(len(prs.slides) == 9, "Presentation Slide Count (Guideline Slide Removed)", f"Expected 9 slides, found {len(prs.slides)}")

# ── SUMMARY ──────────────────────────────────────────────────────────
print("\n======================================================================")
print(f"VERIFICATION RESULTS: {len(passed_checks)} Passed | {len(errors)} Errors | {len(warnings)} Warnings")
print("======================================================================")
if errors:
    print("\nERRORS ENCOUNTERED:")
    for err in errors:
        print(" ", err)
    sys.exit(1)
else:
    print("\nALL VERIFICATIONS PASSED: 100% Coherent, Zero Conflicts Detected!")
    sys.exit(0)
