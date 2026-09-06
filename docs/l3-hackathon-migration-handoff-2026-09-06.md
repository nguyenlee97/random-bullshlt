# Handoff: Live Evaluation L3 và chuyển staging sang Hackathon VPS

Ngày bàn giao: 2026-09-06

Repo/worktree: `C:\Users\LENOVO\Downloads\random-bullshlt-evaluation-v4`

Nhánh: `codex/v4-live-evaluation`
Implementation HEAD trước commit tài liệu bàn giao: `7d92f51c460f46a539a4d171df9b04bdc33ee3af`

## 1. Mục tiêu của hội thoại tiếp theo

Hội thoại tiếp theo có hai mục tiêu liên quan nhưng nên thực hiện theo thứ tự:

1. Bảo toàn và chuyển toàn bộ V4 Live Evaluation hiện tại từ staging đang hết hạn sang Hackathon VPS tại `https://zah-4.123c.vn`.
2. Sau khi L1/L2 và các flow nền chạy ổn trên môi trường mới, implement L3 Recovery dùng chung cho Web và Zalo OA, có approval, audit, verification và rollback.

Không cần migrate account/campaign test cũ. Có thể coi Hackathon VPS là môi trường mới, tạo account và campaign/scenario mới để chạy acceptance từ đầu.

## 2. Prompt có thể copy sang hội thoại mới

```text
Tiếp tục dự án từ docs/l3-hackathon-migration-handoff-2026-09-06.md trên nhánh
codex/v4-live-evaluation. Trước tiên hãy kiểm tra lại branch, HEAD, dirty files và
đọc toàn bộ handoff. Production/staging VPS tại *.pawgrammers.io.vn sắp hết hạn,
hãy bảo toàn code và chuyển V4 sang Hackathon VPS https://zah-4.123c.vn bằng
docker-compose.hackathon.yml, giữ nguyên env/token/OA riêng của Hackathon và không
sao chép secret từ IOT Generation. Data/account có thể tạo mới.

Sau khi migration và smoke test thành công, hãy xác nhận Scenario Lab -> L1 -> L2,
UI Campaign Management và Zalo routing không xung đột với FAQ/report/tạo campaign.
Sau đó implement L3 theo hướng fail-closed, human approval, action registry,
idempotency, before/after audit, verification và rollback. Bắt đầu bằng một action
recovery an toàn, nối Web và Zalo vào cùng service, rồi chạy E2E có bằng chứng.
Không được mô tả L3 là hoàn thiện trước khi mutation và verification thực sự chạy.
```

## 3. Trạng thái Git và phạm vi code

Nhánh được tạo từ `v4/production-readiness` tại commit `9732dee`. Toàn bộ chuỗi thay đổi hiện có trong nhánh, không chỉ commit cuối:

1. `f8e4a41` — Live Evaluation vertical slice ban đầu.
2. `56a63a1` — Campaign Management Hub.
3. `398f76d` — sửa scroll campaign page.
4. `afeee20` — giữ history Autopilot read-only có thể scroll.
5. `ad73cc4` — đưa Campaign Management về control-plane contract.
6. `39a28c5` — merge unified campaign management vào nhánh Evaluation.
7. `8b8a0f7` — resumable L2 investigation workspace.
8. `edebbaa` — mở rộng L2 evidence và scenario acceptance.
9. `88ee4ac` — checkpoint release packaging.
10. `6cc54d1` — deploy/acceptance validation.
11. `b127faf` — staging acceptance và mobile Scenario Lab.
12. `d37e7de` — bust mobile analytics layout cache.
13. `836059f` — L2 staging checkpoint documentation.
14. `bc2c236` — Zalo reply isolation và L2 evidence exposure.
15. `709f372` — release diff verification.
16. `1f6fb0b` — owner-scoped campaign deep link.
17. `f0ae69b` — giữ selected campaign qua directory polling.
18. `3c4c789` — render typed evidence contract hiện tại.
19. `2654191` — tách trạng thái thực thi L2 khỏi evidence gap.
20. `41c538d` — hiển thị campaign hoàn thành và pagination.
21. `6bf53ac` — revisioned campaign operations workspace.
22. `7d92f51` — stack campaign config fields thành một cột.

Tại thời điểm bàn giao, nhánh **chưa có trên remote**. `git ls-remote --heads origin codex/v4-live-evaluation` không trả về ref. Việc đầu tiên trước khi staging hết hạn nên là push nhánh:

```powershell
git push -u origin codex/v4-live-evaluation
```

Chỉ push sau khi kiểm tra remote và quyền truy cập đúng. Không đưa các file untracked dưới đây vào commit ngoài ý muốn:

```text
.codex-tmp/
AGENTS.md
KNOWLEDGE_MEMORY_FEATURE_FLOW.md
KNOWLEDGE_MEMORY_TECHNICAL_APPROACH.md
ops/evaluation_vps_zalo_e2e.py
```

`ops/evaluation_vps_zalo_e2e.py` là helper test đã dùng trong quá trình E2E nhưng hiện chưa được track; cần review secrets/output trước khi quyết định commit.

## 4. Những phần đã hoàn thành

### 4.1 Scenario Lab và report dataset

Scenario Lab đã được implement trong Analytics site và được link từ Campaign Management. Hiện có 12 preset. Mỗi lần apply không sửa thẳng phần văn bản report mà thực hiện theo flow:

```text
baseline bất biến
  -> preview scenario từ baseline
  -> tạo ReportDataset revision mới
  -> activate revision
  -> rebuild AnalyticsRecord
  -> rebuild đồng bộ 6 ReportAnalysis
  -> chạy L1 trên đúng revision đó
```

Dataset có revision, input hash, scenario parameters và seed để lặp lại test. Apply/reset có rollback nếu rebuild lỗi. Scenario acceptance contract mô tả incident L1, hypothesis L2 và evidence class mong đợi cho từng preset.

Các file chính:

- `backend/lib/reportScenarios.js`
- `backend/services/reportDatasets.js`
- `backend/models/ReportDataset.js`
- `backend/models/CampaignReportState.js`
- `analytics_frontend/scenario-lab.js`
- `agent/tests/test_scenario_acceptance.py`

Toàn bộ facts của Scenario Lab là dữ liệu giả lập phục vụ test Evaluation. Không được diễn giải creative/render/publisher signal trong scenario như telemetry production thật.

### 4.2 L1 Detect

L1 đã chạy deterministic và tạo/cập nhật incident theo report revision. Các detector hiện có:

- Data-quality gate.
- Under-delivery theo threshold và persistence window.
- CTR regression có minimum sample, relative drop và z-score.
- Pacing lệch thấp/cao.
- Robust trend dùng median/MAD.
- Technical evidence signals cho creative render, click telemetry, config drift và tracking delay.

Incident được deduplicate, có timeline, policy version, dataset revision, recurrence và auto-resolve khi signal không còn tái hiện. API được ownership-scope và các trigger có idempotency. Periodic worker đã có implementation nhưng đang tắt trên staging; hiện Scenario Apply và Run Evaluation là hai trigger chủ yếu.

Các file chính:

- `agent/evaluation/engine.py`
- `agent/evaluation/service.py`
- `agent/evaluation/store.py`
- `agent/evaluation/routes.py`
- `agent/evaluation/worker.py`

### 4.3 L2 Investigate

L2 không còn chỉ đổi state. Nó là investigation job chạy background, resumable và read-only. Orchestrator hiện có năm vai trò:

1. Performance Analyst.
2. Creative Inspector.
3. Placement Investigator.
4. Setup Auditor.
5. Coordinator tổng hợp hypothesis và recommendation.

Mỗi specialist thu thập evidence qua bounded tools/probes. Evidence dùng typed relation:

- `supports`
- `contradicts`
- `context`
- `unavailable`

Contract `evidence-relations-v3` ngăn coordinator suy diễn quá mức. Ví dụ, zero click không tự chứng minh click handler hỏng; placement trong catalog không tự chứng minh còn inventory/bookable; report completeness không tự chứng minh publisher delivery đúng.

Investigation job có lease, resume và checkpoint. Trạng thái thực thi specialist được tách khỏi độ đầy đủ evidence: specialist có thể hoàn thành công việc nhưng kết quả vẫn ghi `unavailable` nếu nguồn evidence không tồn tại. Incident Q&A dùng investigation bundle/evidence IDs thay vì trả lời tự do không grounding.

Các file chính:

- `agent/evaluation/multi_agent.py`
- `agent/evaluation/investigation_jobs.py`
- `agent/evaluation/investigation_worker.py`
- `agent/evaluation/investigation_resume.py`
- `agent/evaluation/playbooks.py`
- `agent/evaluation/probes.py`
- `agent/evaluation/evidence_tools.py`
- `agent/evaluation/evidence_relations.py`
- `agent/evaluation/decision_contract.py`
- `agent/evaluation/questions.py`
- `agent/evaluation/agent_model.py`
- `agent_frontend/src/components/CampaignEvaluationWorkspace.jsx`
- `agent_frontend/src/components/InvestigationEvidence.jsx`

L2 còn các giới hạn thật cần giữ nguyên khi handoff:

- Chưa có publisher booking/inventory probe thật.
- Comparable placement/alternative có thể trả `unavailable`; `poor_placement` vì vậy có thể kết thúc `partial` thay vì ép kết luận.
- Một phần evidence vẫn đến từ simulated report/catalog, chưa phải publisher runtime telemetry.
- Scheduler định kỳ đang tắt; investigation được trigger rõ ràng từ Web/Zalo.

### 4.4 Zalo OA

Zalo incident flow đã được tách khỏi flow FAQ/report/tạo campaign:

- Alert chỉ ghi vào namespace `recent_incident_refs`.
- Alert không tự thay đổi `active_campaign_id`.
- Alert không tự tạo hoặc ghi đè `pending_action`.
- Incident command rõ ràng có mã `INC-*` được route trước.
- Bare number khi đồng thời có campaign pending context và incident context sẽ fail closed thay vì đoán.
- Reply parser đọc nhiều shape từ provider: `message.reply`, `quote`, `reply_to`, `quoted_message` và direct reply ID.
- Không resolve được reply-to thì bot yêu cầu user gửi lệnh rõ như `1 INC-*`.
- Outbox có idempotency để retry không gửi alert trùng.
- Lựa chọn `2 INC-*` thực sự khởi chạy L2 và không phá pending Autopilot.

Live E2E cũ đạt 10/12. Hai vấn đề đã được quan sát:

1. Reply-to metadata thiếu gây collision với bare-number command. Code đã được sửa ở `bc2c236` bằng parser mở rộng, fail-closed và observability.
2. Một tin nhắn user xuất hiện trên Zalo Web nhưng app không nhận webhook event. Không có event trong app để xử lý; đây vẫn là điểm cần retest với OA Hackathon, chưa được phép tuyên bố đã fix.

Các file chính:

- `agent/zalo_incidents.py`
- `agent/zalo_channel.py`
- `agent/zalo_routes.py`
- `agent/zalo_campaign_agent.py`
- `agent/zalo_worker.py`
- `agent/zalo_tools.py`

### 4.5 Campaign Home và Campaign Management UI

`/manage` là directory thống nhất theo owner/account/workspace, không phải danh sách global của toàn hệ thống. Lifecycle hiển thị theo effective status: campaign có raw status active nhưng end date đã qua sẽ vào nhóm completed, trong khi raw source status vẫn được giữ cho audit.

Thứ tự nhóm đã sửa:

1. Đang vận hành.
2. Chờ quyết định.
3. Đang xây dựng.
4. Đã hoàn thành.

Pagination hiện tại:

- Đang vận hành: 2/card page.
- Chờ duyệt: 4/card page.
- Đang xây dựng: 6/card page.
- Đã hoàn thành: 4/card page.

Badge Evaluation chữ đen trên nền xanh đậm đã được sửa.

`/manage/campaigns/:id` hiện có:

- Overview với campaign health, current config, report và metrics.
- Campaign Setup layout một cột.
- Chỉnh sửa các field an toàn: objective, total budget, daily budget, start date, end date.
- Revision history bất biến với before/after diff, note, request ID idempotent và optimistic expected revision.
- Placement có link mở site tương ứng.
- Creative có thumbnail/image viewer.
- Reports và Live Evaluation workspace.
- Floating Campaign Agent ở góc phải; đây là assistant deterministic để Q&A/navigation, không sửa campaign trực tiếp.

Placement và creative mutation chưa được hỗ trợ. Đây là chủ ý an toàn; chúng chỉ đang được hiển thị và liên kết.

Campaign đã dùng để kiểm tra UI gần nhất:

- `ORD-2026-036` — ZPlay.
- Raw source status: `active`.
- Effective lifecycle: completed vì đã qua end date.
- Daily budget được derive `220.000.000 / 8 = 27.500.000`.
- 6 placements, 2 creatives.

Các file chính:

- `agent/campaign_directory.py`
- `agent/campaign_config.py`
- `agent/campaign_assistant.py`
- `agent/router.py`
- `agent_frontend/src/components/CampaignHome.jsx`
- `agent_frontend/src/components/CampaignManagement.jsx`
- `agent_frontend/src/lib/campaignHomeLayout.js`

## 5. Trạng thái L3 hiện tại

L3 hiện được khóa fail-closed; chưa có campaign mutation production:

- API transition `prepare_recovery`, `start_recovery`, `verify`, `resolve` trả HTTP 409.
- Zalo option 3 nói rõ L3 chưa mở.
- Demo cũ “restore baseline” không còn được xem là recovery production và đã bị vô hiệu hóa.
- L2 không tự mutate campaign.

Không được chỉ mở lại các state transition cũ rồi gọi đó là L3. L3 cần một vertical slice thật gồm proposal -> approval -> mutation -> verification -> resolve/rollback.

### 5.1 Technical approach cho L3

Thiết kế nên dùng chung một domain service cho Web và Zalo:

```text
L2 investigation bundle
  -> Recovery Proposal Builder
  -> action registry validation
  -> risk + approval policy
  -> awaiting approval
  -> owner confirms exact proposal/nonce
  -> idempotent executor
  -> before/after audit snapshot
  -> verification window
  -> resolved | rollback | failed/escalated
```

Các thành phần cần implement:

1. `RecoveryActionRegistry`
   - Schema input/output/guards cho từng action.
   - Action chỉ được đề xuất nếu L2 evidence đủ và không có contradiction nghiêm trọng.
   - Action implementation không nằm trong LLM.

2. `RecoveryProposal`
   - `proposal_id`, incident/campaign/action IDs.
   - Evidence IDs và hypothesis nguồn.
   - Expected impact, risks, changed fields.
   - Verification criteria/window.
   - `expires_at`, nonce, policy version, status.

3. Approval policy
   - MVP luôn yêu cầu human approval.
   - Ownership server-side.
   - Xác nhận phải gắn đúng proposal/incident; generic `Xác nhận` không đủ khi mơ hồ.
   - Expired hoặc superseded proposal không được execute.

4. Idempotent executor
   - Unique execution key cho proposal revision.
   - Capture before snapshot trước mutation.
   - Apply qua backend/service contract thật, không sửa DB ad hoc từ chatbot.
   - Capture after snapshot và audit event.

5. Verification worker
   - Chờ hoặc nhận một report dataset/window mới.
   - So before/after theo success criteria đã lưu trong proposal.
   - `resolved` nếu đạt, `failed/escalated` nếu không đạt.
   - Rollback chỉ chạy khi action hỗ trợ và vẫn qua guard/idempotency.

6. Web/Zalo adapters
   - Web và Zalo chỉ gọi proposal/action service chung.
   - UI hiển thị diff, risk, evidence, expiry, approval và verification progress.
   - Zalo gửi proposal summary có mã rõ ràng và management deep link.

### 5.2 Action đầu tiên được khuyến nghị

Ưu tiên action rollback campaign config về một revision đã biết thay vì ngay lập tức làm budget reallocation hoặc creative swap. Repo đã có revision history và safe-field validation nên action này có bề mặt thay đổi nhỏ hơn và dễ chứng minh before/after.

Vertical slice đầu tiên:

```text
scenario config_drift
  -> L1 config_drift incident
  -> L2 Setup Auditor xác nhận approved/current diff
  -> proposal restore_config_revision
  -> user approve trên Web hoặc Zalo
  -> config service tạo revision mới phục hồi approved values
  -> run Evaluation trên revision/report window mới
  -> verify config hash/diff đã trở lại expected
  -> resolve incident
```

Sau khi action này pass E2E mới thêm:

- Pause một placement lỗi.
- Resume placement sau verification.
- Chuyển allocation sang placement thay thế.
- Creative swap/rollback.

## 6. Staging hiện tại trước khi hết hạn

Public endpoints:

- Agent: `https://agent.pawgrammers.io.vn`
- Agent API: `https://api.pawgrammers.io.vn`
- Analytics: `https://analytics.pawgrammers.io.vn`

SSH đã dùng: `root@agent.pawgrammers.io.vn`

Hostname guard đã xác nhận: `momolita`

Runtime paths:

```text
/var/www/agent-api
/var/www/backend
/var/www/analytics_frontend
/var/www/agent                       # frontend symlink
/var/www/evaluation-releases/<id>/frontend
/var/backups/advertising-agent/evaluation/<id>/
```

Process manager:

- `agent-api`
- `adspilot-api`

Release đang chạy:

- Release ID: `20260906-evaluation-m6-8`
- Git HEAD: `7d92f51c460f46a539a4d171df9b04bdc33ee3af`
- Local manifest: `.codex-tmp/evaluation-m6-8/manifest.json`
- Release m6-8 là frontend delta sau m6-7.

Validation gần nhất:

- 48 runtime snapshot files và 100 frontend files khớp checksum release.
- Rollback artifact tồn tại.
- `/agent/ready` trả toàn bộ readiness checks thành công.
- `/api/health` báo database connected.
- Browser validation không có console warning/error.
- L2 engine `multi-agent-v6`.
- Evidence contract `evidence-relations-v3`.
- Periodic Evaluation worker đang tắt.
- OA staging là `IOT Generation`.

Không cần chuyển dữ liệu staging theo yêu cầu hiện tại. Tuy nhiên trước khi VPS hết hạn vẫn nên push branch và lưu các report/manifest không chứa secret nếu cần làm bằng chứng.

## 7. Hackathon VPS và deployment contract

Target public domain: `https://zah-4.123c.vn`

Repo có stack riêng:

- Compose project: `advertising-agent-hackathon`
- Compose file: `docker-compose.hackathon.yml`
- Runbook: `deploy/hackathon/README.md`
- Env templates:
  - `deploy/hackathon/stack.env.example`
  - `deploy/hackathon/agent.env.example`
  - `deploy/hackathon/backend.env.example`

Actual env files không được commit và phải mode `0600`:

```text
deploy/hackathon/stack.env
deploy/hackathon/agent.env
deploy/hackathon/backend.env
```

Stack dùng named volumes riêng cho Mongo, Qdrant, backend uploads, caches và Zalo token store. Không tái dùng volume hoặc `.env` từ staging.

Các route public chính:

```text
/
/agent
/backend/
/api/
/uploads/
/adspilot/
/analytics/
/znews/
/baomoi/
/zingmp3/
/smoney/
/dicungcon/
/zagoo/
```

Compose command chuẩn:

```sh
docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  up -d --build
```

Sau khi stack lên, build lại RAG:

```sh
docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  exec agent python scripts/build_rag_index.py --force
```

Readiness cuối phải kiểm tra `/ready`, không chỉ container `/health`.

Seed cho môi trường fresh nếu cần:

```sh
node seed/index.js
node seed/seed-audience-missing.js
node seed/migrate-np6-catalog.js --apply --deployment-id=zah4-hackathon-np6
```

Địa chỉ SSH/user/path checkout cụ thể của Hackathon VPS chưa được ghi trong repo/handoff này. Hội thoại mới phải xác nhận đúng target và hostname bằng read-only check trước khi deploy, không được suy đoán từ SSH của staging.

## 8. Lưu ý bắt buộc về hai Zalo OA

Staging dùng OA `IOT Generation`; Hackathon dùng OA riêng:

```text
ZALO_OA_ID=847163434345003951
ZALO_OA_NAME=Advertising Agent
ZALO_APP_ID=669472079566550173
callback=https://zah-4.123c.vn/agent/api/agent/auth/zalo/callback
```

Việc OA Hackathon đã tồn tại giúp không phải tạo lại OA, nhưng vẫn phải kiểm tra environment-specific integration:

- Không copy OA access token, refresh token, app secret hoặc token volume từ staging.
- Giữ các giá trị OA/app trong `deploy/hackathon/agent.env` hiện hữu.
- Xác nhận callback và webhook trên OA console vẫn trỏ tới `zah-4.123c.vn`.
- Xác nhận token store trong named volume của Hackathon còn hợp lệ; nếu token hết hạn thì reconnect OA Hackathon.
- Xác nhận signature/replay guard trước khi bật outbound.

Năm feature switches của stack:

```text
ZALO_LOGIN_ENABLED
ZALO_OA_ENABLED
ZALO_AGENT_WORKER_ENABLED
ZALO_OUTBOUND_ENABLED
ZALO_OPENAI_ENABLED
```

Nên giữ tất cả tắt trong lúc bring-up cơ bản, sau đó bật inbound trước, kiểm tra webhook, rồi mới bật outbound. Đây là kiểm tra cấu hình, không phải yêu cầu setup một OA mới.

## 9. Runbook migration đề xuất

### Phase A — bảo toàn source trước khi staging hết hạn

1. Xác nhận branch/HEAD/dirty files.
2. Push `codex/v4-live-evaluation` lên remote.
3. Lưu manifest/test reports không chứa secrets.
4. Không cần dump Mongo/report data nếu chấp nhận fresh account/campaign.

### Phase B — inventory Hackathon VPS

1. Xác nhận SSH target và hostname.
2. Kiểm tra `git status`, branch, disk, Docker, compose, nginx/certificate.
3. Kiểm tra current stack và tạo rollback snapshot/backup trước khi thay code.
4. Kiểm tra env key presence mà không in secret values.
5. Kiểm tra named volumes và OA token volume thuộc đúng compose project.

### Phase C — deploy code hiện tại trước L3

1. Checkout/pull toàn bộ nhánh `codex/v4-live-evaluation`; không cherry-pick vài commit cuối vì feature phụ thuộc cả chuỗi 22 commit.
2. Dùng env Hackathon hiện hữu.
3. Build/start stack bằng compose Hackathon.
4. Build RAG index.
5. Kiểm tra container health, public `/ready`, backend DB, static routes và browser console.
6. Chỉ sau khi base stack khỏe mới bật Zalo inbound/outbound theo thứ tự an toàn.

### Phase D — tạo data fresh và acceptance L1/L2

1. Tạo account mới.
2. Tạo campaign mới hoàn tất order/report.
3. Xác nhận campaign xuất hiện đúng group lifecycle trên `/manage`.
4. Mở Campaign Management, kiểm tra current config, setup revision, creative viewer và placement links.
5. Apply scenario và xác nhận report revision + L1 incident.
6. Start L2, theo dõi specialist jobs, evidence relations và coordinator result.
7. Kiểm tra Campaign Agent Q&A/navigation không mutate campaign.
8. Kiểm tra Zalo FAQ/report/create campaign trước và sau alert.
9. Kiểm tra `2 INC-*` mở đúng incident; bare number mơ hồ phải fail closed.
10. Retest trường hợp tin nhắn xuất hiện trên Zalo Web nhưng webhook không tới app.

### Phase E — implement L3

1. Giữ L3 409/fail-closed trong lúc schema/service chưa hoàn tất.
2. Implement action registry và proposal persistence.
3. Implement `restore_config_revision` end-to-end.
4. Nối Web approval và Zalo approval vào cùng service.
5. Implement verification/rollback.
6. Mở feature flag L3 chỉ sau focused tests và E2E trên fresh campaign.

## 10. Acceptance suite bắt buộc trên Hackathon VPS

### Base platform

- Homepage, login, create campaign, report, analytics và publisher sites load đúng cùng domain.
- `/ready` pass; Mongo/Qdrant/backend checks thật sự healthy.
- Fresh account chỉ thấy campaign của mình.
- Expired active campaign được phân loại completed.

### Scenario Lab

- Danh sách đủ 12 preset.
- Preview không mutate active dataset.
- Apply tạo đúng một revision với request idempotent.
- Reset tạo revision từ baseline và resolve signal phù hợp.
- Report và Evaluation luôn tham chiếu cùng dataset revision.
- Mobile không có horizontal overflow.

### L1

- Healthy baseline không tạo false incident.
- Low delivery/CTR/creative/config/tracking scenarios tạo đúng class incident.
- Persistence/sample/data-quality gates hoạt động.
- Duplicate run không tạo incident/notification trùng.

### L2

- Investigation tạo đúng specialist tasks theo issue type.
- Lease/resume không chạy trùng.
- Evidence relation được render và không causal-overclaim.
- Missing publisher evidence được ghi `unavailable/partial`, không bị biến thành `failed` hoặc fabricated evidence.
- Q&A trỏ đúng bundle/evidence IDs.

### Zalo coexistence

- FAQ vẫn trả lời sau khi nhận alert.
- “Xem report” không bị route thành incident command.
- “Tạo campaign” không bị `recent_incident_refs` can thiệp.
- Explicit `INC-*` mở đúng incident.
- Bare number mơ hồ fail closed.
- Reply-to message ID map đúng incident nếu provider gửi metadata.
- Unknown reply-to yêu cầu explicit command.
- Duplicate webhook/outbox không gửi hai alert.
- Pending Autopilot không bị L2 alert/command ghi đè.
- Freeform inbound message thực sự có webhook event; ghi lại provider/app logs nếu mất event.

### L3 sau khi implement

- Không tạo proposal khi L2 thiếu evidence bắt buộc hoặc có contradiction blocking.
- User khác không đọc/approve/execute proposal.
- Proposal hết hạn/superseded/nonce sai bị từ chối.
- Double approval hoặc retry chỉ execute một lần.
- Before/after config snapshot và immutable audit event tồn tại.
- Config revision rollback tạo một revision mới, không rewrite lịch sử.
- Verification đạt thì incident resolved.
- Verification không đạt thì failed/escalated hoặc rollback theo policy.
- Web và Zalo cho cùng proposal/state; không có hai executor path khác nhau.
- Generic `Xác nhận` không approve nhầm khi có nhiều pending contexts.

## 11. Validation đã có trước handoff

Các con số dưới đây thuộc các checkpoint khác nhau; không nên cộng hoặc mô tả như một lần chạy duy nhất:

- Backend report suite: 87/87 pass.
- Frontend suite gần nhất: 220/220 pass và production build thành công.
- Eval/Zalo focused checkpoint: 237 pass.
- Campaign/Evaluation/Zalo focused sau các UI fix: 165 pass.
- Full agent checkpoint: 800 pass, 6 failure nền không liên quan ở OpenAI mocks/date fixture/order assertions.
- Analytics suite sau mobile fix: 9 pass.
- Real-model counterfactual checkpoint: 4 cases x 2 rounds, 80 calls; offline corrected acceptance 8/8 mà không gọi model lại.
- Staging browser QA: không có console error/warning tại checkpoint gần nhất.
- Live Zalo E2E cũ: 10/12; một reply-routing issue đã được code-fix, một inbound webhook delivery issue phải retest trên OA Hackathon.

Chi tiết bằng chứng:

- `docs/evaluation-l2-checkpoint-2026-09-01.md`
- `docs/evaluation-zalo-e2e-report-2026-09-01.md`
- `EVALUATION_VPS_ACCEPTANCE_2026-08-31.md`
- `EVALUATION_IMPLEMENTATION_PLAN.md`
- `EVALUATION_MULTI_AGENT_M1.md`
- `EVALUATION_INCIDENT_QA_M2.md`
- `EVALUATION_L2_STABILITY_M3.md`
- `EVALUATION_L2_RELATIONS_M4.md`

## 12. Definition of done cho hội thoại tiếp theo

Migration hoàn thành khi:

- Nhánh được bảo toàn trên remote.
- Hackathon stack có rollback và chạy đúng HEAD mong muốn.
- Public readiness, fresh account/campaign, Scenario Lab, L1, L2 và Zalo coexistence được kiểm tra lại bằng evidence.
- OA Hackathon dùng credential/token/callback riêng, không lẫn staging.

L3 vertical slice đầu tiên hoàn thành khi:

- Config drift tạo evidence L1/L2 đủ để sinh proposal.
- User xem được exact diff/risk/verification plan.
- Approval Web hoặc Zalo đi qua cùng service và ownership gate.
- Mutation tạo config revision mới có before/after audit.
- Verification thật quyết định resolve hoặc rollback/failure.
- Retry, expiry, duplicate webhook và ambiguous confirmation đều fail safe.
