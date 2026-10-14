#!/usr/bin/env python3
"""
CSO(의약품 판촉영업자) 가용현금 계산기 — 2026년 기준
=====================================================
입력: 월 순이익(수수료 매출 − 판촉·차량·통신 등 사업경비, 본인 사회보험·소득세 차감 전)
출력: 개인사업자(감면 유형별) vs 법인(대표 급여 설계) 월 가용현금 비교

제도값·공통 함수는 pharma_tax_calc.PARAMS 를 재사용한다.
"""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, asdict
from pharma_tax_calc import PARAMS, income_tax, yellow_cap, national_pension_monthly, health_insurance_monthly, won

# ------------------------------------------------------------ 추가 제도값 (2026)
P2 = {
    # 개인 최저한세: 감면 전 산출세액 3천만 이하 35%, 초과분 45% (조특법 132조)
    "min_tax_low": 0.35, "min_tax_high": 0.45, "min_tax_split": 30_000_000,
    # 창업중소기업 세액감면(조특법 6조): 5년간. 100% 감면 연도는 최저한세 배제.
    # 업종이 '사업지원 서비스업'으로 인정될 때만 가능. '상품중개업(도매 범주)'이면 불가.
    # 2026.1.1 이후 창업분 감면율 개편(75%) 보도 있음 → startup_rate 파라미터로 둠.
    # 법인세 2026 사업연도~: 2억 이하 10%, 200억 이하 20% (2025.12 개정, 1%p 인상)
    "corp_brackets": [(200_000_000, 0.10, 0), (20_000_000_000, 0.20, 20_000_000)],
    "corp_local_rate": 0.10,
    # 근로소득공제 (총급여 구간: 상한, 공제율, 누적공제)
    "earned_income_deduction": [
        (5_000_000, 0.70, 0),
        (15_000_000, 0.40, 3_500_000),
        (45_000_000, 0.15, 7_500_000),
        (100_000_000, 0.05, 12_000_000),
        (float("inf"), 0.02, 14_750_000),
    ],
    "earned_income_deduction_cap": 20_000_000,
    # 근로소득세액공제: 산출세액 130만 이하 55%, 초과 30%; 한도 총급여별 74/66/50/20만
    # 직장가입자 본인부담: 연금 4.75%, 건보 3.595%(+장기요양 13.14%), 고용 0.9%
    "emp_np": 0.0475, "emp_hi": 0.03595, "emp_ei": 0.009,
    # 사업주 부담: 연금 4.75, 건보 3.595(+장요), 고용 1.15, 산재 0.7(서비스업 근사)
    "er_np": 0.0475, "er_hi": 0.03595, "er_ei": 0.0115, "er_wc": 0.007,
    "dividend_tax": 0.154,  # 배당소득 원천징수 14% + 지방 1.4% (연 2천만 이하 분리과세)
}

REGIMES = {
    "none":       {"label": "감면 없음(상품중개업 등)", "sme": 0.0, "startup": 0.0},
    "sme10":      {"label": "중기특별감면 10%",        "sme": 0.10, "startup": 0.0},
    "startup50":  {"label": "창업감면 50%(최저한세 적용)", "sme": 0.0, "startup": 0.50},
    "startup75":  {"label": "창업감면 75%(2026 개편안)", "sme": 0.0, "startup": 0.75},
    "startup100": {"label": "청년창업감면 100%(비수도권)", "sme": 0.0, "startup": 1.00},
}

@dataclass
class CsoInputs:
    monthly_profit: float            # 월 순이익(본인 보험·세금 전)
    monthly_revenue: float | None = None  # 수수료 매출(공급가액). 모르면 순이익과 같다고 둠
    regime: str = "none"
    dependents: int = 0
    yellow_umbrella: bool = True
    hi_property_points: float = 0
    label: str = ""

# ------------------------------------------------------------ 개인사업자
def min_tax(calc_tax: float) -> float:
    s = P2["min_tax_split"]
    return P2["min_tax_low"] * min(calc_tax, s) + P2["min_tax_high"] * max(calc_tax - s, 0)

def compute_sole(i: CsoInputs) -> dict:
    reg = REGIMES[i.regime]
    revenue = (i.monthly_revenue or i.monthly_profit) * 12
    profit = i.monthly_profit * 12

    hi = 0.0
    for _ in range(30):
        bi = profit - hi
        hi_new = health_insurance_monthly(bi / 12, i.hi_property_points) * 12
        if abs(hi_new - hi) < 1:
            break
        hi = hi_new
    bi = profit - hi
    np_ = national_pension_monthly(bi / 12) * 12 if bi > 0 else 0.0
    yellow = min(yellow_cap(bi), max(bi, 0)) if i.yellow_umbrella else 0.0
    deductions = PARAMS["basic_deduction"] + i.dependents * PARAMS["dependent_deduction"] + np_ + yellow
    taxable = max(bi - deductions, 0)
    calc = income_tax(taxable)

    reduction = calc * (reg["startup"] or reg["sme"])
    after_red = calc - reduction
    floor = 0.0 if reg["startup"] >= 1.0 else min_tax(calc)   # 100% 창업감면은 최저한세 배제
    if reg["startup"] or reg["sme"]:
        after_red = max(after_red, floor)
    credits = PARAMS["standard_tax_credit"] + PARAMS["e_filing_credit"]
    national = max(after_red - credits, 0)
    local = national * PARAMS["local_tax_rate"]
    tax = national + local
    net = bi - np_ - tax
    return {
        "label": i.label or f"개인 / 월순익 {won(i.monthly_profit)} / {reg['label']}",
        "type": "sole", "inputs": asdict(i),
        "revenue": revenue, "profit": profit, "health_insurance": hi, "business_income": bi,
        "national_pension": np_, "yellow_umbrella": yellow, "taxable_income": taxable,
        "calc_tax": calc, "reduction": calc - after_red, "income_tax_total": tax,
        "vat_passthrough": revenue * PARAMS["vat_rate"],
        "effective_rate": tax / bi if bi > 0 else 0,
        "net_cash_annual": net, "net_cash_monthly": net / 12,
        "double_entry_required": revenue >= 75_000_000,
        "faithful_report_required": revenue >= 500_000_000,
    }

# ------------------------------------------------------------ 법인 + 대표 급여
def earned_income_deduction(gross: float) -> float:
    prev_cap = 0
    for cap, rate, acc in P2["earned_income_deduction"]:
        if gross <= cap:
            return min(acc + (gross - prev_cap) * rate, P2["earned_income_deduction_cap"])
        prev_cap = cap
    raise AssertionError

def earned_income_credit(calc_tax: float, gross: float) -> float:
    c = calc_tax * 0.55 if calc_tax <= 1_300_000 else 715_000 + (calc_tax - 1_300_000) * 0.30
    if gross <= 33_000_000: cap = 740_000
    elif gross <= 70_000_000: cap = max(740_000 - (gross - 33_000_000) * 0.008, 660_000)
    elif gross <= 120_000_000: cap = max(660_000 - (gross - 70_000_000) * 0.5, 500_000)
    else: cap = max(500_000 - (gross - 120_000_000) * 0.5, 200_000)
    return min(c, cap)

def corp_tax(taxable: float) -> float:
    if taxable <= 0: return 0.0
    for cap, rate, deduct in P2["corp_brackets"]:
        if taxable <= cap: return taxable * rate - deduct
    raise AssertionError

def compute_corp(monthly_profit: float, monthly_salary: float, dependents: int = 0,
                 withdraw_dividend: bool = False, label: str = "") -> dict:
    profit = monthly_profit * 12
    salary = monthly_salary * 12
    np_base = min(max(monthly_salary, PARAMS["np_income_floor"]), PARAMS["np_income_cap"]) * 12
    er_social = np_base * P2["er_np"] + salary * (P2["er_hi"] * (1 + PARAMS["ltc_rate_of_hi"]) + P2["er_ei"] + P2["er_wc"])
    corp_taxable = max(profit - salary - er_social, 0)
    ctax = corp_tax(corp_taxable) * (1 + P2["corp_local_rate"])
    retained = corp_taxable - ctax

    emp_social = np_base * P2["emp_np"] + salary * (P2["emp_hi"] * (1 + PARAMS["ltc_rate_of_hi"]) + P2["emp_ei"])
    eid = earned_income_deduction(salary)
    deductions = PARAMS["basic_deduction"] + dependents * PARAMS["dependent_deduction"] + np_base * P2["emp_np"]
    taxable = max(salary - eid - deductions, 0)
    calc = income_tax(taxable)
    national = max(calc - earned_income_credit(calc, salary) - PARAMS["standard_tax_credit"], 0)  # 표준세액공제 13만(근로자)은 보수적으로 7만
    wtax = national * (1 + PARAMS["local_tax_rate"])
    take_home = salary - emp_social - wtax

    dividend_net = retained * (1 - P2["dividend_tax"]) if withdraw_dividend else 0.0
    personal_cash = take_home + dividend_net
    return {
        "label": label or f"법인 / 월순익 {won(monthly_profit)} / 급여 {won(monthly_salary)}" + (" / 전액배당" if withdraw_dividend else " / 유보"),
        "type": "corp",
        "profit": profit, "salary": salary, "employer_social": er_social,
        "corp_taxable": corp_taxable, "corp_tax": ctax, "retained_after_tax": retained,
        "employee_social": emp_social, "salary_tax": wtax, "take_home": take_home,
        "dividend_net": dividend_net,
        "total_tax_and_social": ctax + er_social + emp_social + wtax + (retained - dividend_net if withdraw_dividend else 0),
        "personal_cash_monthly": personal_cash / 12,
        "retained_monthly": (0 if withdraw_dividend else retained) / 12,
        "net_cash_monthly": (personal_cash + (0 if withdraw_dividend else retained)) / 12,
    }

# ------------------------------------------------------------ 출력
SOLE_ROWS = [
    ("연 순이익(입력)", "profit"), ("건강보험+장기요양(필요경비)", "health_insurance"),
    ("= 사업소득금액", "business_income"), ("국민연금(소득공제)", "national_pension"),
    ("노란우산(소득공제)", "yellow_umbrella"), ("과세표준", "taxable_income"),
    ("산출세액", "calc_tax"), ("감면액(최저한세 반영)", "reduction"),
    ("소득세+지방세", "income_tax_total"), ("= 연 가용현금", "net_cash_annual"), ("= 월 가용현금", "net_cash_monthly"),
]
CORP_ROWS = [
    ("연 순이익(급여 전)", "profit"), ("대표 급여(연)", "salary"), ("법인 부담 4대보험", "employer_social"),
    ("법인 과세표준", "corp_taxable"), ("법인세+지방세", "corp_tax"), ("법인 세후 유보", "retained_after_tax"),
    ("본인 부담 4대보험", "employee_social"), ("근로소득세+지방세", "salary_tax"), ("급여 실수령(연)", "take_home"),
    ("배당 실수령(연)", "dividend_net"),
    ("= 월 개인 현금", "personal_cash_monthly"), ("= 월 법인 유보", "retained_monthly"), ("= 월 합계(개인+유보)", "net_cash_monthly"),
]

def table(results, rows):
    out = ["| 항목 | " + " | ".join(r["label"] for r in results) + " |", "|---|" + "|".join("---:" for _ in results) + "|"]
    for name, key in rows:
        out.append(f"| {name} | " + " | ".join(won(r[key]) for r in results) + " |")
    if rows is SOLE_ROWS:
        out.append("| 실효부담률(소득금액 대비) | " + " | ".join(f"{r['effective_rate']*100:.1f}%" for r in results) + " |")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profit", type=float, nargs="*", default=[20_000_000, 30_000_000], help="월 순이익(원)")
    ap.add_argument("--regimes", nargs="*", default=list(REGIMES), help=f"감면 유형: {', '.join(REGIMES)}")
    ap.add_argument("--salary", type=float, nargs="*", default=[5_000_000, 10_000_000], help="법인 대표 월급여(원)")
    ap.add_argument("--dependents", type=int, default=0)
    ap.add_argument("--no-yellow", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    sole = [compute_sole(CsoInputs(monthly_profit=p, regime=r, dependents=a.dependents, yellow_umbrella=not a.no_yellow))
            for p in a.profit for r in a.regimes]
    corp = [compute_corp(p, s, a.dependents, d) for p in a.profit for s in a.salary for d in (False, True)]
    if a.json:
        print(json.dumps({"sole": sole, "corp": corp}, ensure_ascii=False, indent=2)); return
    print("## 개인사업자\n"); print(table(sole, SOLE_ROWS))
    print("\n## 법인 + 대표 급여\n"); print(table(corp, CORP_ROWS))

if __name__ == "__main__":
    main()
