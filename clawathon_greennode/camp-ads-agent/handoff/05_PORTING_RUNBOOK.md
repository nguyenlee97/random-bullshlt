# 05 · Porting Runbook — rebuild trên GreenNode trong 7 ngày

> Tiền đề: pha A đã có repo chạy được + gói handoff này + eval baseline. Pha B chỉ là **đổi model + tinh chỉnh prompt + deploy** — không viết lại.

## Checklist 1 lần (D0, tại training 10/06)
- [ ] Nhận account, MaaS token, gói credit.
- [ ] Hỏi BTC & ghi lại: **giá trị `path` chính xác của 3 model**; base_url MaaS; giới hạn token; voting page test live hay video; được nhúng UI không; được chuẩn bị code trước không.
- [ ] Deploy "hello-world" (`/health` + echo) lên Runtime để chắc hạ tầng thông.

## Swap model — đúng 3 thao tác
1. Set env:
   ```bash
   export MAAS_BASE_URL="https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
   export MAAS_API_KEY="<token từ training>"
   ```
2. Sửa `config/models.yaml` → điền `path` thật của Qwen/Gemma cho từng task.
3. Chạy eval: `python -m evals.run`. Ghi lại 3 chỉ số.

> Không đụng vào `app/steps`, `app/logic`, `app/schemas`. Nếu phải sửa ngoài config/prompt để chạy được → kiến trúc pha A chưa "model-agnostic", quay lại sửa lớp `call_llm`.

## Lịch 7 ngày (gắn với eval gate)
| Ngày | Mục tiêu | Cổng |
|------|----------|------|
| D0 10/06 | Hạ tầng thông + swap model + eval lần 1 | hello-world ACTIVE |
| D1 11/06 | Tinh chỉnh prompt cho bước rớt parity | JSON valid ≥ 90% |
| D2 12/06 | Hero (bước 3,5,6) đạt parity | accuracy ≥ 99%, field ≥ 85% |
| D3 13/06 | End-to-end 6 bước trên model BTC | walking skeleton chạy |
| D4 14/06 | Hoàn thiện bước 1,2,4 + ổn định | chạy 10 lần không lỗi |
| D5 15/06 | Polish UI + con số hiệu quả + mock đẹp | demo "dùng thử ngay" |
| D6 16/06 | Freeze, build Docker, deploy AgentBase, quay video | agent ACTIVE + video |
| D7 17/06 | Nộp sớm (mục tiêu 10:00) | repo public + link sống |

## Khi parity chưa đạt — bậc thang xử lý (theo thứ tự, dừng khi đạt)
1. Hạ `temperature` về 0.0–0.1 cho task đó.
2. Thêm 1–2 few-shot vào đúng prompt bị lệch.
3. Bật `retries=2` ở `call_llm_json`.
4. Đẩy thêm 1 phần logic số/format từ prompt sang Python.
5. Đổi model task đó sang model khác trong 3 model BTC (vd report → Gemma thay vì Qwen).
6. **Không** leo thang sang "đổi kiến trúc" hay "thêm framework".

## Build & deploy
```bash
docker build -t vcr.vngcloud.vn/<backend>/camp-ads-agent:rc1 .
docker push  vcr.vngcloud.vn/<backend>/camp-ads-agent:rc1
# hoặc dùng skill pack BTC:
# /agentbase-wizard  ->  /agentbase-deploy  ->  /agentbase-monitor
```
Kiểm tra sau deploy: `GET /health` = 200; mở voting URL test thử như người lạ.

## Định nghĩa "rebuild thành công"
- [ ] Eval parity đạt gate trên model BTC.
- [ ] Agent ACTIVE, `/health` 200, không hardcode secret.
- [ ] Demo chạy mượt 10 lần, có nút dùng thử + mock nạp sẵn.
- [ ] Video 60–90s + repo README chỉn chu.
