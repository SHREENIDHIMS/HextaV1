"""Generate synthetic mortgage documents for batch ingestion testing."""

from __future__ import annotations

import random
from pathlib import Path

LOAN_TYPES = ["conventional", "FHA", "VA", "USDA"]
TOPICS = [
    "credit_score",
    "debt_to_income",
    "down_payment",
    "interest_rate",
    "closing_costs",
    "appraisal",
    "title_insurance",
    "loan_terms",
    "documentation_required",
    "eligibility_criteria",
    "processing_time",
    "rate_lock",
    "escrow_account",
]
DEPARTMENTS = ["general", "lending", "underwriting", "compliance"]

TEMPLATES = {
    "credit_score": """CREDIT SCORE REQUIREMENTS

For {loan_type} loans, the minimum credit score is {min_score}.
Borrowers with scores between {low_score} and {mid_score} may qualify
with additional documentation and a larger down payment.

Credit score tiers and corresponding rates:
- Excellent: 760+ → best rate
- Good: 700-759 → slightly higher rate
- Fair: 640-699 → standard plus 0.5%
- Below 620: requires justification

Factors affecting credit score:
1. Payment history ({pct_history}% weight)
2. Credit utilization ({pct_util}% weight)
3. Length of credit history ({pct_length}% weight)
4. New credit ({pct_new}% weight)
5. Credit mix ({pct_mix}% weight)
""",
    "debt_to_income": """DEBT-TO-INCOME RATIO GUIDELINES

Maximum DTI ratios for {loan_type}:
- Front-end ratio: {front_pct}% (housing expenses / income)
- Back-end ratio: {back_pct}% (total debt / income)

Exceptions may be made for:
- High credit scores (>740)
- Substantial reserves (>24 months)
- Low LTV (<70%)

Documentation required:
- Pay stubs (last 30 days)
- W-2 forms (last 2 years)
- Tax returns (last 2 years)
- Bank statements (last 60 days)
""",
    "down_payment": """DOWN PAYMENT REQUIREMENTS

{loan_type} minimum down payment: {min_down}%.

Options to meet down payment:
1. Personal savings (verified via bank statements)
2. Gift funds (requires gift letter)
3. Retirement account withdrawal (subject to tax implications)
4. Down payment assistance programs (DPA)

For primary residences: {primary_pct}% minimum
For second homes: {second_pct}% minimum
For investment properties: {invest_pct}% minimum
""",
    "interest_rate": """INTEREST RATE STRUCTURE

Current {loan_type} rates:
- 30-year fixed: {rate_30} APR
- 15-year fixed: {rate_15} APR
- 5/1 ARM: {rate_arm} APR (initial)
- 7/1 ARM: {rate_7arm} APR (initial)

Rate lock options:
- 30-day lock: included in rate
- 45-day lock: +{rate_45_fee} fee
- 60-day lock: +{rate_60_fee} fee

Rate float down option available once before closing.
""",
    "closing_costs": """CLOSING COSTS BREAKDOWN

Estimated closing costs for {loan_type}:
- Origination fee: {pct_orig}% of loan
- Appraisal: ${appraisal}
- Credit report: ${credit_report}
- Title insurance: ${title_insurance}
- Recording fees: ${recording}
- Escrow setup: ${escrow_setup}
- Attorney fees: ${attorney}

Total estimated: ${total_cost} ({pct_total}% of loan amount)
Seller may contribute up to {pct_seller_contrib}% for {loan_type}.
""",
    "appraisal": """APPRAISAL PROCESS

{loan_type} appraisal requirements:
- Full appraisal required for primary residences
- Limited appraisal for rate/term refinances
    - Exempt for streamline refinances with >70% LTV

Appraiser must be:
- Licensed in the state
- Fannie Mae or Freddie Mac approved
- Independent (no affiliation with borrower)

Timeline: 7-14 business days
Cost: ${appraisal_cost}
    """,
    "title_insurance": """TITLE INSURANCE OVERVIEW

For {loan_type} loans:
- Lender's title policy: required, protects the lender
- Owner's title policy: optional, protects the buyer

Coverage amount:
- Lender's: equal to loan amount
- Owner's: equal to purchase price or refinance amount

Standard exclusions:
- Zoning restrictions
- Environmental hazards
- Survey matters not shown
- easement rights
""",
    "loan_terms": """LOAN TERMS AND CONDITIONS

{loan_type} standard terms:
- Maximum term: {max_term} years
- Minimum term: {min_term} years
- Amortization: {amortization}
- Pre Payment penalty: {prepay_penalty}

Balloon options:
- 5-year interest only: available
- 7-year balloon: available for {loan_type}
- 10-year interest only: available for high-balance

Rate structure:
- Fully amortizing
- Interest-only option
- Minimum payment calculation
""",
    "documentation_required": """REQUIRED DOCUMENTATION

{loan_type} documentation checklist:
[ ] Application form (Form 1003)
[ ] Proof of income (last 2 years)
[ ] Federal tax returns (last 2 years)
[ ] W-2 and/or 1099 forms
[ ] Pay stubs (last 30 days)
[ ] Bank statements (last 60 days)
[ ] Asset statements
[ ] Liability statements
[ ] Identification (driver's license or passport)
[ ] Social Security number

Additional for self-employed:
[ ] Profit and loss statement
[ ] Balance sheet
[ ] Business tax returns
""",
    "eligibility_criteria": """ELIGIBILITY CRITERIA

{loan_type} eligibility requirements:
1. Credit score: minimum {min_score}
2. Debt-to-income ratio: maximum {max_dti}%
3. Down payment: minimum {min_down}%
4. Loan-to-value ratio: maximum {max_ltv}%
5. Reserves: minimum {min_reserves} months

Property types accepted:
- Single family detached {primary_ok}
- Condominium {condo_ok}
- Townhouse {townhouse_ok}
- 2-4 unit property {multi_ok}
- Manufactured home {manufactured_ok}

Borrower requirements:
- Minimum age: 18
- Employment: 2+ years in same field
- Bankruptcy: discharged {bankruptcy_wait}
- Foreclosure: {foreclosure_wait} waiting period
""",
    "processing_time": """PROCESSING TIMELINE

{loan_type} standard timeline:
- Application to pre-approval: 1-3 business days
- Under contract to clear to close: 21-45 days
- Appraisal: 7-14 business days
- Underwriting: 3-5 business days
- Final approval: 1-2 business days
- Closing: 1-3 business days

Factors that extend timeline:
- Complex credit situations
- Self-employed income
- Property issues
- High loan amounts
- Low appraisal values
- Missing documentation
""",
    "rate_lock": """RATE LOCK POLICY

{loan_type} rate lock options:
- Standard lock: 30-60 days, no fee
- Extended lock: 90 days, +{ext_fee} fee
- 120-day lock: +{ext_120_fee} fee (available for construction)

Lock benefits:
- Protection against rate increases
- Rate match guarantee
- One free float-down option

Lock confirmation:
- Must be confirmed in writing
- Lock period starts on business day
- Rates valid until lock expires
""",
    "escrow_account": """ESCROW ACCOUNT DETAILS

{loan_type} escrow requirements:
- Property taxes: collected monthly
- Homeowners insurance: collected monthly
- Mortgage insurance: collected monthly (if applicable)

Escrow analysis:
- Performed annually
- Projected vs actual amounts
- Cushion: 1/12 of projected annual disbursements

Low escrow options:
- Waive escrow for {loan_type} if LTV < {escrow_waive_ltv}%
- Borrower pays taxes/insurance directly
- One-time escrow waiver fee: ${escrow_waiver_fee}
""",
}


def generate_document(idx: int) -> tuple[str, str, str]:
    """Generate a document and return (filename, content, department)."""
    topic = random.choice(TOPICS)
    loan_type = random.choice(LOAN_TYPES)
    department = random.choice(DEPARTMENTS)

    template = TEMPLATES[topic]
    content = template.format(
        loan_type=loan_type,
        pct_orig=random.choice([0.5, 1.0, 1.5, 2.0]),
        low_score=random.randint(500, 620),
        mid_score=random.randint(620, 700),
        pct_history=random.choice(["35", "30", "35"]),
        pct_util=random.choice(["30", "20", "30"]),
        pct_length=random.choice(["15", "20", "15"]),
        pct_new=random.choice(["10", "15", "10"]),
        pct_mix=random.choice(["10", "15", "10"]),
        front_pct=random.choice([28, 31, 36, 41, 43]),
        back_pct=random.choice([36, 43, 45, 50, 55]),
        min_down=random.choice([0, 3.0, 3.5, 5.0, 10.0, 15.0, 20.0]),
        primary_pct=random.choice([3, 3.5, 5.0, 5.0]),
        second_pct=random.choice([10.0, 15.0, 20.0]),
        invest_pct=random.choice([15.0, 20.0, 25.0]),
        rate_30=round(random.uniform(5.5, 8.5), 2),
        rate_15=round(random.uniform(5.0, 8.0), 2),
        rate_arm=round(random.uniform(5.25, 8.25), 2),
        rate_7arm=round(random.uniform(5.25, 8.25), 2),
        rate_45_fee=round(random.uniform(100, 500), 0),
        rate_60_fee=round(random.uniform(200, 700), 0),
        appraisal=random.choice([350, 450, 550, 600, 750]),
        credit_report=random.randint(15, 40),
        title_insurance=round(random.uniform(500, 2000), 0),
        recording=random.randint(50, 200),
        escrow_setup=random.choice([150, 200, 250, 300]),
        attorney=random.choice([0, 500, 1000, 1500]),
        total_cost=round(random.uniform(4000, 12000), 0),
        pct_total=round(random.uniform(2.0, 5.0), 1),
        pct_seller_contrib=random.choice([2, 3, 6, 9]),
        appraisal_cost=random.randint(300, 800),
        max_term="30",
        min_term="5",
        amortization=random.choice(["Fully amortizing", "Interest only 5/60"]),
        prepay_penalty=random.choice(["None", "Yes, first 3 years"]),
        min_score=random.choice([500, 580, 620, 660, 700]),
        max_dti=random.choice([43, 45, 50, 55]),
        max_ltv=random.choice([80, 87, 90, 95, 97, 100]),
        min_reserves=random.choice([0, 2, 3, 6, 12, 24]),
        primary_ok=random.choice(["Yes", "Yes"]),
        condo_ok=random.choice(["Yes", "Yes"]),
        townhouse_ok=random.choice(["Yes", "Yes"]),
        multi_ok=random.choice(["No", "Yes"]),
        manufactured_ok=random.choice(["No", "No"]),
        bankruptcy_wait=random.choice(["2 years", "4 years", "7 years"]),
        foreclosure_wait=random.choice(["3 years", "4 years", "7 years"]),
        ext_fee=round(random.uniform(500, 1500), 0),
        ext_120_fee=round(random.uniform(1000, 2000), 0),
        escrow_waive_ltv=random.choice([60, 70, 75, 80]),
        escrow_waiver_fee=random.randint(200, 500),
    )

    filename = f"doc_{idx:05d}_{topic}_{loan_type}.txt"
    return filename, content, department


def main(n: int = 100) -> None:
    pending = Path("storage/pending")
    pending.mkdir(parents=True, exist_ok=True)

    for i in range(n):
        fname, content, dept = generate_document(i)
        path = pending / f"{dept}_{fname}"
        path.write_text(content, encoding="utf-8")

    print(f"Generated {n} documents in {pending}/")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=100)
    a = p.parse_args()
    main(a.n)
