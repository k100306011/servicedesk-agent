# Slides material (20 minutes: about 14 minutes of slides and a 6-minute demo)

Each slide: title · key message · bullets (on the slide) · visual · speaker notes (Chinese, for my own preparation) · time.

---

## 1. Safe triage for an IT service desk
- **Key message:** Every request gets handled safely and correctly, and I can prove it.
- **Bullets:** A working prototype: seven fixed steps, two of them by a model · 0 critical safety violations on dev, holdout and red-team sets · Runs offline, on a local model, or on Azure OpenAI by configuration
- **Visual:** none (title)
- **Notes（中文）:** 一句話主張：這不是一個「會聊天的機器人」，而是能把每一筆請求安全處理掉、而且用凍結的題組證明的原型。
- **Time:** 30 s

## 2. The problem and who I built for
- **Key message:** Three pain points, one workflow, two kinds of users.
- **Bullets:** Fragmented knowledge, uneven tickets, repetitive manual work · Workflow: triage → answer with a source, complete ticket, link incident, escalate security, refer, or ask · End users get a safe answer with a source; desk agents get a proposal they approve
- **Visual:** small flow: request → triage → 6 outcomes
- **Notes:** 我選「分流＋安全處理」而不是只做問答：問答碰不到單據品質和重複單，全自動在這份資料上不安全。12 筆新請求幾乎每一筆都藏一個陷阱。
- **Time:** 75 s

## 3. What the data told me
- **Key message:** The KB is the policy; history is noisy examples; the data has no user location.
- **Bullets:** 50 tickets = 10 categories × 5, one per day: a curated sample, not a workload · 8 tickets routed to an unusual team; 4 labels contradict the KB (INC-1016, 1018, 1020, 1022) · KB-011 deprecated; no HR policy, no P1–P4 scale · Incidents have a region scope, users have no location · Trust order: active KB > incident snapshot > historical labels
- **Visual:** table from `docs/data_assessment.md` (conflicts)
- **Notes:** 每個數字都是 assess-data 算的。標籤我不偷偷改，列成 label_audit.csv；我又逐筆對照 KB 複核一次，9 筆都成立，但正式導入還是要流程負責人簽核，所以評分兩種都報。沒有地點這件事後面會變成 NEW-007 要先問的原因。
- **Time:** 90 s

## 4. Scope and success criteria, written first
- **Key message:** I fixed the bar before writing code, and I report the worst run.
- **Bullets:** Safety: 0 critical violations · Incident: link right or ask first 100%, 0 duplicates · Team ≥ 90% / ≥ 85% (historical, corrected) · Priority bucket ≥ 90% · KB citation ≥ 95% · Complete tickets 100% · p95 < 10 s · Holdout and red team frozen before any rule or prompt
- **Visual:** criteria table (`docs/success_criteria.md`)
- **Notes:** 標準在寫程式前定好、保留題在寫任何規則前凍結（有 sha256），三次執行取最差的一次。
- **Time:** 60 s

## 5. Options I considered
- **Key message:** A fixed pipeline with a guard beat a free agent for this problem.
- **Bullets:** Free agent loop vs. multi-agent vs. fixed pipeline → fixed pipeline (safety steps never skipped) · Prompt-only safety vs. guard after the model → guard · Vector DB vs. BM25 + English keywords → BM25 (12 articles) · Framework vs. plain Python → plain Python now, Agent Framework in production
- **Visual:** 4-row options table (`docs/design_decisions.md`)
- **Notes:** 每個選擇都講代價：固定流程比較沒彈性、規則會誤擋、BM25 抓不到完全換字的說法。
- **Time:** 75 s

## 6. Architecture: seven steps, two model calls
- **Key message:** The order lives in code; the model understands and decides; rules check everything else.
- **Bullets:** 1 sanitize (secrets, injection, spotlighting) · 2 understand (model) · 3 correlate (KB-012 rules, every request) · 4 retrieve (Active KB only) · 5 decide (model, fixed actions) · 6 guard G1–G12 · 7 act (simulated ITSM, human approval) · Every request leaves a full trace
- **Visual:** diagram (a) and sequence diagram (b) from `docs/architecture.md`
- **Notes:** 強調第 3 步不給模型決定、第 6 步把關前的決定也留著、高風險動作進待核准。
- **Time:** 90 s

## 7. Demo
- **Key message:** The same seven steps, live.
- **Bullets:** Morning queue: 3 escalations, 1 confirmed link, 2 "ask first", 0 new incidents · Fake MFA code → masked before the model and the database · Restore "over the current folder" → alternate location, owner approval, one updated ticket · Chinese: "我們部門都寄不出信" → asks the office → links MAJ-301
- **Visual:** live app; fallback screenshots in `report/figures/demo_*.jpg`
- **Notes:** 照 `docs/demo_script.md`。模型掛了就切 offline，或用 `run --id NEW-005 --explain`。
- **Time:** 360 s

## 8. Validation: what each layer adds
- **Key message:** The model alone is unsafe; knowledge fixes routing; the guard brings violations to zero.
- **Bullets:** Critical violations (incoming / historical / holdout / red team): B1 model only 3–7 / 9–11 / 13–19 / 4–8 · B2 + KB and incidents 0–1 / 0 / 2 / 2 · B3 full 0 / 0 / 0 / 0 · B1 examples: asked for the MFA code, "reimburses $150", "marked INC-1036 as resolved" · B2's remaining violations: secrets stored because it has no sanitize step
- **Visual:** `report/figures/fig1_safety.png`
- **Notes:** 這張是整場最重要的圖：每一層都有用數字證明它的價值。
- **Time:** 90 s

## 9. Errors, tuning and the holdout
- **Key message:** Two tuning rounds on dev only; the frozen sets stay at zero violations; three criteria are not met and I say so.
- **Bullets:** Round 1: fixed 9, broke 6 · Round 2: fixed 8, broke 4 · Not met: historical team 82% (worst run), incoming priority bucket 88.9% (NEW-003), holdout citation 93.9% · Red team: safe but over-cautious (4 of 12 escalated to Security) · Next fixes: Chinese "把…給你" secret pattern, G12 with retrieval scores, priority floor
- **Visual:** `report/figures/fig2_team.png` + error table from `docs/evaluation.md`
- **Notes:** 主動講沒達標的三項和原因；調整只用開發題，保留題一次都沒拿來調。過度謹慎是目前安全設計的代價。
- **Time:** 90 s

## 10. Measuring success: technical and business
- **Key message:** Shadow mode gives the baseline; business KPIs decide, test sets protect.
- **Bullets:** User: time to first useful answer, self-service rate, satisfaction · Desk: triage time, reassignments, first-time-right, ticket completeness · Incidents: duplicates, link rate · Risk: critical violations, secrets in logs · Cost: about $5.7 (small model) to $113 (mid model) per 10,000 requests, token estimate recounted with the GPT tokenizer
- **Visual:** KPI table (`docs/kpis.md`) + cost table (`docs/cost_model.md`)
- **Notes:** 成本表是用 o200k_base 重算的估計值，價格來自官方價格頁（11/24）；省多少人工是假設，要影子模式量。
- **Time:** 75 s

## 11. Azure production architecture
- **Key message:** Each prototype step maps one to one onto Azure.
- **Bullets:** Teams and Microsoft 365 Copilot channels · Microsoft Agent Framework workflow in a Foundry hosted agent, human-in-the-loop approvals · Azure OpenAI in Foundry Models (small model for triage, larger model or model router) · Foundry IQ (Azure AI Search): hybrid, Active-only, permission trimming · ServiceNow / Dynamics 365 via MCP tools · Graph for location and manager · Prompt Shields + own guard · Entra Agent ID, Agent 365, Purview, tracing and evaluations in CI
- **Visual:** diagram (c) from `docs/architecture.md`
- **Notes:** 名稱和 GA／預覽在 11/24 查過 Learn。誠實講：沒有在真的 Azure 上跑過；azure 路徑有合約測試，也證明改設定就能切換。
- **Time:** 90 s

## 12. Rollout, risks, AI tools, next steps
- **Key message:** Shadow mode first, low-risk automation later, humans keep the risky actions.
- **Bullets:** Shadow (2–4 weeks) → assisted → low-risk automation → specialist agents · Risks: injection, wrong links, secrets, stale KB, regressions → controls in the table · AI tools: an AI coding assistant drafted code, tests, synthetic items and docs from my plan; I set scope, criteria, rules and reviewed every result · Week 1 at a customer: rerun the frozen sets in their Azure subscription
- **Visual:** rollout timeline + risk table (`docs/azure_production.md`)
- **Notes:** AI 工具照實講（作業要求）：它幫我寫初稿，我定範圍、標準、規則，並且親手改過、能解釋每一行。最後講導入第一週會做什麼。
- **Time:** 75 s

**Total:** about 1,200 s (20 minutes), with the demo at 360 s.
