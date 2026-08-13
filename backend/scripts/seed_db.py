"""Seed database with sample mortgage documents and users.

Creates rich, queryable content across four RBAC departments:
  general, compliance, underwriting, eligibility

Documents are chunked via the real StructuralChunker and embeddings
are generated via the real FastEmbed model (or random fallback if
the model isn't downloaded yet — BM25 search still works without them).

Usage (from the backend/ directory):
    python -m scripts.seed_db

Or via docker:
    docker compose run --rm backend python -m scripts.seed_db
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.db.postgres.schema import ensure_schema
from app.db.postgres.session import acquire
from app.documents.chunking.structural_chunker import StructuralChunker
from app.documents.indexing import index_document
from app.auth.passwords import hash_password

logger = logging.getLogger(__name__)

# ─── Document corpus ────────────────────────────────────────────────
# Each entry: (title, doc_type, department, content_text)
DOCUMENTS: list[tuple[str, str, str, str]] = [
    # ── general ──
    (
        "Loan Application Process Guide",
        "process",
        "general",
        """Loan Application Process Guide

This guide walks applicants through our standard mortgage application process from start to finish.

Step 1 — Pre-Approval
Before house hunting, get pre-approved. This tells you how much home you can afford and strengthens your offer. You will need recent pay stubs, bank statements, and a credit report. A preliminary credit score of at least 620 is recommended for most programs.

Step 2 — House Hunting
Work with a real estate agent, view homes within your budget, and make an offer. Your pre-approval letter shows sellers you are a serious buyer.

Step 3 — Formal Application
Submit the official loan application (Form 1000). You must provide the purchase agreement, W-2s for the past two years, recent pay stubs (last 30 days), bank statements (last two months), and proof of homeowners insurance.

Step 4 — Processing
A loan processor verifies all documents, orders the home appraisal, and reviews your financial profile. The processor checks your debt-to-income (DTI) ratio, which should stay below 43 percent of gross monthly income for most conventional loans.

Step 5 — Underwriting
The underwriter makes the final decision. They review credit, income, assets, and the appraisal. If approved, you receive a commitment letter.

Step 6 — Closing
Sign final documents at closing. You will need a certified check or wire transfer for closing costs (typically 2-5 percent of the loan amount). After signing, the loan is recorded and you get the keys.""",
    ),
    (
        "2024 Mortgage Product Comparison",
        "product_guide",
        "general",
        """2024 Mortgage Product Comparison

Federal Housing Administration (FHA) Loans
Minimum credit score: 580 for 3.5 percent down, 500–579 for 10 percent down.
Maximum debt-to-income ratio: 43 percent.
Requires mortgage insurance premium (MIP) for the life of the loan on 3.5 percent down payments.
Loan limits vary by county; the baseline limit in most areas is $472,030.

Conventional Conforming Loans
Minimum credit score: 620.
Down payment: as low as 3 percent.
DTI limit: 45–50 percent depending on credit score.
No mortgage insurance required if down payment is 20 percent or more. If less than 20 percent, private mortgage insurance (PMI) is required until equity reaches 20 percent.

Jumbo Loans
Minimum credit score: 700 (680 for some lenders).
Typical down payment: 10–20 percent.
DTI limit: 43 percent (can go up to 50 percent with strong compensating factors).
Loan amounts above conforming limits ($809,950 in high-cost counties).

Adjustable-Rate Mortgage (ARM)
Initial fixed period of 5, 7, or 10 years.
After the initial period, the rate adjusts monthly or annually.
Caps limit how much the rate can change: initial cap, periodic cap, lifetime cap.
Minimum credit score: 620.
Maximum DTI: 43 percent.

VA Loans
Available to eligible veterans, active-duty service members, and surviving spouses.
No down payment or PMI required.
Funding fee: 1.25–3.3 percent of loan amount (can be rolled into the loan).
Credit score: no official minimum, but 620+ is recommended.

USDA Rural Development Loans
Available in eligible rural areas.
No down payment required.
Income limits apply: 115 percent of the area median income.
Credit score: 640+ recommended.
One percent upfront guarantee fee (can be rolled into the loan).""",
    ),
    (
        "Closing Costs and Fees Breakdown",
        "guide",
        "general",
        """Closing Costs and Fees Breakdown

Closing costs typically range from 2 to 5 percent of the loan amount. Here is a detailed breakdown of common fees:

1. Origination Fee (0.5–1.5 percent of loan amount)
   Covers the lender's cost of processing the loan. Often negotiable.

2. Appraisal Fee ($300–$500)
   Required by lenders to determine the property's market value.

3. Credit Report Fee ($25–$50)
   Pulls your credit history for underwriting.

4. Underwriting Fee ($500–$1,500)
   Charged by the lender for the underwriter's review.

5. Flood Determination Fee ($15–$30)
   Verifies whether the property is in a flood zone.

6. Title Search and Title Insurance (0.5–1 percent of loan amount)
   Ensures the property has clear ownership history.

7. Recording Fees ($50–$200)
   Charged by the county for recording the deed and mortgage.

8. Escrow Account Setup ($200–$500)
   Prepays property taxes and homeowners insurance.

9. Pre-paid Interest (0.1–0.5 percent of loan amount)
   Interest from the closing date until the first payment.

10. Private Mortgage Insurance (PMI) (0.3–1.5 percent annually)
   Required when down payment is less than 20 percent on conventional loans.

Lender credits can offset some closing costs in exchange for a slightly higher interest rate (rate buy-down).""",
    ),

    # ── compliance ──
    (
        "Fair Lending Policy",
        "policy",
        "compliance",
        """Fair Lending Policy

Our institution complies with federal fair lending laws to ensure equal access to mortgage credit.

Protected Classes Under the Equal Credit Opportunity Act (ECOA):
- Race, color, national origin, religion, sex, marital status, age, receipt of public assistance.

Prohibited Practices:
- redlining (discriminating based on neighborhood demographics or ZIP code)
- steering (directing applicants toward or away from certain loan products)
- disparate treatment (different standards, terms, or conditions)
- disparate impact (neutral policies that disproportionately affect a protected class)

Required Documentation:
- All lending decisions must be documented in writing.
- Adverse action notices must be sent within 30 days of a denial.
- Loan-level pricing adjustments must be justified by risk tiers, not borrower characteristics.

Fair Lending Training:
- All loan officers and underwriters must complete annual fair lending training.
- Training covers scenario-based examples of discriminatory practices.

Complaint Handling:
- Fair lending complaints are logged in the compliance tracking system.
- The compliance officer reviews all complaints within 5 business days.
- Annual fair lending audits are conducted by internal audit.""",
    ),
    (
        "Privacy and Data Protection Policy",
        "policy",
        "compliance",
        """Privacy and Data Protection Policy

We are committed to protecting customer personal and financial information under the Gramm-Leach-Bliley Act (GLBA) and applicable state laws.

Information We Collect:
- Personal identifiers: name, address, Social Security Number, date of birth.
- Financial information: income, assets, debts, employment history, credit history.
- Property information: address, appraised value, tax assessments.
- Communications: email, phone call recordings, chat transcripts.

How We Use Information:
- Process and evaluate loan applications.
- Conduct background and credit checks.
- Comply with legal and regulatory requirements.
- Detect fraud and prevent financial crime.
- Provide customer service and account management.

Information Sharing:
- We do not sell customer information to third parties.
- Third-party service providers (appraisers, title companies, credit bureaus) receive only the minimum information needed for their function.
- All third parties sign confidentiality agreements and are subject to GLBA safeguards.

Data Security:
- Customer data is encrypted in transit (TLS 1.3) and at rest (AES-256).
- Access is restricted on a need-to-know basis with role-based access controls.
- Multi-factor authentication is required for all internal systems.
- Audit logs track every access to customer records.

Retention and Disposal:
- Personal information is retained for 7 years after loan maturity or termination.
- Paper records are shredded. Electronic records are securely deleted.

Customer Rights:
- Customers may request a copy of their personal information.
- Opt-out of information sharing is available (except for credit-related disclosures required by law).
- Privacy notices are provided at application and annually thereafter.""",
    ),
    (
        "Anti-Money Laundering (AML) Requirements",
        "policy",
        "compliance",
        """Anti-Money Laundering (AML) Requirements

This policy implements the Bank Secrecy Act (BSA), USA PATRIOT Act, and FinCEN regulations.

Customer Due Diligence (CDD):
- Verify identity of all applicants using government-issued photo ID.
- Collect and verify residential address via utility bills, bank statements, or lease agreements.
- Identify beneficial owners for legal entity applicants (25 percent threshold).

Suspicious Activity Monitoring:
- Transaction monitoring system flags unusual patterns (e.g., rapidly increasing loan amounts, straw buyer indicators).
- Currency transactions over $10,000 must be reported via Form 1003.
- Suspicious Activity Reports (SARs) must be filed within 30 days of detection.

Red Flags to Report:
- Unusual urgency to close without normal verification steps.
- Reluctance to provide standard documentation.
- Discrepancies between application and supporting documents.
- Complex ownership structures that obscure beneficial ownership.
- Loans involving politically exposed persons (PEPs).

OFAC Screening:
- All applicants are screened against the SDN (Specially Designated Nationals) list.
- Screening occurs at application and at closing.
- Blocked persons must be reported to OFAC within 10 days.

Recordkeeping:
- CDD records retained for 5 years after account closure.
- SARs retained for 7 years.
- Training records retained for 3 years.

AML Training:
- All relevant employees complete annual AML training.
- The compliance officer provides quarterly AML updates to underwriting and processing teams.""",
    ),
    (
        "Red Flags Identity Theft Policy",
        "policy",
        "compliance",
        """Red Flags Identity Theft Prevention Policy

Implemented under the Fair and Accurate Credit Transactions Act (FACTA) and FTC Red Flags Rules.

Identifying Information Red Flags:
- Suspicious personal information (e.g., address does not match credit report, SSN already associated with another file).
- Documents that look altered or forged.
- Photographs that appear to be cut and pasted or taken from a distance.
- Discrepancies in employment, income, or asset information not supported by documentation.

Detecting Red Flags:
- Credit report shows multiple recent inquiries or new accounts.
- Address or phone number recently changed without forwarding confirmation.
- Applicant requests rapid processing with reluctance to provide standard verification.

Responding to Red Flags:
- Level 1 (Low): Enhanced verification (additional documentation, phone call to employer).
- Level 2 (Medium): Secondary review by compliance officer.
- Level 3 (High): File a report with the FTC IdentityTheft.gov and suspend the application.

Customer Notification:
- If identity theft is confirmed, the customer is notified within 3 business days.
- A fraud alert is placed on the customer's credit file.
- Law enforcement is contacted if criminal activity is suspected.

Program Updates:
- The Red Flags program is reviewed quarterly.
- Updates address new identity theft vectors and regulatory guidance.
- Annual board approval of the program is documented.""",
    ),

    # ── underwriting ──
    (
        "Credit Scoring and Risk Assessment Guidelines",
        "underwriting",
        "underwriting",
        """Credit Scoring and Risk Assessment Guidelines

Underwriting Standards for Credit Evaluation

Credit Score Tiers:
Excellent: 760+ — Best available pricing, no interest rate adjustment.
Good: 700–759 — Standard pricing with minor adjustments.
Fair: 680–699 — Pricing adjustment of +0.25 percent.
Need Work: 620–679 — Pricing adjustment of +0.5 percent, additional reserves may be required.
Below 620: Refer to senior underwriter for approval; typically requires 25+ percent down and substantial reserves.

Debt-to-Income (DTI) Ratio Limits:
- Front-end DTI (housing costs): maximum 28 percent of gross monthly income.
- Back-end DTI (total debt including housing): maximum 43 percent for standard approval.
- High-DTI exceptions (up to 50 percent) require compensating factors:
  * Excellent credit score (740+)
  * Substantial asset reserves (6+ months of payments)
  * Secondary income from a stable source
  * Significant down payment (30 percent or more)

Compensating Factors:
- Reserves: cash/savings that can cover PITI for 1–6 months.
- Liquidity: unencumbered assets (checking, savings, retirement accounts excluding penalties).
- Stable employment: 2+ years with the same employer or consistent income history.
- Large down payment: 20 percent or more reduces risk.

Credit Report Review:
- Analyze all three credit bureaus (Experian, TransUnion, Equifax).
- Dispute any inconsistencies or errors before underwriting.
- Bankruptcies: discharged bankruptcy can be considered after 2 years (Chapter 7) or 4 years (Chapter 13) with re-established credit.
- Foreclosures: 4 years since completion of foreclosure or deed-in-lieu.

Interest Rate Adjustments:
Credit score below 700 adds 0.125 percent to 0.5 percent to the rate.
Each percentage point above 43 percent DTI adds 0.125 percent.
Less than 20 percent down (without PMI) adds 0.25 percent.""",
    ),
    (
        "Income and Employment Verification Handbook",
        "underwriting",
        "underwriting",
        """Income and Employment Verification Handbook

Documenting Income for Mortgage Qualification

Primary Income Sources:
1. Salaried Employment — Verify with recent pay stubs (last 30 days) and W-2 forms (past two years). Base salary is the gross amount before deductions.

2. Commission and Bonus Income — Requires a two-year history. Use the lower of year-over-year decline or average of the most recent two years. Must be likely to continue.

3. Self-Employment Income — Requires complete federal tax returns (Form 1040, Schedule C or K-1), year-to-date profit-and-loss statement, and a CPA-prepared letter. Add back non-recurring expenses (depreciation, amortization, one-time charges).

4. Rental Income — Requires Schedule E and two years of tax returns. Use the lower of the reported amount or 75 percent of the gross rent (to account for vacancy).

5. Retirement or Disability Income — Requires award letters, tax returns (if taxable), and documentation that payments will continue for at least three years.

6. Child Support or Alimony — Requires divorce decree or court order, proof of receipt for one year, and documentation that payments will continue for at least three years.

Employment Verification:
- Contact employer directly for all applicants. Use the employer's official phone number.
- Verify dates of employment, current position, and expected continuation of employment.
- For self-employed, verify business existence with a business license or state filing.

Income Calculation Methods:
- Monthly gross income: annual salary divided by 12.
- Hourly employees: hourly rate × hours per week × 52 / 12.
- Overtime: included only if documented for two years.
- Base income only is used for DTI calculation unless consistently documented.

Asset Documentation:
- Bank statements: last two months, large deposits seasoning for 60+ days.
- Investment accounts: most recent statement.
- Retirement accounts: most recent statement; 401k loans noted separately.
- Gift letters: required for gifted funds; must show relationship and that no repayment is expected.

Red Flags Requiring Additional Review:
- Recent job changes without explanation.
- Unexplained gaps in employment.
- Self-employment in business for less than two years.
- Large, unseasoned deposits in bank statements.""",
    ),
    (
        "Automated Underwriting System (AUS) Decision Guide",
        "underwriting",
        "underwriting",
        """Automated Underwriting System (AUS) Decision Guide

The AUS (Desktop Underwriter or Loan Product Advisor) provides real-time underwriting decisions.

AUS Responses:
1. Approve/Eligible (A/E): The loan meets all guidelines. Minimal or no manual underwriting required.
2. Approve/Ineligible (A/IN): The loan qualifies but requires additional documentation or conditions.
3. Refer/Known (R/K): Requires manual underwriting. Submit to a senior underwriter.
4. Refer/Sent (R/S): Incomplete submission. Resubmit with additional information.

When to Use AUS:
- All conventional, FHA, VA, and USDA loan applications.
- New construction, purchase, and refinance transactions.
- Primary residence, second homes, and 2–4 unit investment properties.
- Do NOT use AUS for commercial loans or loans with 5+ units.

Triggering AUS Fields:
- Credit score below 620.
- DTI above 43 percent.
- Down payment less than 10 percent.
- Self-employed borrower.
- Bankruptcy or foreclosure in the past 7 years.
- Non-traditional credit references (rent, utilities, phone).

Overriding AUS:
- Can only be overridden by a senior underwriter (AU-3 or higher).
- Must document the rationale for any override.
- All override reasons and compensating factors must be fully documented in the loan file.

Property Type Restrictions:
- Condos: Must be on the HUD-approved list.
- Co-ops: Not eligible for FHA or VA; considered on a case-by-case basis for conventional loans.
- manufactured homes: Require specific construction and affidavit standards.

Non-QM and Exception Loans:
- Must bypass AUS and go through full manual underwriting.
- Requires VP approval and additional risk-based pricing adjustments.

Resubmission After AUS Refer:
- Address all identified conditions before resubmitting.
- Include all required documentation in the correct format.
- Use the same case ID if resubmitting within 30 days.""",
    ),

    # ── eligibility ──
    (
        "Minimum Eligibility Requirements by Loan Program",
        "eligibility",
        "eligibility",
        """Minimum Eligibility Requirements by Loan Program

Federal Housing Administration (FHA) Loans
Minimum credit score: 500 for 10 percent down (3.5 percent down requires 580+).
Maximum DTI: 43 percent (can go to 50 percent with compensating factors).
Down payment: Minimum 3.5 percent from own funds or gifted funds.
Cash reserves: 1 month of PITI required.
Employment: 2 years of stable employment history.
Property: Must be the borrower's primary residence. Second homes and investment properties are not eligible.
First-time homebuyer: Not required, but preferred.
Gift funds: Allowed from family, close relative, employer, or charitable organization. Must include a gift letter.
Reserves: 1 month of mortgage payment in the bank after closing.

Conventional Conforming Loans
Minimum credit score: 620 for fixed-rate, 660 for ARMs (some lenders accept 600).
Maximum DTI: 45 percent standard, up to 50 percent with strong compensating factors.
Down payment: Minimum 3 percent (can be gifted for primary residence).
Property: Primary residence or second home. 2–4 unit properties allowed.
Reserves: 2 months for first-time buyers, 6 months for investment properties.
Self-employment: 2 years of tax returns required.

Jumbo Loans
Minimum credit score: 700 (680 for some lenders with strong factors).
Maximum DTI: 43 percent (exceptions up to 50 percent with compensating factors).
Down payment: Minimum 10–20 percent.
Cash reserves: 6–12 months of mortgage payments required in the bank.
Annual income: Typically requires $200,000+ household income.
Assets: Liquid assets equal to 1–2 months of payments plus closing costs.
Property: Primary residence, second home, or 1–4 unit investment.

VA Loans
Eligibility: Must be a veteran, active-duty service member, or surviving spouse.
Credit score: No official minimum, but 620+ is recommended.
Funding fee: 1.25–3.3 percent (varies by down payment and service type).
Down payment: Zero down payment allowed.
Property: Primary residence only. No second homes or investment properties.
Reserves: Not typically required but preferred for self-employed borrowers.

USDA Rural Development Loans
Property location: Must be in an eligible rural area (check the USDA eligibility map).
Income limit: 115 percent of the area median income (varies by county).
Credit score: 640+ recommended (680+ for streamlined processing).
Down payment: Zero down payment allowed.
Debt limits: DTI 29/41 (front/back), exceptions up to 46 percent.
Property: Must be a primary residence in a rural area.

Adjustable-Rate Mortgage (ARM)
Minimum credit score: 620.
Maximum DTI: 43 percent.
Down payment: Same as the underlying loan program (conventional, FHA, etc.).
Rate protection: Initial fixed period of 5, 7, or 10 years.
Recapture: Some programs have recapture requirements on refinance.""",
    ),
    (
        "Asset and Reserve Requirements",
        "eligibility",
        "eligibility",
        """Asset and Reserve Requirements

Documentation of Assets:
- Bank statements: Two months of complete statements for all deposit accounts (checking, savings, CDs, money market).
- Investment accounts: Most recent statement showing current value and recent activity.
- Retirement accounts: 401k, IRA, Roth IRA — most recent statement.
- Business assets: Year-to-date profit/loss statement, balance sheet, and two years of business tax returns.
- Gift funds: Must be documented with a gift letter and evidence of transfer (cancelled check or bank transfer).

Seasoning Requirements:
- Large deposits (over 50 percent of monthly income) must be seasoned for 60+ days in the account.
- Exception: Deposits from verified gifts, sale of another property, or employer bonuses are exempt from seasoning.
- Retirement account withdrawals: Documented with a 401k/IRA distribution statement.

Cash Reserves:
- Primary residence purchase: 1 month of PITI reserves for conventional loans, 2 months for FHA.
- Second home: 2 months of reserves.
- Investment property (1 unit): 4 months of reserves (covers 2 properties).
- Investment property (2–4 units): 6 months of reserves.
- Self-employed borrowers: 6 months of reserves for all property types.

Acceptable Reserve Assets:
- Cash, checking, savings (verified by bank statement).
- Certificates of deposit (CDs) with documented withdrawal penalties.
- Stocks, bonds, mutual funds (valued at current market price).
- 401k/IRA (valued at vested balance minus early withdrawal penalties if under age 59.5).
- Gift funds (with proper gift letter and no repayment expected).
- Proceeds from sale of primary residence (must be completed before closing).

Unacceptable Reserve Assets:
- Future appreciation of the subject property.
- Guaranteed loans or notes.
- Life insurance cash value without a withdrawal option.
- Automobiles, boats, or collectibles.
- Unvested stock options or restricted stock units.""",
    ),
]

# ─── Seed users ──────────────────────────────────────────────────────
SEED_USERS: list[dict] = [
    {
        "email": "admin@hexa.local",
        "password": "adminpass",
        "full_name": "Admin User",
        "role": "super_admin",
        "department": "general",
        "allowed_departments": ["compliance", "underwriting", "eligibility"],
    },
    {
        "email": "officer@hexa.local",
        "password": "officerpass",
        "full_name": "Loan Officer",
        "role": "loan_officer",
        "department": "general",
        "allowed_departments": ["compliance"],
    },
    {
        "email": "underwriter@hexa.local",
        "password": "uwpass",
        "full_name": "Underwriter",
        "role": "underwriter",
        "department": "underwriting",
        "allowed_departments": ["general"],
    },
    {
        "email": "compliance@hexa.local",
        "password": "compliancepass",
        "full_name": "Compliance Officer",
        "role": "compliance",
        "department": "compliance",
        "allowed_departments": ["general"],
    },
    {
        "email": "eligibility@hexa.local",
        "password": "eligibilitypass",
        "full_name": "Eligibility Specialist",
        "role": "loan_officer",
        "department": "eligibility",
        "allowed_departments": ["general"],
    },
    {
        "email": "agent@hexa.local",
        "password": "agentpass",
        "full_name": "Customer Service Agent",
        "role": "loan_officer",
        "department": "general",
        "allowed_departments": [],
    },
]


def seed_documents() -> None:
    """Clear and re-seed the documents table with sample content."""
    from app.documents.embedding import generate_embeddings

    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks")
            cur.execute("DELETE FROM documents")
            conn.commit()

    chunker = StructuralChunker(max_tokens=300)

    from app.documents.text_extraction import ExtractedText

    total_docs = 0
    total_chunks = 0

    for title, doc_type, department, content in DOCUMENTS:
        extracted = ExtractedText(
            text=content,
            pages=[content],
            source_format="md",
        )

        chunks = list(chunker.chunk(extracted))
        if not chunks:
            logger.warning("No chunks for '%s', skipping", title)
            continue

        chunk_texts = [c.content for c in chunks]

        embeddings = None
        try:
            embeddings = generate_embeddings(chunk_texts)
        except Exception as e:
            logger.warning("Embedding generation failed for '%s': %s", title, e)
            embeddings = None

        with acquire() as conn:
            result = index_document(
                conn=conn,
                doc_title=title,
                doc_type=doc_type,
                department=department,
                source_path=None,
                chunks=chunks,
                embeddings=embeddings,
            )
            total_docs += 1
            total_chunks += result.chunks_indexed
            logger.info(
                "Seeded '%s' (dept=%s): %d chunks",
                title, department, result.chunks_indexed,
            )

    logger.info(
        "Seed complete: %d documents, %d chunks", total_docs, total_chunks
    )


def seed_users() -> None:
    """(Re)create the seed users table."""
    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users")
            conn.commit()

            for u in SEED_USERS:
                cur.execute(
                    "INSERT INTO users "
                    "(email, password_hash, full_name, role, department, allowed_departments) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        u["email"],
                        hash_password(u["password"]),
                        u["full_name"],
                        u["role"],
                        u["department"],
                        u["allowed_departments"],
                    ),
                )
            conn.commit()
            logger.info("Seeded %d users", len(SEED_USERS))


def print_credentials() -> None:
    print("\n" + "=" * 60)
    print("  LOGIN CREDENTIALS")
    print("=" * 60)
    for u in SEED_USERS:
        print(f"  {u['email']:<25}  /  {u['password']:<16}  ({u['role']}, dept={u['department']})")
    print("=" * 60 + "\n")


def print_sample_questions() -> None:
    questions = [
        # ── General questions (any role) ──
        ("What are the steps in the mortgage application process?",
         "General Process", "loan_application_process_guide.md"),
        ("How much are typical closing costs?",
         "General Costs", "closing_costs_and_fees.md"),
        ("Compare FHA and conventional loan requirements.",
         "General Products", "mortgage_product_comparison.md"),

        # ── Compliance questions (loan_officer + compliance only) ──
        ("What is the Equal Credit Opportunity Act?",
         "Compliance", "fair_lending_policy.md"),
        ("How long should we retain CDD records?",
         "Compliance", "aml_requirements.md"),
        ("What are the Red Flags that require filing a SAR?",
         "Compliance", "aml_requirements.md"),
        ("What customer data must we encrypt?",
         "Compliance", "privacy_policy.md"),

        # ── Underwriting questions (underwriter only) ──
        ("What credit score is needed for the best rate?",
         "Underwriting", "credit_scoring_guidelines.md"),
        ("What compensating factors allow DTI above 43 percent?",
         "Underwriting", "credit_scoring_guidelines.md"),
        ("How do we document self-employment income?",
         "Underwriting", "income_verification_handbook.md"),
        ("When should an AUS refer decision be overridden?",
         "Underwriting", "aus_decision_guide.md"),

        # ── Eligibility questions (eligibility role only) ──
        ("What credit score is required for a VA loan?",
         "Eligibility", "eligibility_requirements.md"),
        ("How much cash reserves do I need for a jumbo loan?",
         "Eligibility", "eligibility_requirements.md"),
        ("What assets are NOT acceptable for reserves?",
         "Eligibility", "asset_and_reserve_requirements.md"),

        # ── Cross-department access (loan_officer sees compliance) ──
        ("What protected classes are covered by ECOA?",
         "Cross-dept (officer sees compliance)", "fair_lending_policy.md"),

        # ── Questions that should return low/no match ──
        ("What is the latest iPhone model?",
         "No-match (out of domain)", None),
        ("How do I reset my router password?",
         "No-match (not mortgage-related)", None),
    ]

    print("=" * 60)
    print("  SAMPLE QUESTIONS (by access level)")
    print("=" * 60)
    for q, cat, source in questions:
        src = f" — expects match from {source}" if source else " — expects low/no match"
        print(f"  [{cat}]\n    Q: {q}{src}\n")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    ensure_schema()
    seed_users()
    seed_documents()
    print_credentials()
    print_sample_questions()
