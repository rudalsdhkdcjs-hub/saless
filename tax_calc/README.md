# tax_calc — 의약품 도매업 개인사업자 가용현금 계산기

`pharma_tax_calc.py`(도매업·매출 기준)와 `cso_net_cash.py`(CSO·순이익 기준, 개인 vs 법인), `cso_plan.py`(차량·판촉·가족급여·연금 반영 생활가용)로 구성 (표준 라이브러리만 사용).
제도값은 파일 상단 `PARAMS`, 입력은 `Inputs` 데이터클래스.
가정·출처·결과 해석은 `work_log/` 의 최신 기록 참조.

```bash
python3 pharma_tax_calc.py --help
```
