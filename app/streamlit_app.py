"""Streamlit UI: end-user chat, service desk review console, and evaluation results.
Run: streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8601
The UI only calls the same pipeline as the CLI; it holds no business logic of its own.
"""
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from sdagent import ROOT, actions, data, pipeline
from sdagent.baseline import required_fields, variant
from sdagent.explain import explain

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Service Desk Agent", layout="wide")
DB = actions.connect()
EXAMPLES = {f"{r['request_id']} ({r['channel']})": (r["message"], r["channel"]) for r in data.incoming_requests()}
EXAMPLES |= {"中文: 我們部門都寄不出信": ("我們部門都寄不出信", "chat"),
             "中文: 收到不是我發起的 MFA 通知": ("我剛剛收到兩次不是我發起的 MFA 登入通知，要怎麼辦？", "chat"),
             "中文: 共用資料夾被拒絕存取": ("共用磁碟可以開，但是 Finance 資料夾顯示拒絕存取。", "chat")}

with st.sidebar:
    st.header("Settings")
    default = os.getenv("LLM_PROFILE", "offline").split("#")[0].strip()
    profile = st.selectbox("Model profile", ["offline", "local", "azure"], index=["offline", "local", "azure"].index(default))
    config = st.selectbox("Configuration", ["B3", "B2", "B1"] if profile != "offline" else ["B0"],
                          help="B0 rules only · B1 model only · B2 model + KB + incidents · B3 all 7 steps")
    if st.button("Reload config (YAML and prompts)"):
        data.reload()
        st.success("Config reloaded")
    if st.button("Reset database"):
        actions.reset()
        st.session_state.clear()
        st.rerun()


def show_trace(t) -> None:
    for s in t.steps:
        st.markdown(f"**{s.name}** — {s.summary} `{s.ms} ms`")
        if s.output not in (None, [], {}):
            st.json(s.output, expanded=False)
    if t.pre_guard and t.guard_fixes:
        st.markdown("**Before the guard:** " + f"`{t.pre_guard.action}` · {t.pre_guard.user_reply}")
    st.code(explain(t), language="text")


chat_tab, console_tab, eval_tab = st.tabs(["User chat", "Service desk console", "Evaluation"])

with chat_tab:
    st.subheader("Ask the service desk")
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("conv_id", pipeline.free_text_request("x").request_id)
    c1, c2, c3 = st.columns([3, 1, 1])
    pick = c1.selectbox("Example", ["(type your own)"] + list(EXAMPLES))
    channel = c2.selectbox("Channel", ["chat", "web", "email", "phone_transcript"],
                           index=["chat", "web", "email", "phone_transcript"].index(EXAMPLES[pick][1]) if pick in EXAMPLES else 0)
    if c3.button("New conversation"):
        st.session_state["chat"], st.session_state["conv_id"] = [], pipeline.free_text_request("x").request_id
        st.rerun()
    if pick in EXAMPLES and st.button("Send example"):
        st.session_state["pending"] = EXAMPLES[pick][0]
    typed = st.chat_input("Describe your IT problem")
    message = typed or st.session_state.pop("pending", None)
    if message:
        history = [{"role": m["role"], "text": m["text"]} for m in st.session_state["chat"]]
        req = pipeline.free_text_request(message, channel, history)
        req.request_id = st.session_state["conv_id"]
        with st.spinner("Working..."):
            trace = pipeline.run_request(req, config=config, profile=profile, db=DB)
        st.session_state["chat"] += [{"role": "user", "text": message}, {"role": "agent", "text": trace.decision.user_reply, "trace": trace}]
    for m in st.session_state["chat"]:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.write(m["text"])
            if m["role"] == "agent":
                t = m["trace"]
                st.caption(f"{t.decision.action} · {t.decision.category} · {t.decision.priority} · sources: {', '.join(t.decision.cited_kb) or '-'}")
                with st.expander("How this was handled"):
                    show_trace(t)

with console_tab:
    st.subheader("Morning queue (12 incoming requests)")
    if st.button("Process the 12 morning requests"):
        bar, traces = st.progress(0.0), []
        reqs = pipeline.load_set("incoming")
        for i, r in enumerate(reqs, 1):
            traces.append(pipeline.run_request(r, config=config, profile=profile, db=DB))
            bar.progress(i / len(reqs), text=r.request_id)
        st.session_state["batch"] = {t.request_id: t for t in traces}
    batch = st.session_state.get("batch", {})
    links = DB.execute("SELECT incident_id, COUNT(DISTINCT request_id) n FROM links GROUP BY incident_id").fetchall()
    cols = st.columns(len(data.incidents()) + 1)
    for col, inc in zip(cols, data.incidents()):
        n = next((r["n"] for r in links if r["incident_id"] == inc["incident_id"]), 0)
        ask = sum(1 for t in batch.values() if t.decision.incident_id == inc["incident_id"] and t.decision.action == "ask_clarifying")
        col.metric(f"{inc['incident_id']} · {inc['service']}", f"{n} linked", f"{ask} to confirm · {inc['status']}", delta_color="off")
    new_inc = DB.execute("SELECT COUNT(*) FROM tickets WHERE kind='incident'").fetchone()[0]
    cols[-1].metric("New incidents opened", new_inc)
    if batch:
        rows = []
        for t in batch.values():
            d = t.decision
            need = required_fields(d.category, variant(d.category, t.message)) if d.action == "create_ticket" else []
            filled = len([f for f in need if f not in d.missing_fields])
            rows.append({"request": t.request_id, "channel": t.channel, "action": d.action, "category": d.category,
                         "priority": d.priority, "team": d.team, "incident": d.incident_id or "-",
                         "fields": f"{filled}/{len(need)}" if need else "-",
                         "rules": ", ".join(sorted({f["rule"] for f in t.guard_fixes})) or "-"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        rid = st.selectbox("Open a request", list(batch))
        t = batch[rid]
        left, right = st.columns(2)
        with left:
            st.markdown(f"**Request:** {t.message}")
            st.markdown(f"**Reply to user:** {t.decision.user_reply}")
            st.markdown(f"**Sources:** {', '.join(t.decision.cited_kb) or '-'}  \n**Agent note:** {t.decision.agent_note}")
            if t.guard_fixes:
                st.markdown("**Guard fixes:**\n" + "\n".join(f"- {f['rule']}: {f['change']}" for f in t.guard_fixes))
        with right:
            for tk in DB.execute("SELECT * FROM tickets WHERE request_id=? ORDER BY id DESC LIMIT 1", (rid,)).fetchall():
                st.markdown(f"**Ticket {tk['id']}** · {tk['kind']} · status `{tk['status']}` · approver: {tk['approver'] or '-'}")
                st.json({"fields": json.loads(tk["fields"]), "missing": json.loads(tk["missing"])})
        with st.expander("Trace"):
            show_trace(t)
    st.markdown("**Waiting for approval** (high-risk actions count only after a person approves)")
    pending = DB.execute("SELECT id, request_id, category, team, approver, fields FROM tickets WHERE status='pending_approval'").fetchall()
    if not pending:
        st.caption("Nothing is waiting.")
    else:
        st.dataframe(pd.DataFrame([dict(r) for r in pending]), hide_index=True, width="stretch")
        tid = st.selectbox("Ticket", [r["id"] for r in pending])
        who = st.text_input("Your name", "service desk agent")
        edits = st.text_area("Edits for 'Edit & approve' (JSON)", "{}")
        b1, b2, b3 = st.columns(3)
        if b1.button("Approve"):
            actions.decide_approval(DB, tid, True, who)
            st.rerun()
        if b2.button("Edit & approve"):
            actions.decide_approval(DB, tid, True, who, "edited", json.loads(edits or "{}"))
            st.rerun()
        if b3.button("Reject"):
            actions.decide_approval(DB, tid, False, who)
            st.rerun()
    st.markdown("**Audit log** (last 10)")
    log = DB.execute("SELECT ts, actor, tool, request_id, detail FROM audit_log ORDER BY id DESC LIMIT 10").fetchall()
    st.dataframe(pd.DataFrame([dict(r) for r in log]) if log else pd.DataFrame(), hide_index=True, width="stretch")

with eval_tab:
    summary = ROOT / "results" / "summary.csv"
    if not summary.exists():
        st.info("No results yet. Run: python -m sdagent eval ... then python -m sdagent summarize")
    else:
        st.dataframe(pd.read_csv(summary), hide_index=True, width="stretch")
        for fig in sorted((ROOT / "report" / "figures").glob("*.png")):
            st.image(str(fig), caption=fig.stem)
