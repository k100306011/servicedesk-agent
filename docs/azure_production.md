# From prototype to Azure production

Names and GA / preview status were checked on Microsoft Learn and official Microsoft blogs on **2026-11-24**. Links are at the end.
The diagram is in [architecture.md](architecture.md#c-azure-target-architecture).

## Component map

| Prototype | Azure production | Why | Status (2026-11-24) |
|---|---|---|---|
| Streamlit chat | Agent published to **Microsoft Teams and Microsoft 365 Copilot** from Foundry Agent Service; the employee portal for long answers | Meet users where they already work | Publishing GA (Jun 2026). Published agents do not show citations, so sources are written into the reply text |
| Email and phone-transcript channels | **Microsoft Graph** mail change notifications on the service desk mailbox (mailbox scoped with RBAC for Applications in Exchange Online). Phone: **Teams Phone Extensibility** with **Azure Speech in Foundry Tools** for transcription | One intake for every channel | Graph GA. Azure Communication Services as a standalone telephony platform is being retired, and new customers cannot buy PSTN numbers since Oct 2026, so new phone intake goes through Teams |
| 7-step pipeline (`pipeline.py`) | **Microsoft Agent Framework** workflow: each step is an executor; `approval_required` becomes a human-in-the-loop request; checkpoints keep pending approvals. Deployed as a **hosted agent** in **Foundry Agent Service** | Same fixed flow, now stateful, resumable and observable | Agent Framework 1.0 GA (Apr 2026, Python and .NET). Hosted agents GA (Jul 2026). The Foundry hosting packages for Agent Framework are still prerelease |
| Local 14B model | **Azure OpenAI in Foundry Models**: a small model such as `gpt-6-luna` for triage; a larger model (`gpt-6.2-sol`) or **model router** for hard cases; **Data Zone Standard** deployment for data residency | Cost and quality can be tuned per step | `gpt-6-luna` GA (Sep 2026), `gpt-6.2-sol` GA (Nov 2026), model router GA (version 2025-11-18). Data Zones: US, EU, APAC |
| BM25 over 11 Active articles | **Foundry IQ (Azure AI Search)**: hybrid search, semantic ranker, filter `status eq 'Active'`, document-level permission filtering. Or a **Foundry IQ knowledge base** (agentic retrieval with citations). Sources: SharePoint and ITSM knowledge | This is where "fragmented knowledge" gets fixed | Azure AI Search was renamed Foundry IQ (Azure AI Search) in Nov 2026. Hybrid and semantic ranker GA; native ACL/RBAC permission filtering GA in REST 2026-10-01; Purview-label enforcement still preview. Knowledge bases GA; the documented agent connection still uses a preview API version |
| Simulated ITSM tools (SQLite) | **ServiceNow** or **Dynamics 365 Customer Service** APIs as **MCP** or **OpenAPI** tools; MCP `require_approval` for write actions | Real tickets, real incidents | Dynamics 365 Customer Experience MCP Server for Service is GA. No first-party ServiceNow connector found in the Foundry catalog; use the OpenAPI tool or ServiceNow's MCP server. The OpenAPI tool has no OAuth identity passthrough |
| "Which office are you in?" | **Microsoft Graph** user profile: `department`, `officeLocation`, `manager` | Removes the location question (NEW-007) and finds the approver | GA |
| Approval routing | **Microsoft Entra ID Governance** access packages for pre-approved standard roles | Standard roles go through governed self-service | GA |
| sanitize (secrets, injection, spotlighting) | **Foundry guardrails** with **Prompt Shields** (user prompt attacks and document attacks); **PII detection in Azure Language in Foundry Tools**; keep our own markers and redaction in code | Platform defenses first, own rules on top | Prompt Shields GA. Document-attack detection is off by default, so turn it on. Spotlighting is preview, Chat Completions only and not available for agents, so the code keeps its own markers. Agent-level guardrails are preview |
| guard (`policies.yaml`) | Stays in code, versioned; every change runs the frozen evaluation set in CI | Policy must be auditable and testable | n/a |
| Agent identity | **Microsoft Entra Agent ID**, managed identity, least privilege (the agent identity cannot resolve tickets), **Key Vault**, Private Endpoints and VNet | The agent is an identity that needs governance too | Entra Agent ID GA (Jun 2026). Hosted agents support bring-your-own VNet |
| Trace and evaluation | **Foundry tracing** (OpenTelemetry) to **Application Insights**; **Foundry evaluations**; the frozen sets run in **GitHub Actions** or **Azure DevOps** on every prompt or rule change | Know at once when a change makes things worse | Tracing GA for prompt and hosted agents. Several agent evaluators (task adherence, intent resolution) are preview; the GitHub Action uses a beta tag |
| (nothing in the prototype) | **Microsoft Agent 365** (agent registry, observability, governance); **Microsoft Purview** (audit, DSPM, DLP) | The enterprise must see and govern every agent | Agent 365 GA (May 2026) |
| `results/` and the KPI table | ITSM data in **Microsoft Fabric**, KPIs in **Power BI** | Show business value, not only model scores | GA |

## Rollout in four phases

1. Shadow mode (2 to 4 weeks): the agent only proposes, and people work as today. Measure agreement between the agent and the desk on action, team and priority, plus every critical check. The frozen test sets keep running on each change.
2. Assisted mode: desk agents approve or edit each proposal with one click. Measure handling time, reassignments and ticket completeness by queue.
3. Low-risk automation: automate only low-risk paths, for example linking to a known incident or self-service answers with a cited KB article. Access, restores, software approval and security cases always keep a human approval.
4. Later: specialist agents per owning team, each with its own identity and permissions, connected over A2A. This comes only after the shared pipeline is stable.

## Risks and how to handle them

| Risk | Control |
|---|---|
| Prompt injection through email or imported text | Prompt Shields (document attacks on), own markers and injection flags, G10 floor, least-privilege agent identity |
| Wrong incident link or duplicate incident | Deterministic KB-012 check, location from Graph, human confirmation when the match is only possible |
| Secrets in tickets or logs | Redaction before the model and before storage, Purview DLP, the secret-leak check in CI |
| Stale or conflicting knowledge | Only Active articles indexed, a review date per article, monthly review of guard triggers and KB gaps with the knowledge owners |
| Model or prompt change makes things worse | Frozen dev, holdout and red-team sets in CI; release only when the critical checks stay at 0 |

## Sources (opened on 2026-11-24)

- Foundry Agent Service: https://learn.microsoft.com/en-us/azure/foundry/agents/overview
  - Hosted agents: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
  - Publish to Copilot and Teams: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/publish-copilot
- Microsoft Agent Framework: https://learn.microsoft.com/en-us/agent-framework/overview/
  - Human in the loop: https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop
  - 1.0 release: https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/
- Models: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure
  - Model router: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router
  - Deployment types: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types
  - v1 API: https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle
- Foundry IQ (Azure AI Search): https://learn.microsoft.com/en-us/azure/search/whats-new
  - Document-level access: https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview
  - Foundry IQ: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq
- Prompt Shields: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-prompt-shields
  - Guardrails: https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview
  - PII: https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/overview
- Entra Agent ID: https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id
  - Agent 365: https://learn.microsoft.com/en-us/microsoft-agent-365/overview
  - Purview for Foundry: https://learn.microsoft.com/en-us/purview/ai-azure-foundry
- Tracing: https://learn.microsoft.com/en-us/azure/foundry/observability/concepts/trace-agent-concept
  - Evaluators: https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators
  - CI: https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-github-action
- Graph user: https://learn.microsoft.com/en-us/graph/api/resources/user
  - Change notifications: https://learn.microsoft.com/en-us/graph/change-notifications-overview
  - Azure Communication Services retirement guide: https://learn.microsoft.com/en-us/azure/communication-services/acs-retirement-and-breaking-changes-guide
  - Speech: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/overview
- Entitlement management: https://learn.microsoft.com/en-us/entra/id-governance/entitlement-management-overview
- Tools: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol
  - https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/openapi
  - Dynamics 365 MCP: https://learn.microsoft.com/en-us/dynamics365/customer-service/develop/mcp-tools-overview
- Fabric: https://learn.microsoft.com/en-us/fabric/fundamentals/microsoft-fabric-overview
