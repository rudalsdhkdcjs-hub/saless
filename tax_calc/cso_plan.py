#!/usr/bin/env python3
"""
CSO 개인사업자 — 차량·판촉비·가족급여·연금까지 넣은 "수중에 남는 돈" 계산기 (2026)
===================================================================================
입력 월 영업이익 = 수수료 매출 − 소액 운영비(통신·기장료 등). 차량·판촉·가족급여·본인 보험·세금 차감 전.
출력: 세무상 소득/세금과 별도로 **실제 현금흐름**(할부 원리금, 판촉 지출, 적립)을 구분해 보여준다.
"""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, asdict
from pharma_tax_calc import PARAMS, income_tax, yellow_cap, national_pension_monthly, health_insurance_monthly, won
from cso_net_cash import P2, min_tax, earned_income_deduction, earned_income_credit

CAR = {
    "없음": 0,
    "기존차(내연기관, 보유)": 0,
    "폴스타4 싱글":   66_900_000, "폴스타4 듀얼": 71_900_000,
    "G80 전동화":    89_190_000,
    "모델Y RWD":     57_000_000,
    "EV3 롱레인지":   47_000_000,
    "아이오닉6 롱레인지": 52_000_000,
    "EV6 롱레인지":   53_000_000,
    "아이오닉5 롱레인지": 54_000_000,
    "아이오닉9":      67_000_000,
    "GV60":          68_000_000,
    "EV9":           75_000_000,
    "GV70 전동화":    77_000_000,
    "모델Y 롱레인지 AWD": 64_000_000,
    "폴스타3 리어":   77_900_000, "폴스타3 듀얼": 85_900_000, "폴스타3 퍼포먼스": 99_900_000,
}
EFF = {  # 복합전비 km/kWh (인증값; 실주행은 겨울 포함 약 15% 낮게 봄)
    "폴스타4 싱글": 4.6, "폴스타4 듀얼": 4.2, "G80 전동화": 4.5, "모델Y RWD": 5.5, "EV3 롱레인지": 5.4, "아이오닉6 롱레인지": 5.8, "EV6 롱레인지": 5.2, "아이오닉5 롱레인지": 4.9, "아이오닉9": 4.1, "GV60": 4.6, "EV9": 4.0, "GV70 전동화": 4.3, "모델Y 롱레인지 AWD": 5.0, "폴스타3 리어": 4.0, "폴스타3 듀얼": 3.8, "폴스타3 퍼포먼스": 3.6,
}
P3 = {
    "dep_years": 5,                 # 업무용승용차 5년 정액 강제
    "dep_cap": 8_000_000,           # 감가상각 연 800만 한도(초과 이월)
    "nologbook_cap": 15_000_000,    # 운행기록부 미작성 시 관련비용 연 1,500만 한도
    "ent_base": 36_000_000, "ent_rate": 0.003,   # 기업업무추진비 한도
    "pension_credit_rate": 0.132,   # 종합소득 4,500만 초과
    "pension_cap": 9_000_000,
    "ev_tax_relief": 5_300_000,     # 개소세 300 + 교육세 90 + 취득세 140 (2026.12.31까지, 확인 필요)
}

@dataclass
class Plan:
    monthly_profit: float
    car: str = "폴스타4 듀얼"
    car_apr: float = 0.059           # 풀할부 금리(가정)
    car_months: int = 60
    option_price: float = 0          # 옵션 추가금
    km_per_year: float = 50_000
    won_per_kwh: float = 220         # 집 완속 위주(150~200) + 일부 급속(350~393) 혼합
    real_eff_factor: float = 0.85    # 인증 전비 대비 실주행 보정
    insurance: float = 1_800_000
    maintenance: float = 500_000     # 정비·세차·소모품(타이어 제외)
    tire_set_price: float = 1_500_000
    tire_life_km: float = 40_000
    car_tax: float = 130_000         # 전기차 자동차세
    ice_fuel_km_per_l: float = 14.0  # 기존차 연비(스포티지 디젤)
    ice_fuel_won_per_l: float = 1_550  # 경유
    ice_maintenance: float = 1_500_000  # 기존차 정비·타이어(고주행)
    ice_insurance: float = 1_000_000
    ice_car_tax: float = 400_000
    logbook: bool = False            # 운행기록부 작성 여부
    biz_ratio: float = 1.0           # 운행기록부 작성 시 업무사용비율
    subsidy: float = 1_500_000       # 전기차 보조금(지자체 포함, 차량가 8,500만 미만만)
    promo_monthly: float = 3_000_000 # 판촉·접대 지출(제약사 담당자 등, 의료인 제외)
    promo_evidence: bool = True      # 적격증빙(사업용카드) 여부
    family_salary_monthly: float = 0 # 가족 직원 급여
    spouse_was_dependent: bool = True
    pension: float = 9_000_000       # 연금저축+IRP
    yellow: bool = True
    dependents: int = 0
    sme10: bool = False              # 중소기업특별세액감면 10%(상품중개업=도매 분류 시)
    label: str = ""

def amortization_year1(principal, apr, months):
    r = apr / 12
    pay = principal * r / (1 - (1 + r) ** -months)
    bal, interest = principal, 0.0
    for _ in range(12):
        i = bal * r; interest += i; bal -= pay - i
    return pay * 12, interest

def compute(p: Plan) -> dict:
    profit = p.monthly_profit * 12
    revenue = profit  # 보수적: 접대비 한도 계산용 수입금액

    # ---- 차량
    price = CAR[p.car]
    if p.car == "기존차(내연기관, 보유)":
        net_price, pay_y1, int_y1, dep, dep_allowed, dep_carry = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        other = (p.km_per_year / p.ice_fuel_km_per_l * p.ice_fuel_won_per_l + p.ice_maintenance + p.ice_insurance + p.ice_car_tax)
    elif price:
        net_price = max(price + p.option_price - p.subsidy - P3["ev_tax_relief"] + p.option_price * 0.07, 0)  # 옵션분 취득세 7%
        pay_y1, int_y1 = amortization_year1(net_price, p.car_apr, p.car_months)
        dep = net_price / P3["dep_years"]
        dep_allowed = min(dep, P3["dep_cap"]); dep_carry = dep - dep_allowed
        charge = p.km_per_year / (EFF[p.car] * p.real_eff_factor) * p.won_per_kwh
        tires = p.km_per_year / p.tire_life_km * p.tire_set_price
        other = charge + tires + p.insurance + p.maintenance + p.car_tax
    else:
        net_price = pay_y1 = int_y1 = dep = dep_allowed = dep_carry = other = 0.0
    related = dep_allowed + int_y1 + other
    car_expense = related * p.biz_ratio if p.logbook else min(related, P3["nologbook_cap"])
    car_cash = pay_y1 + other
    car_charge = (p.km_per_year / (EFF[p.car] * p.real_eff_factor) * p.won_per_kwh) if p.car in EFF else 0.0

    # ---- 판촉·접대
    promo = p.promo_monthly * 12
    ent_cap = P3["ent_base"] + revenue * P3["ent_rate"]
    promo_expense = min(promo, ent_cap) if p.promo_evidence else 0.0

    # ---- 가족 급여
    fam = p.family_salary_monthly * 12
    fam_np_base = min(max(p.family_salary_monthly, PARAMS["np_income_floor"]), PARAMS["np_income_cap"]) * 12
    er_social = (fam_np_base * P2["er_np"] + fam * (P2["er_hi"] * (1 + PARAMS["ltc_rate_of_hi"]) + P2["er_ei"] + P2["er_wc"])) if fam else 0.0
    emp_social = (fam_np_base * P2["emp_np"] + fam * (P2["emp_hi"] * (1 + PARAMS["ltc_rate_of_hi"]) + P2["emp_ei"])) if fam else 0.0
    fam_tax = 0.0
    if fam:
        tb = max(fam - earned_income_deduction(fam) - PARAMS["basic_deduction"] - fam_np_base * P2["emp_np"], 0)
        c = income_tax(tb)
        fam_tax = max(c - earned_income_credit(c, fam) - PARAMS["standard_tax_credit"], 0) * (1 + PARAMS["local_tax_rate"])
    dependents = p.dependents - (1 if (fam and p.spouse_was_dependent and p.dependents > 0) else 0)

    # ---- 사업소득 (건보 순환)
    opex = car_expense + promo_expense + fam + er_social
    hi = 0.0
    for _ in range(40):
        bi = profit - opex - hi
        hi_new = health_insurance_monthly(bi / 12, 0) * 12
        if abs(hi_new - hi) < 1: break
        hi = hi_new
    bi = profit - opex - hi
    np_ = national_pension_monthly(bi / 12) * 12 if bi > 0 else 0.0
    yellow = min(yellow_cap(bi), max(bi, 0)) if p.yellow else 0.0
    taxable = max(bi - PARAMS["basic_deduction"] - dependents * PARAMS["dependent_deduction"] - np_ - yellow, 0)
    calc = income_tax(taxable)
    after = max(calc * 0.9, min_tax(calc)) if p.sme10 else calc
    pension_credit = min(p.pension, P3["pension_cap"]) * P3["pension_credit_rate"] if taxable > 0 else 0.0
    national = max(after - PARAMS["standard_tax_credit"] - PARAMS["e_filing_credit"] - pension_credit, 0)
    tax = national * (1 + PARAMS["local_tax_rate"])

    # ---- 현금흐름
    savings = yellow + min(p.pension, P3["pension_cap"])
    owner_cash = profit - promo - car_cash - fam - er_social - hi - np_ - tax
    family_cash = fam - emp_social - fam_tax
    household_cash = owner_cash + family_cash
    spendable = owner_cash - savings
    return {
        "label": p.label or f"{won(p.monthly_profit)}/월 · {p.car} · 판촉{won(p.promo_monthly)} · 가족급여{won(p.family_salary_monthly)}" + (" · 중기10%" if p.sme10 else ""),
        "inputs": asdict(p),
        "car_net_price": net_price, "car_pay_y1": pay_y1, "car_other": other, "car_charge": car_charge, "car_related": related, "car_interest_y1": int_y1, "car_expense": car_expense, "dep_carry": dep_carry, "car_cash": car_cash,
        "promo": promo, "promo_expense": promo_expense, "ent_cap": ent_cap,
        "family_salary": fam, "employer_social": er_social, "family_social": emp_social, "family_tax": fam_tax, "family_cash": family_cash,
        "health_insurance": hi, "business_income": bi, "national_pension": np_, "yellow": yellow, "taxable": taxable,
        "calc_tax": calc, "pension_credit": pension_credit, "income_tax_total": tax,
        "owner_cash": owner_cash, "savings": savings, "spendable": spendable, "household_cash": household_cash,
        "owner_cash_m": owner_cash / 12, "spendable_m": spendable / 12, "household_cash_m": household_cash / 12,
        "tax_saved_vs_noexpense": None,
    }

ROWS = [
    ("연 영업이익(입력)", "profit_in"),
    ("차량 실구매가(보조금·세제 후)", "car_net_price"),
    ("차량 유지비(충전·타이어·보험·정비·세금)", "car_other"),
    ("  └ 그중 충전비", "car_charge"),
    ("차량 관련비용 합계(감가 800만 한도 적용)", "car_related"),
    ("차량 경비 인정", "car_expense"),
    ("  └ 매년 이월되는 감가상각", "dep_carry"),
    ("차량 현금 지출(할부 원리금+유지)", "car_cash"),
    ("판촉·접대 지출", "promo"),
    ("  └ 경비 인정", "promo_expense"),
    ("가족 급여 + 사업주 4대보험", "fam_total"),
    ("건강보험(필요경비)", "health_insurance"),
    ("= 사업소득금액", "business_income"),
    ("국민연금", "national_pension"),
    ("과세표준", "taxable"),
    ("소득세+지방세(연금공제 후)", "income_tax_total"),
    ("= 본인 수중 현금(연)", "owner_cash"),
    ("  └ 그중 적립(노란우산+연금)", "savings"),
    ("= 본인 생활가용(월)", "spendable_m"),
    ("가족 실수령(월)", "family_cash_m"),
    ("= 가구 합계(월, 적립 포함)", "household_cash_m"),
]

def table(rs):
    for r in rs:
        r["profit_in"] = r["inputs"]["monthly_profit"] * 12
        r["fam_total"] = r["family_salary"] + r["employer_social"]
        r["family_cash_m"] = r["family_cash"] / 12
    out = ["| 항목 | " + " | ".join(r["label"] for r in rs) + " |", "|---|" + "|".join("---:" for _ in rs) + "|"]
    for n, k in ROWS:
        out.append(f"| {n} | " + " | ".join(won(r[k]) for r in rs) + " |")
    return "\n".join(out)

def scenarios(profit):
    return [
        Plan(profit, car="없음", promo_monthly=0, pension=0, yellow=False, label=f"{won(profit)} · 차·판촉·적립 없음(기준선)"),
        Plan(profit, car="기존차(내연기관, 보유)", label=f"{won(profit)} · 기존차 유지 · 판촉300 · 적립풀"),
        Plan(profit, car="폴스타4 듀얼", option_price=10_000_000, logbook=False, label=f"{won(profit)} · 폴스타4 듀얼+옵션1000 · 운행기록부 X"),
        Plan(profit, car="폴스타4 듀얼", option_price=10_000_000, logbook=True, biz_ratio=0.9, label=f"{won(profit)} · 폴스타4 듀얼+옵션1000 · 운행기록부 O(90%)"),
        Plan(profit, car="폴스타3 듀얼", option_price=10_000_000, subsidy=0, logbook=True, biz_ratio=0.9, label=f"{won(profit)} · 폴스타3 듀얼+옵션1000 · 운행기록부 O(90%)"),
        Plan(profit, car="폴스타4 듀얼", option_price=10_000_000, logbook=True, biz_ratio=0.9, family_salary_monthly=2_500_000, spouse_was_dependent=False, label=f"{won(profit)} · 폴스타4(기록부O) + 배우자급여250"),
    ]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profit", type=float, nargs="*", default=[20_000_000, 30_000_000], help="월 영업이익(차·판촉 차감 전)")
    ap.add_argument("--deposit", type=float, nargs="*", help="월 입금액(부가세 포함 수수료). 지정 시 --profit 무시: 영업이익 = 입금/1.1 − 운영비")
    ap.add_argument("--misc", type=float, default=250_000, help="월 소액 운영비(통신·기장료·소모품), --deposit 와 함께 사용")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    profits = a.profit
    if a.deposit:
        profits = [d / 1.1 - a.misc for d in a.deposit]
        for d, p in zip(a.deposit, profits):
            print(f"입금 {won(d)}/월(부가세 포함) → 공급가액 {won(d/1.1)} → 부가세 {won(d - d/1.1)} 별도 보관 → 운영비 {won(a.misc)} 차감 → 영업이익 {won(p)}")
    for pr in profits:
        rs = [compute(p) for p in scenarios(pr)]
        if a.json: print(json.dumps(rs, ensure_ascii=False, indent=2)); continue
        print(f"\n### 월 영업이익 {won(pr)}\n"); print(table(rs))

if __name__ == "__main__":
    main()
