# Lattia Design Doc

## Approach selection: Static workflow vs Agentic System

### Static workflow

One option considered was a **static LLM workflow**, where the system would operate primarily as a retrieval-and-selection pipeline. In this approach, the interview is driven by a predefined knowledge base of candidate questions. At each step, the workflow retrieves potentially relevant questions using semantic search and ranking, then the LLM selects the most suitable one, reformulates it naturally for the user, and later maps user responses into machine-readable values.

The LLM’s role here is focused:
- Selecting the next question from retrieved candidates.
- Rephrasing the question into conversational language.
- Normalizing the user’s response into the appropriate structured format.

All other orchestration and logic are handled by the static workflow design.

#### Pros
- **Simplicity**: The LLM’s task is narrower and easier, reducing risk of failure.
- **Lower cost**: Can operate with smaller, cheaper models since reasoning complexity is limited.
- **Better latency**: Less reasoning overhead leads to faster responses.
- **High controllability**: System behavior is predictable because the workflow is explicitly defined.
- **Steerability**: Easy to enforce formatting standards, validate outputs, and constrain the system.
- **Testability**: With static steps, the workflow is easier to unit test and monitor.

#### Cons
- **Rigid and bottlenecked**: System quality depends heavily on the initial workflow design and on the coverage of the question knowledge base.
- **Low adaptability**: The system does not improve organically over time or take advantage of advances in reasoning capabilities of newer LLMs.
- **Maintenance overhead**: Requires constant curation of large sets of labeled, structured questions. Scaling this is difficult.
- **Limited leverage of new knowledge**: Hard to integrate emerging medical research or evolving interview practices, since the system relies on a fixed inventory of pre-labeled questions.

---

### Agentic System

The second option considered was a **fully agentic system**, where the LLM is given autonomy to steer the interview. Instead of selecting from a predefined set of questions, the agent can generate entirely new ones based on user responses, provided tools, and guiding instructions. It can also decide when a domain is complete, when to switch to another domain, and when to conclude the interview. In short, it acts as a true conversational agent with the ability to adapt dynamically.

#### Pros
- **Future-proof**: As LLMs improve (especially in reasoning and medical domains), the system can immediately benefit without redesigning workflows.
- **Easier integration of new knowledge**: New research or domain insights can be added as context (e.g., scraped medical literature), and the agent will incorporate them into its reasoning.
- **Highly adaptive**: The agent can personalize deeply based on user context, focusing more on concerning areas or digging into unexpected user responses.
- **Natural experience**: Feels more like speaking with a thoughtful clinician, rather than progressing through pre-written questions.
- **Flexible conversation steering**: The system can decide when to linger on a domain or move on, providing a more organic and responsive flow.

#### Cons
- **Harder to steer and predict**: Greater autonomy means less control over outputs. Outcomes are less predictable and require careful prompt design, structured reasoning, and detailed guidelines.
- **Reliance on LLM internal knowledge**: The agent draws heavily on its own medical knowledge, which increases risk of hallucinations.
  - Example: the model might assume that smoking strongly affects sleep quality, even if evidence is unclear. In this case, the cost is only suboptimal questioning, not incorrect medical advice, since the system never diagnoses or prescribes.
- **Latency and cost**: A more complex reasoning loop increases latency and requires larger models, raising costs.
  - Mitigation: this is acceptable because intake is a one-time process, not a daily-use feature. Quality and adaptability outweigh latency concerns. Future improvements may reduce cost and response times.

---

### Decision and rationale

After weighing both options, I chose to pursue the **agentic system**.

Its advantages — adaptability, personalization, and future-proofing — clearly outweigh the drawbacks. Most of the cons (steerability, hallucinations, latency, and cost) can be mitigated through careful prompt design, structured reasoning, and system improvements over time.

This approach aligns better with the product’s long-term direction: it has a much higher ceiling for improvement, can integrate new knowledge more easily, and creates a more compelling and natural user experience.

It is also more challenging and sophisticated to build, and seems more interesting to me, and fun!!

---

## Agentic workflow design

### Agent loop

The agent loop itself is deliberately simple.

At each turn, the system:
1. Gathers all relevant context (conversation history, current fields, to-be-collected fields, progress stats, retrieved questions).
2. Formats a prompt and sends it to the LLM.
3. Parses the structured response into a schema object (e.g. `IntakeInterviewTurn` or `PostIntakeInterviewTurn`).
4. Updates the `IntakeInterviewState` accordingly.
5. Returns the next follow-up message for the user.

Because the reasoning is pushed into structured schemas, the loop does little orchestration.
Its role is only to **supply context, run inference, and apply state updates**.
The agent itself — guided by schemas — decides what to do.

```python
def generate_reply(
        self,
        user_query: str,
        history: list[dict[str, str]],
        state: IntakeInterviewState,
        versbose: bool = False,
    ) -> tuple[str, IntakeInterviewState]:

    # prepare messages with context from user query, conversation history, interview state
    system_prompt = ...
    user_message ...
    messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    # run inference
    new_turn = self.llm.send_with_structured_response(
            messages=messages, response_format=IntakeInterviewTurn, verbose=versbose
        )

    # update state
    state.update_from_interview_turn(new_turn)
    return new_turn.followup, state

```

---

### Steering reasoning through schemas

The intelligence of the system is not hardcoded in the loop.
Instead, it is **steered through explicit data structures** that force the LLM to reason step by step:
- Interpret the latest user answer.
- Link it to prior context.
- Decide which values to update.
- Propose new fields if relevant.
- Review domain completeness.
- Select the next field and generate a follow-up.

This reasoning is captured in the `TurnAnalysis` schema

```python
class TurnAnalysis(BaseModel):
    response_interpretation: str   # interpret user’s answer (30–60 words) ...
    context_link: str              # connect to prior context (20–40 words) ...
    value_update_plan: list[str]   # which field keys to update
    completeness_review: str       # short reflection: continue vs mark complete ...
    next_fields_thoughs: str       # physician-style reflection on what’s next ...
    field_requests_to_create: list[str]  # new fields to create
```

By asking the LLM to fill this structure every turn, we “force” it to externalize its reasoning and keep control visible.
This makes the system predictable while still flexible.

---

### Meeting the LLM where it is

A central design principle is to **meet the LLM where it is**, rather than forcing it to adapt to app-centric schemas.

- **LLM-facing schemas** are designed to be **intuitive**: once the agent knows *what* it wants to do (e.g., update a value, mark a domain complete), the *how* is unambiguous.
- **Internal schemas** are designed for **our needs**: database storage, app logic, reporting.

The LLM-facing side gives the agent full expressive control, while the internal side translates that into usable application state.

---

### LLM-facing schemas

These schemas are the primary “language of thought” for the agent.
They allow it to create fields, update values, mark domains, or even close the interview.

- `IntakeFieldRequest` defines a new field and why it is relevant.
    ```python
    class IntakeFieldRequest(BaseModel):
        spec: IntakeFieldSpec   # field definition (domain, type, options ...)
        rationale: str          # why this field is relevant now
    ```

- `IntakeValueUpdate` represents a normalized value for an existing field.
    ```python
    class IntakeValueUpdate(BaseModel):
        key: str                # matches IntakeFieldSpec.key
        value: str              # formatted per value_type (e.g. "yes", "6to8h", "prefer_not_to_say") ...
    ```

- `IntakeInterviewTurn` the main payload for one turn of the interview.
    ```python
    class IntakeInterviewTurn(BaseModel):
        analysis: TurnAnalysis
        domains_to_mark_complete: list[intake_domain]
        mark_interview_complete: bool
        new_fields_to_collect: list[IntakeFieldRequest]
        value_updates: list[IntakeValueUpdate]
        next_field_selection: NextFieldSelection
        followup: str           # the reply to send to the user
    ```

Through these structures, the agent has full ability to steer the session.

---

### Internal schemas

Internal models focus on **state tracking, reporting, and downstream use**.
They are not meant for the LLM, but for us.

- `IntakeInterviewState` container for fields, stats, and interview completion.
    ```python
    class IntakeInterviewState(BaseModel):
        fields: dict[str, IntakeField]   # current fields
        stats: IntakeTurnStats           # progress across domains
        is_done: bool
    ```
- `HealthDataEntry` user-friendly representation of collected data.
    ```python
    class HealthDataEntry(BaseModel):
        name: str
        description: str
        rationale: str
        value: str
        options: list[str] | None
    ```
- `IntakeTurnStats` counters and domain-level progress tracking.
    ```python
    class IntakeTurnStats(BaseModel):
        total_turns: int
        total_target: int
        domain_stats: dict[intake_domain, DomainTurnStat]
    ```

These schemas keep track of collected data, progress against targets, and prepare user-facing summaries.

---

### Summary

- The **agent loop** is thin: context in, schema out, state updated.
- The **schemas** are where the real design lives.
- By **meeting the LLM where it is**, we reduce ambiguity and allow the agent to focus on decisions, not mechanics.
- **LLM-facing schemas** empower the agent; **internal schemas** serve the application and come with their self-contained update logic.

<!-- For detailed explanations of each schema and their design rationale, see [docs/data_models.md](data-models.md). -->


## Completeness logic and domain switching

### Design intuition

A useful analogy is to imagine a doctor conducting an intake interview in a room with **no clock**. Without time awareness, the doctor may lose track of pacing, dwell too long on one topic, and fail to cover other important areas. Now imagine the same doctor with a **clock on the wall** and a general time frame for the session — suddenly, pacing and balance become natural.

The same principle applies here: the agent cannot perceive time on its own, so we provide it with a structured “clock,” plus guidance in the form of soft limits and domain expertise. These three elements together form the **completeness logic**:

1. **A clock**: the agent sees total turns spent and remaining, plus per-domain counters. This provides situational awareness and prevents the interview from drifting indefinitely.

2. **Soft limits**: each domain has a target (e.g., 6 ±2 turns), and the interview has an overall target (e.g., 30 turns). These are not strict rules, but flexible guidelines. We can adjust them later to make the interview shorter, longer, or more thorough.

3. **Domain expertise**: the agent applies judgment. If a domain shows concerns, it may go over the target; if it appears stable, it may close it early. The goal is balance — to cover most domains sufficiently while focusing more deeply where the user’s answers reveal issues.


#### Example of what the agent sees

The structured progress view sent in the user message acts as the agent’s “clock”. It gives the agent situational awareness to pace the conversation, switch domains, and avoid over-focusing on a single area.

```markdown
## Session Progress (watch time, adjust pace)
- Total turns spent: 4
- Total turns left: 26
- Turns count per domain
  - `basic_info` 0 / 6 (+/- 2)
  - `lifestyle` 0 / 6 (+/- 2)
  - `physical_activity` 3 / 6 (+/- 2)
  - `sleep` 5 / 6 (+/- 2) [marked as completed]
  - `mental_health` 0 / 6 (+/- 2)
  - `nutrition` 0 / 6 (+/- 2)
  - `social_relations` 3 / 6 (+/- 2) [marked as completed]
  - `family_history` 0 / 6 (+/- 2)
  - `medical_history` 0 / 6 (+/- 2)
  - `substance_use` 2 / 6 (+/- 2) [marked as completed]
  - `personal_hygiene` 0 / 6 (+/- 2)
  - `current_health_status` 0 / 6 (+/- 2)
```

---

### How it works

Every turn, the agent receives a structured summary of progress (the “clock”). It includes:
- Total turns spent and left.
- Per-domain counts against soft targets.
- Which domains are already marked complete.

The agent then reasons through its `TurnAnalysis`, which includes an explicit `completeness_review` field. This requires it to reflect on:
- whether to continue in the current domain,
- whether to mark a domain complete,
- and whether to consider the interview itself complete.

If it decides a domain should be closed, it sets `domains_to_mark_complete`.
```python
domains_to_mark_complete: list[intake_domain]   # domains to mark complete this turn
```
If it judges the overall interview sufficiently covered, it sets `mark_interview_complete`.
```python
mark_interview_complete: bool   # true if the entire interview should be closed
```
These structured decisions directly update the `IntakeInterviewState`.

```python
def update_from_interview_turn(self, turn: IntakeInterviewTurn) -> None:
    # other updates here...

    # updating turns count
    self.stats.update(turn.next_field_selection.domain)

    # marking domains or interview complete
    for domain in set(turn.domains_to_mark_complete):
        self.stats.mark_completed(domain)

    if turn.mark_interview_complete:
        self.is_done = True
```
---


### Summary

- **Completeness logic** is based on three factors: time awareness (clock), soft limits (guidelines), and domain expertise (judgment).
- The agent is empowered to balance efficiency and depth across domains.
- Every turn includes a structured reasoning step that makes completeness decisions transparent.
- Domains or the entire interview can be marked complete explicitly, ensuring control stays with the agent while remaining interpretable.

## Retrieval (RAG) strategy

### Current approach

We maintain a **knowledge base** of the currated set of intake questions provided. These are ingested into **Qdrant**, a vector database, and stored with their keys, domains, labels, and options.

At each turn, we run **semantic queries** based on the most recent collected field and the most recent to-be-collected field. The top retrieved items are returned to the agent as **examples**, not rules.

Their purpose is to provide **inspiration** — mainly for phrasing, naming conventions, and option structures — while the agent retains full control over what to ask next. Retrieval is explicitly non-binding: if irrelevant, results are ignored.

---

### Future improvements

In the future, retrieval can extend beyond examples to bring in **medical literature** (e.g., PubMed or clinical guidelines). This would allow the agent to ground its reasoning in evidence, surfacing relevant **risk factors** or **associations** to guide follow-up questions.

- Example: if a user reports **daytime sleepiness**, retrieval might bring in research linking it with **sleep apnea risk factors**, prompting the agent to probe snoring, BMI, or apnea symptoms.
- Example: if a user reports **frequent reflux**, retrieval could surface links with **dietary habits** or **meal timing**, helping the agent decide what to ask next.

---

### Summary

- Current: retrieval draws from a **knowledge base of example questions**, queried via recent collected and pending fields.
- Use: results are **examples only**, guiding style and structure, never mandatory.
- Future: expand to **evidence-aware retrieval** from medical literature to enrich reasoning and follow-ups.

## Interview vs Post-interview modes

The system operates in two distinct modes, handled by two different agents:

1. **Interview agent**
   - This is the proactive mode.
   - The agent drives the intake interview, asking new questions, creating new fields, updating values, marking domains complete, and deciding when the overall interview should end.
   - It is responsible for the structured, exploratory flow of the conversation.

2. **Post-interview agent**
   - Once the interview agent has marked the session as complete, the flow switches to a passive mode.
   - In this mode, the agent no longer generates new questions.
   - Instead, it only **receives updates or corrections** from the user, creates new fields if the user introduces relevant information, and updates values accordingly.
   - Its role is purely to **acknowledge, confirm, and record**, without re-opening the interview.

This design allows the user to come back even after the interview is done and continue updating values or adding more information whenever needed.


## Future improvements

### Latency & cost

The current implementation already takes advantage of **caching** to reduce both cost and latency.
- The **system prompt** is fully static, with no dynamic placeholders, so it is cached in full.
- The **user message** is carefully structured so that stable sections are ordered first, maximizing token reuse.
This design means most of the prompt is served from cache, significantly reducing repeated inference costs.

Beyond caching, there are several future directions:

- **Perceived latency reduction**
  The agent could first perform the **analysis**, then generate and send the **follow-up question immediately** before completing the rest of the state updates.
  This mimics a real doctor who continues thinking and reflecting even after asking their next question.
  To implement this, the system would need **streaming responses** and asynchronous connections (e.g., WebSockets).

- **Model specialization for cost**
  A strong model can be used for the **analysis phase**, while a lighter, cheaper model finalizes field creation, value updates, and other structured outputs.
  This preserves reasoning quality while lowering overall cost.

### Scalability

The current system was not designed with **horizontal scalability** in mind:
- The application is **not stateless**, limiting its ability to scale efficiently across multiple nodes.
- The **PII detection** model currently runs inside the app rather than as a separate microservice, which slows down startup and further restricts scalability.

Future work should focus on making the app **stateless** and enabling clean **horizontal scaling**.
Separating services (e.g., PII handling) into independent microservices would also improve flexibility and startup performance.

### PII handling

Today, PII redaction happens **on the server side** immediately upon receiving data, before anything is written to storage. This ensures no unredacted PII enters the database.

A future improvement would be to move part of this responsibility **client-side**, redacting or stripping sensitive identifiers before data is even sent to the server. This would further reduce exposure risk and strengthen privacy guarantees.
