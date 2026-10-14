#!/usr/bin/env python3
"""
의약품 도매업 개인사업자 가용현금(Net Cash) 계산기 — 2026년 기준
=================================================================
입력: 월매출(공급가액), 매출총이익률, 고정비, 인적사항
출력: 부가세(패스스루), 종합소득세+지방소득세, 국민연금, 건강보험,
      연/월 가용현금.

핵심 원리(1st principles):
  가용현금 = 매출총이익 - 판관비 - 사회보험 - 소득세
  매출은 변수가 아니다. 매출총이익(마진)이 변수다.

제도 파라미터는 PARAMS 에 모아두었고, 출처/검증일은 work_log 참조.
"""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, asdict, field

# ---------------------------------------------------------------- 제도값 (2026)
PARAMS = {
    "vat_rate": 0.10,
    # 종합소득세 기본세율 (2023 개정, 2026 귀속 동일): (상한, 세율, 누진공제)
    "income_tax_brackets": [
        (14_000_000, 0.06, 0),
        (50_000_000, 0.15, 1_260_000),
        (88_000_000, 0.24, 5_760_000),
        (150_000_000, 0.35, 15_440_000),
        (300_000_000, 0.38, 19_940_000),
        (500_000_000, 0.40, 25_940_000),
        (1_000_000_000, 0.42, 35_940_000),
        (float("inf"), 0.45, 65_940_000),
    ],
    "local_tax_rate": 0.10,            # 지방소득세 = 소득세의 10%
    "basic_deduction": 1_500_000,      # 본인 기본공제
    "dependent_deduction": 1_500_000,  # 부양가족 1인당
    "standard_tax_credit": 70_000,     # 표준세액공제(사업자)
    "e_filing_credit": 20_000,         # 전자신고 세액공제
    # 노란우산공제 한도 (2025 납입분부터): (사업소득금액 상한, 한도)
    "yellow_umbrella_caps": [
        (40_000_000, 6_000_000),
        (60_000_000, 5_000_000),
        (100_000_000, 4_000_000),
        (float("inf"), 2_000_000),
    ],
    # 국민연금 지역가입자 (2026.1~ 9.5%, 상한 2026.7~ 659만)
    "np_rate": 0.095,
    "np_income_cap": 6_590_000,
    "np_income_floor": 410_000,
    # 건강보험 지역가입자 소득보험료 (2026 7.19%) + 장기요양(건보료의 13.14%)
    "hi_rate": 0.0719,
    "ltc_rate_of_hi": 0.1314,
    "hi_min_monthly": 19_780,          # 최저보험료(참고)
    "hi_property_points_price": 208.4, # 재산점수당 단가(공단 모의계산으로 재확인 필요)
    # 중소기업특별세액감면(조특법 7조) 소기업·도매업: 수도권/비수도권 모두 10%
    "sme_special_reduction_wholesale": 0.10,
    # 기장세액공제: 간편장부대상자가 복식부기로 신고 시 산출세액 20%, 한도 100만
    "bookkeeping_credit_rate": 0.20,
    "bookkeeping_credit_cap": 1_000_000,
    "double_entry_threshold_wholesale": 300_000_000,  # 도매업 복식부기 의무 기준(직전연도)
    # 직원 4대보험 사업주 부담률 근사 (연금4.75+건보3.595+장요0.47+고용1.15+산재0.7)
    "employer_social_rate": 0.1067,
}

# ---------------------------------------------------------------- 입력
@dataclass
class Inputs:
    monthly_sales: float                 # 월 매출(공급가액, 부가세 제외)
    gross_margin: float = 0.075          # 매출총이익률 (업계 평균 7.5%)
    rent: float = 1_500_000              # 월 임차료(창고+사무)
    vehicle: float = 600_000             # 월 차량·배송비
    misc: float = 400_000                # 월 기타(통신·기장료·보험·소모품)
    owner_is_pharmacist: bool = False    # 대표가 약사면 관리약사 불필요
    pharmacist_salary: float = 4_500_000 # 관리약사 월급(세전)
    other_staff_salary: float = 0        # 기타 직원 월급 합계
    dependents: int = 0                  # 부양가족 수(본인 제외)
    yellow_umbrella: bool = True         # 노란우산공제 가입(한도까지 납입 가정)
    sme_reduction: bool = True           # 중소기업특별세액감면 적용
    double_entry: bool = True            # 복식부기 기장(기장세액공제 대상 여부 자동판단)
    hi_property_points: float = 0        # 건보 재산점수(재산 1억 공제 후). 0=무재산
    taxable_purchase_ratio: float = 1.0  # 매입 중 과세매입 비율(의약품 도매 거의 1.0)
    label: str = ""

# ---------------------------------------------------------------- 계산
def income_tax(taxable: float) -> float:
    if taxable <= 0:
        return 0.0
    for cap, rate, deduct in PARAMS["income_tax_brackets"]:
        if taxable <= cap:
            return taxable * rate - deduct
    raise AssertionError

def yellow_cap(business_income: float) -> float:
    for cap, limit in PARAMS["yellow_umbrella_caps"]:
        if business_income <= cap:
            return limit
    raise AssertionError

def national_pension_monthly(income_monthly: float) -> float:
    base = min(max(income_monthly, PARAMS["np_income_floor"]), PARAMS["np_income_cap"])
    return base * PARAMS["np_rate"]

def health_insurance_monthly(income_monthly: float, property_points: float) -> float:
    hi = max(income_monthly, 0) * PARAMS["hi_rate"] + property_points * PARAMS["hi_property_points_price"]
    hi = max(hi, PARAMS["hi_min_monthly"])
    return hi * (1 + PARAMS["ltc_rate_of_hi"])

def compute(i: Inputs) -> dict:
    annual_sales = i.monthly_sales * 12
    cogs = annual_sales * (1 - i.gross_margin)
    gross_profit = annual_sales - cogs

    # 부가세: 사업자 부담이 아닌 패스스루 — 현금흐름 타이밍만 영향
    vat_out = annual_sales * PARAMS["vat_rate"]
    vat_in = cogs * i.taxable_purchase_ratio * PARAMS["vat_rate"]
    vat_payable = vat_out - vat_in   # 운영비 매입세액은 보수적으로 무시

    staff = (0 if i.owner_is_pharmacist else i.pharmacist_salary) + i.other_staff_salary
    staff_cost = staff * 12 * (1 + PARAMS["employer_social_rate"])
    fixed = (i.rent + i.vehicle + i.misc) * 12
    opex_ex_hi = staff_cost + fixed

    # 건보료는 필요경비, 국민연금은 소득공제 → 소득금액과 순환 → 고정점 반복
    hi_annual = 0.0
    for _ in range(30):
        business_income = gross_profit - opex_ex_hi - hi_annual
        hi_new = health_insurance_monthly(business_income / 12, i.hi_property_points) * 12
        if abs(hi_new - hi_annual) < 1:
            break
        hi_annual = hi_new
    business_income = gross_profit - opex_ex_hi - hi_annual

    np_annual = national_pension_monthly(business_income / 12) * 12 if business_income > 0 else 0.0
    yellow = min(yellow_cap(business_income), max(business_income, 0)) if i.yellow_umbrella else 0.0

    deductions = PARAMS["basic_deduction"] + i.dependents * PARAMS["dependent_deduction"] + np_annual + yellow
    taxable = max(business_income - deductions, 0)
    calc_tax = income_tax(taxable)

    reduction = calc_tax * PARAMS["sme_special_reduction_wholesale"] if i.sme_reduction else 0.0
    # 기장세액공제: 직전연도 매출 < 3억(간편장부대상)인데 복식부기로 신고한 경우
    bk_credit = 0.0
    if i.double_entry and annual_sales < PARAMS["double_entry_threshold_wholesale"]:
        bk_credit = min(calc_tax * PARAMS["bookkeeping_credit_rate"], PARAMS["bookkeeping_credit_cap"])
    credits = PARAMS["standard_tax_credit"] + PARAMS["e_filing_credit"] + bk_credit
    national_tax = max(calc_tax - reduction - credits, 0)
    local_tax = national_tax * PARAMS["local_tax_rate"]
    total_income_tax = national_tax + local_tax

    # 가용현금: 노란우산 납입액은 실제 현금 유출(적립)이지만 본인 자산이므로 '저축'으로 분리 표기
    net_cash = business_income - np_annual - total_income_tax
    disposable_after_savings = net_cash - yellow

    return {
        "label": i.label or f"월매출 {i.monthly_sales/1e4:,.0f}만 / 마진 {i.gross_margin*100:.1f}%",
        "inputs": asdict(i),
        "annual_sales": annual_sales,
        "gross_profit": gross_profit,
        "staff_cost": staff_cost,
        "fixed_cost": fixed,
        "health_insurance": hi_annual,
        "business_income": business_income,
        "national_pension": np_annual,
        "yellow_umbrella": yellow,
        "deductions": deductions,
        "taxable_income": taxable,
        "calc_tax": calc_tax,
        "sme_reduction": reduction,
        "credits": credits,
        "income_tax_total": total_income_tax,
        "effective_tax_rate_on_income": (total_income_tax / business_income) if business_income > 0 else 0,
        "vat_payable_passthrough": vat_payable,
        "net_cash_annual": net_cash,
        "net_cash_monthly": net_cash / 12,
        "disposable_monthly_after_yellow": disposable_after_savings / 12,
    }

# ---------------------------------------------------------------- 출력
def won(x: float) -> str:
    return f"{x/1e4:,.0f}만"

ROWS = [
    ("연매출(공급가액)", "annual_sales"),
    ("매출총이익", "gross_profit"),
    ("인건비(관리약사+4대보험)", "staff_cost"),
    ("고정비(임차·차량·기타)", "fixed_cost"),
    ("건강보험(필요경비)", "health_insurance"),
    ("= 사업소득금액", "business_income"),
    ("국민연금(소득공제)", "national_pension"),
    ("노란우산(소득공제)", "yellow_umbrella"),
    ("과세표준", "taxable_income"),
    ("산출세액", "calc_tax"),
    ("중기특별감면", "sme_reduction"),
    ("세액공제 합", "credits"),
    ("소득세+지방세", "income_tax_total"),
    ("[참고] 부가세 납부(패스스루)", "vat_payable_passthrough"),
    ("= 연 가용현금", "net_cash_annual"),
    ("= 월 가용현금", "net_cash_monthly"),
    ("월 가용현금(노란우산 적립 후)", "disposable_monthly_after_yellow"),
]

def markdown_table(results: list[dict]) -> str:
    head = "| 항목 | " + " | ".join(r["label"] for r in results) + " |"
    sep = "|---|" + "|".join("---:" for _ in results) + "|"
    lines = [head, sep]
    for name, key in ROWS:
        lines.append(f"| {name} | " + " | ".join(won(r[key]) for r in results) + " |")
    lines.append("| 실효세율(소득금액 대비) | " + " | ".join(f"{r['effective_tax_rate_on_income']*100:.1f}%" for r in results) + " |")
    return "\n".join(lines)

def default_scenarios() -> list[Inputs]:
    out = []
    for sales in (20_000_000, 30_000_000):
        for margin in (0.075, 0.10, 0.15, 0.20):
            out.append(Inputs(monthly_sales=sales, gross_margin=margin))
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sales", type=float, nargs="*", help="월매출(원) 목록. 미지정 시 2000만/3000만")
    ap.add_argument("--margin", type=float, nargs="*", help="매출총이익률 목록(0.075 등)")
    ap.add_argument("--pharmacist", action="store_true", help="대표가 약사(관리약사 급여 0)")
    ap.add_argument("--dependents", type=int, default=0)
    ap.add_argument("--no-yellow", action="store_true")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--scenarios", help="시나리오 JSON 파일 경로(Inputs 필드 배열)")
    a = ap.parse_args()

    if a.scenarios:
        with open(a.scenarios, encoding="utf-8") as f:
            scen = [Inputs(**s) for s in json.load(f)]
    elif a.sales or a.margin:
        scen = [Inputs(monthly_sales=s, gross_margin=m, owner_is_pharmacist=a.pharmacist,
                       dependents=a.dependents, yellow_umbrella=not a.no_yellow)
                for s in (a.sales or [20_000_000, 30_000_000])
                for m in (a.margin or [0.075])]
    else:
        scen = default_scenarios()
        for s in scen:
            s.owner_is_pharmacist = a.pharmacist
            s.dependents = a.dependents
            s.yellow_umbrella = not a.no_yellow

    results = [compute(s) for s in scen]
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(markdown_table(results))

if __name__ == "__main__":
    main()
