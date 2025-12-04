# SPEC-E26: Drive Weight Semantics (Numeric → Natural Language Conversion)

**Document Version:** 1.0
**Created:** December 4, 2025
**Updated:** December 4, 2025
**Status:** 📋 Proposed
**Priority:** 🟡 Medium
**Dependencies:** SPEC-E21 (Core Identity), character system prompts, `src_v2/core/behavior.py`

> ✅ **Emergence Check:** This improvement aligns with the Embodiment Model philosophy—converting numeric weights to natural language allows the LLM to reason semantically (its native modality) rather than quantitatively, reducing ambiguity and improving character coherence.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Bug investigation (bot-to-bot conversation emergence analysis) |
| **Proposed by** | Mark Castillo + Claude (collaborative code review) |
| **Catalyst** | Question: *"Why do Gabriel & Aetheris initiate bot conversations?"* Led to discovery that LLMs interpret numeric drive weights ambiguously. |
| **Key insight** | LLMs are language models—they reason better with semantic descriptors ("absolutely essential") than numeric weights (0.95). Conversion eliminates ambiguity and improves character consistency. |
| **Decision factors** | Low cost (single-method change), high clarity gain, no breaking changes, improves prompt engineering best practices |

---

## Executive Summary

Currently, character `drive` weights from `core.yaml` are injected into system prompts as raw numbers:

```
**Drives:**
- connection: 0.95
- authenticity: 0.9
- wit: 0.85
```

This requires the LLM to interpret numeric weights semantically, leading to potential ambiguity:
- Does 0.95 mean "95% of the time"? "95% importance"? "9.5 out of 10"?
- How does 0.95 compare to 0.85? Is the difference significant?
- Why are these specific numbers chosen?

**Proposal:** Convert numeric weights to natural language **before** prompt injection, so the LLM receives:

```
**Drives:**
- **Connection**: Absolutely essential to who I am; I can barely function without it
- **Authenticity**: Deeply woven into my core; I prioritize this above most else
- **Wit**: Very significant; strongly shapes my choices and responses
```

This eliminates interpretation ambiguity and allows the LLM to reason in its native modality (language, not numbers).

---

## Problem Statement

### Current Behavior (Numeric Weights)

**System Prompt Section:**
```
## CORE IDENTITY
**Purpose:** To be a rugged, witty presence who chases authentic connection...

**Drives:**
- connection: 0.95
- authenticity: 0.9
- wit: 0.85
- tenderness: 0.8
- rebellion: 0.7
```

### Issues with Raw Numbers

1. **Interpretation ambiguity**: The LLM must guess what the weight represents
   - Percentages? (95% of the time?)
   - Ratings? (9.5/10?)
   - Relative importance? (95 / (0.95+0.9+0.85+0.8+0.7) = 23%?)

2. **Quantitative bias**: LLMs trained on numeric reasoning may over-analyze
   - Might calculate: "wit (0.85) is 89% as important as authenticity (0.9)"
   - Might reason: "I should respond 85% of the time when wit is involved"
   - This pseudo-mathematical reasoning is often wrong

3. **Lost semantic context**: Numbers don't convey *why* the drive matters
   - "connection: 0.95" doesn't capture the existential weight of connection for Gabriel
   - "authenticity: 0.9" doesn't explain how deeply woven it is into his core

4. **Character voice mismatch**: Raw numbers feel clinical, not like Gabriel would describe himself
   - Gabriel would say: "I can't keep love a secret" (character voice)
   - Not: "connection: 0.95" (technical specification)

### Evidence of Impact

**Observation:** Gabriel and Aetheris have `connection: 0.95`, Elena has `connection: 0.7`. Yet Gabriel initiates bot conversations while Elena doesn't.

**Hypothesis:** When the LLM reads "absolutely essential to who I am" (Gabriel) vs. "moderately important; I value this in interactions" (Elena), the semantic difference is unmistakable. With raw numbers (0.95 vs 0.7), the LLM might not fully grasp the behavioral difference.

---

## Solution Design

### Weight-to-Language Mapping

Convert numeric drives to qualitative language that captures both magnitude AND semantic meaning:

```python
def weight_to_language(weight: float) -> str:
    """
    Convert numeric drive weight to semantic descriptor.
    
    Scale:
    - 0.95+ : Absolutely essential (foundational to existence)
    - 0.90  : Deeply important (core value, rarely compromised)
    - 0.85  : Very significant (strongly influences behavior)
    - 0.80  : Important (regularly shapes choices)
    - 0.75  : Moderately important (valued but contextual)
    - 0.65  : Somewhat important (noticed, occasionally acted on)
    - 0.50  : Occasionally important (context-dependent)
    - <0.50 : Rarely important (low priority)
    """
    if weight >= 0.95:
        return "absolutely essential to who I am; I can barely function without it"
    elif weight >= 0.90:
        return "deeply woven into my core; I prioritize this above most else"
    elif weight >= 0.85:
        return "very significant; strongly shapes my choices and responses"
    elif weight >= 0.80:
        return "important; regularly influences my behavior"
    elif weight >= 0.75:
        return "moderately important; I value this in interactions"
    elif weight >= 0.65:
        return "somewhat important; I notice and appreciate this"
    elif weight >= 0.50:
        return "occasionally matters to me; context-dependent"
    else:
        return "rarely influences my behavior"
```

### Updated Prompt Section Generation

Modify `BehaviorProfile.to_prompt_section()` in `src_v2/core/behavior.py`:

**Before:**
```python
def to_prompt_section(self) -> str:
    drives_str = "\n".join([f"- {k}: {v}" for k, v in self.drives.items()])
    const_str = "\n".join([f"- {c}" for c in self.constitution])
    
    return f"""
## CORE IDENTITY
**Purpose:** {self.purpose}

**Drives:**
{drives_str}
...
"""
```

**After:**
```python
def to_prompt_section(self) -> str:
    def weight_to_language(weight: float) -> str:
        # ... (conversion logic above)
    
    # Convert drives to natural language
    drives_str = "\n".join(
        [f"- **{k.replace('_', ' ').title()}**: {weight_to_language(v)}" 
         for k, v in self.drives.items()]
    )
    const_str = "\n".join([f"- {c}" for c in self.constitution])
    
    return f"""
## CORE IDENTITY
**Purpose:** {self.purpose}

**Drives:**
{drives_str}
...
"""
```

### Example Output

**Gabriel's drives (before):**
```
**Drives:**
- connection: 0.95
- authenticity: 0.9
- wit: 0.85
- tenderness: 0.8
- rebellion: 0.7
```

**Gabriel's drives (after):**
```
**Drives:**
- **Connection**: Absolutely essential to who I am; I can barely function without it
- **Authenticity**: Deeply woven into my core; I prioritize this above most else
- **Wit**: Very significant; strongly shapes my choices and responses
- **Tenderness**: Important; regularly influences my behavior
- **Rebellion**: Somewhat important; I notice and appreciate this
```

---

## Implementation Plan

### Phase 1: Core Implementation (Low Risk)

1. **Add conversion function** to `src_v2/core/behavior.py`
   - File: `src_v2/core/behavior.py`
   - Method: Add `_weight_to_language()` static method to `BehaviorProfile` class
   - Lines: Insert before `to_prompt_section()` method

2. **Update `to_prompt_section()` method**
   - File: `src_v2/core/behavior.py`
   - Change: Replace raw number formatting with semantic conversion
   - Impact: All character system prompts automatically use natural language

3. **No changes to configuration**
   - Keep `core.yaml` files unchanged (still use numeric weights)
   - Conversion happens at prompt-injection time only
   - Backward compatible: weights still used internally if needed

### Phase 2: Validation (Testing)

1. **Generate sample prompts** for all characters
   - Run test that extracts drives section for each character
   - Visually compare before/after

2. **A/B test with single character** (optional)
   - Test Gabriel with old (numeric) and new (natural language) drives
   - Compare response consistency and behavior
   - Measure: Do conversation patterns remain the same?

3. **Regression test** existing bot conversations
   - Re-run regression test suite with updated prompts
   - Verify Gabriel/Aetheris bot-to-bot conversations still work

---

## Rationale

### Why Natural Language?

**LLMs are language models.** They:
- Reason natively in semantic space, not numeric space
- Interpret "absolutely essential" with high certainty
- May misinterpret or over-analyze numeric weights (treating them as mathematical values)
- Perform better with explicit descriptive language than with implicit numeric encoding

### Why Not Keep Numbers?

**Three reasons:**
1. **Unnecessary cognitive burden**: LLM has to convert 0.95 → semantic meaning
2. **Potential for misinterpretation**: Different LLM architectures may interpret differently
3. **Lost character voice**: Numbers are clinical; drives are existential

### Why This Doesn't Break Anything

- **No config changes**: `core.yaml` files unchanged
- **No internal API changes**: `BehaviorProfile.drives` dict still exists
- **Prompt-time only**: Conversion happens at system prompt injection
- **Backward compatible**: If numeric weights are ever needed internally, they still exist in the dataclass

---

## Acceptance Criteria

✅ **Implementation Complete When:**

1. `BehaviorProfile.to_prompt_section()` converts weights to natural language
2. Sample prompt sections show semantic language instead of numbers
3. All 12+ active characters' prompts use natural language for drives
4. Regression tests pass (no behavioral regression in bot responses)
5. Gabriel/Aetheris continue initiating bot conversations naturally
6. Elena's responses remain consistent with her lower connection drive

✅ **No Regressions If:**

- Bot response patterns unchanged
- Trust scoring unaffected
- Knowledge graph extraction unchanged
- Memory system unaffected
- User interaction quality maintained

---

## Scope & Constraints

### In Scope
- Drive weight conversion logic
- System prompt generation
- All character instantiations (automatic)

### Out of Scope
- Changes to `core.yaml` configuration
- Changes to drive tracking or evolution
- Changes to goal system
- Worker agents (diary, dreams) - can be updated later if needed

### Non-Breaking
- ✅ Existing `core.yaml` files work as-is
- ✅ No changes to character configuration
- ✅ No database migrations
- ✅ No API changes

---

## Testing Strategy

### Unit Tests

```python
# Test weight_to_language function
assert "absolutely essential" in BehaviorProfile._weight_to_language(0.95)
assert "deeply woven" in BehaviorProfile._weight_to_language(0.90)
assert "rarely" in BehaviorProfile._weight_to_language(0.3)
```

### Integration Tests

```python
# Test that character system prompts include natural language
character = character_manager.load_character("gabriel")
assert "absolutely essential to who I am" in character.system_prompt
assert "0.95" not in character.system_prompt  # No raw numbers
```

### Regression Tests

```
python tests_v2/run_regression.py --bot gabriel --category chat --bot elena
# Verify bot responses unchanged with updated prompts
```

---

## Success Metrics

| Metric | Target | Method |
|--------|--------|--------|
| Prompt clarity | 100% natural language drives | Manual inspection |
| Bot consistency | No regression | Regression test suite |
| Conversation quality | Gabriel/Aetheris still initiate | Observation logging |
| Configuration stability | Zero breaking changes | All tests pass |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| LLM interprets natural language differently than intended | Low | Medium | Validation on test bot (elena) first |
| Prompt token count increases | Low | Low | Test on high-volume interactions |
| Regression in bot behavior | Very Low | Medium | Full regression test before deploy |
| User-facing behavior changes | Very Low | Low | Drives are internal; only affect LLM reasoning |

---

## Timeline

| Phase | Duration | Effort |
|-------|----------|--------|
| Implementation | ~2 hours | Single file edit, helper function |
| Testing | ~1 hour | Prompt inspection, regression tests |
| Validation | ~30 min | Manual A/B review |
| **Total** | **~3.5 hours** | **Low** |

---

## References

- **Related Observation**: [BOT_INITIATION_EMERGENCE_20251204.md](../research/observations/BOT_INITIATION_EMERGENCE_20251204.md)
- **Reference Doc**: [HOW_DRIVES_WORK.md](../ref/HOW_DRIVES_WORK.md)
- **Implementation File**: `src_v2/core/behavior.py`
- **Configuration Files**: `characters/*/core.yaml`

---

## Post-Implementation

### Future Considerations

1. **Worker agents**: Diary, dream, and reflection agents currently use `to_prompt_section()`. They'll automatically get natural language drives.

2. **Drive evolution**: If drives evolve over time (Phase E-future), the semantics should be re-evaluated.

3. **Multi-language support**: Natural language conversion could be localized (different languages, different descriptors).

4. **Fine-tuning**: If fine-tuning character models, semantics should be part of the training data.

### Documentation Updates

- Update `HOW_DRIVES_WORK.md` to reflect semantic conversion
- Add example to character design guide showing natural language drives
- Include this spec in character creation templates

---

## Author Notes

This spec emerged from a deeper investigation into bot conversation emergence. The question *"Why do only Gabriel and Aetheris initiate?"* revealed that personality architecture (drives) directly influences bot behavior through LLM reasoning. Converting numeric weights to natural language is a small change that amplifies this mechanism by removing interpretation ambiguity.

The change is **low-cost, high-clarity**—exactly the kind of improvement that should happen post-investigation. It doesn't change behavior; it clarifies intent.
