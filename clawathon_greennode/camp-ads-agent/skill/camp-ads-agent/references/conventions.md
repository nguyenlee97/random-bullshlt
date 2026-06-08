# Conventions — chi tiết để sinh code đúng

## call_llm contract
```python
call_llm(task: str, messages: list, *, json_schema=None, temperature=None) -> str
call_llm_json(task: str, messages: list, schema: dict, *, retries=1) -> dict
```
- `task` PHẢI là 1 key trong `config/models.yaml::tasks`.
- `call_llm_json` strip ```json fences, parse, và nếu fail thì append message "CHỈ trả JSON theo schema" rồi gọi lại tối đa `retries` lần.

## models.yaml — task keys cố định
`brief_parse, creative, segment_explain, setup_plan, report_explain, ao_alert`
Mỗi task: `{ model: "<path trên MaaS>", temperature: <float> }`.

## Pydantic schemas (nguồn chân lý cho JSON)
```python
Target(age, gender, location, interests:list, behaviors:list=[])
Brief(brand, objective, funnel_stage:Literal["awareness","consideration","conversion"],
      target:Target, budget_vnd:int, flight, kpi:list, format:list)
Segment(matched:list, size_est:str, gaps:list, explain:str="")
CampVerdict(camp_id, verdict:Literal["good","watch","bad"], reason)
AgentOutput(brief, segment, setup_plan:dict, kpi_target:dict,
            report_eval:list[CampVerdict], ao_alert:str)
```

## Ngưỡng phân loại mẫu (logic/thresholds.py)
```python
RULES = {"ctr_good":0.015,"ctr_bad":0.005,"cpc_bad":3000,"cr_good":0.02,"cr_bad":0.005}
# good: ctr>=ctr_good AND cr>=cr_good
# bad : ctr<ctr_bad OR cpc>cpc_bad OR cr<cr_bad
# else: watch
```

## KPI theo funnel (logic/kpi_table.py)
```python
KPI = {
 "awareness":   ["Reach","Impressions","CPM","VTR","Frequency"],
 "consideration":["CTR","Engagement","CPV"],
 "conversion":  ["Leads","CR","CPL","ROAS"],
}
```

## dmp_match (logic/dmp_match.py)
- Load `data/dmp_taxonomy.csv`.
- Lowercase + fuzzy match interest brief với cột `interest`.
- matched = interest có trong taxonomy; gaps = interest KHÔNG có.
- size_est = tổng [size_low, size_high] của matched, format "x.xM - y.yM".

## Mẫu prompt: xem ../../handoff/03_PROMPT_LIBRARY.md (nguồn đầy đủ, copy y nguyên).

## Eval: xem ../../handoff/04_EVAL_SET.md (18 case + runner).

## Khi tạo file mới, luôn:
1. Thêm/ cập nhật schema tương ứng.
2. Thêm eval case cho hành vi mới.
3. Chạy `python -m evals.run` trước khi báo xong.
