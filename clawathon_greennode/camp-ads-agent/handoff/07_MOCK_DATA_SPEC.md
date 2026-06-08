# 07 · Mock Data Spec — dữ liệu giả lập trông như thật

Cuộc thi cấm API production → mock toàn bộ. Mock càng giống thật, điểm "khả thi" càng cao. Nguồn tham chiếu: file `Brief Sample.xlsx` của đội.

## 1. Brief mẫu (2 file `data/briefs/*.json`)

### Brand A — Awareness funnel
```json
{"brand":"Brand A","industry":"Tài chính - Du lịch",
 "objective":"Tăng nhận biết với nhóm có ý định du lịch khu vực SEA",
 "funnel_stage":"awareness",
 "target":{"age":"18+","gender":"all","location":"NAT, ưu tiên HCM/HN/ĐN",
   "interests":["Travel","Air travel","Hotels","Personal finance","Credit cards","Technology"],
   "behaviors":["pre-travel signal","traveler destination signal: SG/TH/MY/ID/PH"]},
 "budget_vnd":425000000,"flight":"4 tuần",
 "kpi":["Reach","Impressions","CPM","VTR","Frequency"],
 "format":["Display banner","Video skippable"]}
```

### Brand B — Conversion funnel
```json
{"brand":"Brand B","industry":"Bảo hiểm - Tài chính",
 "objective":"Thu lead đăng ký tư vấn gói bảo hiểm sức khỏe",
 "funnel_stage":"conversion",
 "target":{"age":"25-45","gender":"all","location":"NAT",
   "interests":["Health","Insurance","Finance"],
   "behaviors":["đã tương tác form bảo hiểm","retargeting truy cập landing"]},
 "budget_vnd":150000000,"flight":"3 tuần",
 "kpi":["Leads","Conversion Rate","CPL","ROAS"],
 "format":["Lead form native","Retargeting"]}
```
> Cố tình để Brand B có interest **Insurance, Du học** → kích hoạt tính năng "báo gap DMP".

## 2. Taxonomy DMP (`data/dmp_taxonomy.csv`)
Lấy từ sheet `interest & behaviors` của `Brief Sample.xlsx` (~300 dòng). Cột:
```
interest, category, size_low, size_high
Travel, Travel & tourism, 1500000, 1900000
Air travel, Transportation, 800000, 1100000
Credit cards, Finance, 600000, 850000
...
```
- `dmp_match()` so interest brief với cột `interest` (lowercase, fuzzy).
- Interest brief KHÔNG có trong file = **gap** (vd "Insurance", "Du học", "pre-travel signal SEA").
- `size_est` = tổng `size_low`–`size_high` của các interest matched.

## 3. Report 500 camps (`data/camps_report.csv`)
Schema:
```
camp_id, brand, zone, format, impressions, clicks, ctr, spend_vnd, cpc, conversions, cr, date
C0001, Brand A, news_home, banner, 120000, 1800, 0.015, 5400000, 3000, 36, 0.020, 2026-06-12
```
Quy tắc sinh (script `data/gen_camps.py`):
- 500 dòng, phân bố ~60% good/watch, ~40% bad (đủ để demo thấy "cần cứu").
- `ctr` ~ Beta để có đuôi xấu; `cpc = spend/clicks`; `cr = conversions/clicks`.
- Vài camp cố tình cực xấu (ctr<0.003, cpc>4000) để hero bước 5 nổi bật.
- Số liệu hợp lý theo ngành (CPM/CPC VN), không random vô nghĩa.

```python
# data/gen_camps.py (rút gọn)
import csv, random
def gen(n=500):
    rows=[]
    for i in range(1,n+1):
        imp=random.randint(20000,300000)
        ctr=max(0.001, random.betavariate(2,120))
        clicks=int(imp*ctr); cpc=random.randint(1500,5000)
        spend=clicks*cpc; cr=max(0.0005,random.betavariate(2,90))
        conv=int(clicks*cr)
        rows.append([f"C{i:04d}","Brand A" if i%2 else "Brand B",
            random.choice(["news_home","entertain","sports","finance"]),
            random.choice(["banner","video","native"]),
            imp,clicks,round(ctr,4),spend,cpc,conv,round(cr,4),"2026-06-12"])
    return rows
```

## 4. Eval cases (`evals/cases.jsonl`)
Dựng theo [04_EVAL_SET](04_EVAL_SET.md) — 18 case. Data phải nhất quán với 2 brief & report ở trên.

## 5. Checklist mock data
- [ ] 2 brief JSON (1 awareness, 1 conversion) — có sẵn gap ở Brand B.
- [ ] taxonomy DMP ~300 interest + size.
- [ ] 500 camps CSV, phân bố good/bad hợp lý, có vài camp cực xấu.
- [ ] script sinh data tái lập được (seed cố định để demo ổn định).
- [ ] số liệu "trông như thật" (CPM/CPC theo thị trường VN).
