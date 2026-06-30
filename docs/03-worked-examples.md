# 03. 실전 사례 & 손실 계산 공식 (Worked Examples & Loss Formulas)

[← 목차로 (Back to index)](../README.md)

---

강의에 등장한 **온라인 쇼핑몰** 사례의 숫자를 공식으로 정리합니다. 마그네틱 세일즈의 ②문제 인식과
③문제 심화는 이 계산을 **고객과 함께** 수행하는 것이 핵심입니다.

This formalizes the numbers from the lecture's **online shopping mall** example. The core of Steps
②–③ is to run this math **together with the customer**.

---

## 기본 공식 (Base Formulas)

```
월 매출 (Monthly revenue) = 광고 트래픽으로 만든 결제 × 객단가
순익 (Net profit)        = 월 매출 − 광고비 − 기타 비용
손실 (Loss)             = 개선 시 순익 − 현재 순익
```

> 핵심 변수는 **전환율(conversion rate)** 입니다. 전환율이 4배가 되면 같은 광고비로 매출이 4배가 됩니다.
> The key lever is the **conversion rate** — 4× conversion = 4× revenue at the same ad spend.

---

## 사례 데이터 (Case Data)

| 항목 (Item) | 값 (Value) |
|---|---|
| 월 광고비 (Monthly ad spend) | 300만원 |
| 현재 전환율 (Current conversion) | 0.5% |
| 목표/경쟁사 전환율 (Target conversion) | 2% (4배) |

---

## 매출 비교 (Revenue Comparison)

| 구분 (Case) | 전환율 | 월 매출 (Monthly revenue) |
|---|---|---|
| 현재 (Current) | 0.5% | **500만원** |
| 경쟁사/개선 (Improved) | 2% | **2,000만원** |
| **차이 (Gap)** | — | **월 1,500만원 (₩15M/mo)** |

---

## 순익 비교 (Net Profit Comparison)

| 구분 (Case) | 전환율 | 순익 (Net profit) |
|---|---|---|
| 현재 (Current) | 0.5% | **200만원** |
| 개선 (Improved) | 2% | **1,700만원** |
| **차이 (Gap)** | — | **월 1,500만원** |

> 매출 차이와 순익 차이가 모두 **월 1,500만원**으로 수렴 — 이 한 숫자가 전체 설득의 앵커입니다.
> Both the revenue gap and profit gap converge on **₩15M/month** — the single anchor number.

---

## 손실의 시간 단위 분해 (Loss Broken Down by Time)

③ 문제 심화에서 사용하는 **실시간 출혈** 수치입니다.
The **real-time bleed** figures used in Step ③.

| 단위 (Unit) | 손실 (Loss) | 계산 (Calculation) |
|---|---|---|
| 월 (Month) | 1,500만원 | 기준값 (base) |
| 하루 (Day) | 50만원 | 1,500만원 ÷ 30 |
| 시간 (Hour) | 2만원 | 50만원 ÷ 24 (≈) |
| 분 (Minute) | 333원 | 2만원 ÷ 60 (≈) |

> 활용 멘트: **"우리가 대화하는 10분 동안 3,330원이 사라졌습니다..!"** (333원 × 10분)
> Line: *"In the 10 minutes we've talked, ₩3,330 just disappeared."*

---

## 장기 누적 손실 (Long-Term Cumulative Loss)

| 기간 (Period) | 손실 (Loss) |
|---|---|
| 1개월 (1 month) | 1,500만원 |
| 1년 (1 year) | 1억 8,000만원 (₩180M) |
| 5년 (5 years) | 9억원 (₩900M) |

### 9억원의 기회비용 (What ₩900M Could Buy)

- 🏢 강남 아파트 한 채 (A Gangnam apartment)
- 🎓 자녀 유학비 전액 (Kids' full study-abroad)
- 👴 편안한 은퇴 자금 (A comfortable retirement)

> 손실을 **기회비용**으로 번역하면, 추상적 숫자가 **개인적 고통**으로 바뀝니다.
> Translating loss into opportunity cost turns an abstract figure into **personal pain**.

---

## Before / After 성과 (Results Trajectory)

| 월 (Month) | 매출 (Revenue) | 비고 |
|---|---|---|
| 6월 (Before) | 500만원 | 시작점 |
| 7월 | 1,200만원 | — |
| 8월 (After) | 2,000만원 | 4배 성과 (4×) |

> "3개월 뒤, 4배 성과로!" — 작은 결정의 누적 임팩트를 보여주는 마무리 그래프.
> *"4× results in 3 months!"* — the closing graph showing compounding impact.

---

## 가격 앵커링 (Price Anchoring)

| 비교 대상 (Compared against) | 금액 (Amount) |
|---|---|
| 1년 손실 (1-year loss) | 1억 8,000만원 |
| 8주 후 통장 (Future balance) | 8,000만원 |
| **해결책 가격 (Solution price)** | **300만원** |

> 1.8억 손실·8천만원 미래 옆에 놓인 **300만원**은 비용이 아니라 **투자**로 인식됩니다.
> Next to ₩180M of loss and ₩80M of upside, **₩3M** reads as an **investment**, not a cost.

[← 목차로 (Back to index)](../README.md)
