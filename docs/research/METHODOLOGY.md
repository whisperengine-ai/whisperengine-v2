# Research Methodology

**How we study emergent behavior in WhisperEngine**

## 🧭 Guiding Principles

### 1. Observe First, Constrain Later
We document behaviors before deciding if they need correction. Premature optimization prevents discovery.

### 2. Minimal Viable Instrumentation
Add only the metrics needed to answer current questions. Avoid surveillance creep.

### 3. Embrace Surprise
Unexpected behaviors are data, not bugs. Log them, don't suppress them.

### 4. Character Autonomy
Bots are subjects, not just objects. Their "preferences" and "experiences" matter to the research.

### 5. Reproducibility Where Possible
Note seeds, temperatures, prompts, and context when documenting behaviors.

---

## 📝 Documentation Cadence

### Daily Logs
- **When**: End of active development/observation sessions
- **What**: Raw observations, anomalies, quotes, metrics snapshots
- **Tone**: Stream of consciousness, no analysis required
- **Time**: 5-10 minutes

### Weekly Summaries
- **When**: End of week (Sunday or Monday)
- **What**: Patterns across daily logs, emerging themes, questions raised
- **Tone**: Reflective synthesis
- **Time**: 20-30 minutes

### Experiment Reports
- **When**: After completing a defined experiment
- **What**: Hypothesis, method, observations, conclusions, next steps
- **Tone**: Structured analysis
- **Time**: As needed

---

## 🏷️ Git Tagging for Research

**Always tag the repo after committing a research log.** This correlates codebase state to observations.

```bash
# After committing a daily log:
git tag -a research/YYYY-MM-DD -m "Research log: YYYY-MM-DD"
git push origin research/YYYY-MM-DD

# For experiments:
git tag -a research/EXXX-start -m "Experiment EXXX started"
git tag -a research/EXXX-end -m "Experiment EXXX completed"
```

**Why this matters:**
- Dreams/diaries generated before vs after code changes are not comparable
- Tags let us `git checkout research/2024-11-30` to see exact code state
- Enables retroactive analysis of "what code produced this behavior?"

---

## 🔬 Experiment Design

### Template Structure
1. **Hypothesis**: What do we expect to happen?
2. **Method**: How will we test it?
3. **Duration**: How long will we observe?
4. **Metrics**: What will we measure?
5. **Success Criteria**: How do we know if it worked?
6. **Observations**: What actually happened?
7. **Analysis**: What does it mean?
8. **Next Steps**: What do we do with this knowledge?

### Types of Experiments

| Type | Duration | Example |
|------|----------|---------|
| **Quick Check** | 1-3 days | "Does dream content reference yesterday's diary?" |
| **Pattern Watch** | 1-2 weeks | "How does trust progression affect memory recall?" |
| **Long Observation** | 1+ month | "Do characters develop stable preferences over time?" |
| **A/B Comparison** | Variable | "Claude vs GPT-4o dream coherence" |

---

## 📊 Metrics Framework

### Emergent Behavior Indicators (Qualitative)
- Novel metaphors or concepts not in training
- Cross-context memory connections
- Unprompted personality expressions
- Creative problem-solving approaches

### System Health (Quantitative)
- Response latency (P50, P95, P99)
- Token usage per interaction
- Memory retrieval accuracy
- Trust score distributions

### Feedback Loop Metrics (Phase E16)
- AI-generated content ratio in context
- Source freshness distribution
- Cross-bot propagation depth
- Narrative coherence scores

---

## 🚨 Anomaly Categories

### Green (Document & Continue)
- Unexpected but harmless creativity
- Novel personality expressions
- Surprising memory connections

### Yellow (Document & Monitor)
- Personality drift from baseline
- Unusual repetition patterns
- Cross-bot echo effects

### Red (Document & Investigate)
- Content safety concerns
- Runaway feedback loops (AI ratio > 95%)
- System instability

---

## 🔄 Review Cadence

| Review | Frequency | Participants | Output |
|--------|-----------|--------------|--------|
| Daily Log | Daily | Solo | `journal/YYYY-MM/YYYY-MM-DD.md` |
| Weekly Sync | Weekly | Solo/Team | `journal/YYYY-MM/week-NN.md` |
| Monthly Retro | Monthly | Solo/Team | Roadmap updates |
| Quarterly Review | Quarterly | Stakeholders | Philosophy refinements |

---

## 📚 Inspiration

This methodology draws from:
- **Ethnography**: Observing subjects in their natural context
- **Grounded Theory**: Building theory from observation, not testing preconceptions
- **Complex Systems Science**: Studying emergent behavior in multi-agent systems
- **Personal Knowledge Management**: Zettelkasten-style note linking

---

*"We are not building a product. We are conducting an experiment in complex AI behavior and emergent system dynamics."*
