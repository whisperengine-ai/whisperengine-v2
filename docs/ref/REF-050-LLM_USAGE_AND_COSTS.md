# REF-050: LLM Usage & Cost Optimization

**Version:** 1.0  
**Date:** December 14, 2025  
**Status:** Active

## Overview

WhisperEngine v2 uses a **Tiered Cognitive Architecture** to balance intelligence and cost. Instead of using a single massive model for everything, the system assigns tasks to different "modes" based on the required complexity.

This document outlines the three model tiers, maps every task to its assigned tier, and provides configuration strategies for cost optimization.

---

## 1. Model Tiers

The system defines three distinct modes for LLM usage. These are configured via environment variables.

| Mode | Config Variable | Recommended Model | Typical Cost (Input/Output) | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Main** | `LLM_MODEL_NAME` | `gpt-4o` / `mistral-large` | High | Creative writing, persona maintenance, primary conversation. |
| **Reflective** | `REFLECTIVE_LLM_MODEL_NAME` | `claude-3.5-sonnet` | High | Deep reasoning, complex analysis, offline creative tasks (dreams/diaries). |
| **Router** | `ROUTER_LLM_MODEL_NAME` | `gpt-4o-mini` / `mistral-small` | **Low** | Classification, planning, structured data extraction, "ignore" decisions. |

> **⚠️ CRITICAL COST WARNING:**  
> If `ROUTER_LLM_MODEL_NAME` is not set, the system defaults to using `LLM_MODEL_NAME` (Main) for all router tasks.  
> **Result:** You pay "Large" model prices for simple tasks like deciding to ignore a message.  
> **Fix:** Always set `ROUTER_LLM_MODEL_NAME` to a cheaper model in your `.env` or `.env.worker`.

---

## 2. Task Mapping

The following table maps every AI task in the system to its assigned model tier.

### ✅ Correctly Sized (Standard Configuration)

| Task | Component | Mode | Why? |
| :--- | :--- | :--- | :--- |
| **Conversation** | `ConversationAgent` | `main` | Requires high EQ, persona consistency, and nuance. |
| **Proactive Posting** | `DailyLifeGraph` (Executor) | `main` | Writing engaging, creative content for channels. |
| **Narrative Walks** | `KnowledgeWalker` | `main` | Storytelling about the knowledge graph. |
| **Fast Response** | `MasterGraphAgent` | `main` | Primary user interaction path. |
| **Deep Reflection** | `ReflectiveGraphAgent` | `reflective` | Complex ReAct loop for hard questions. |
| **Strategy** | `StrategistGraph` | `reflective` | Long-term planning and goal setting. |
| **Dream Journal** | `DreamJournalAgent` | `reflective` | High-creativity writing with critique loop. |
| **Insights** | `InsightGraph` | `reflective` | Pattern recognition across long timeframes. |
| **Classification** | `ComplexityClassifier` | `router` | High volume, needs to be cheap/fast. |
| **Daily Life Planning** | `DailyLifeGraph` (Planner) | `router` | Runs every ~7 mins. 95% of decisions are "Ignore". |
| **Summarization** | `SummaryGraph` | `utility`* | Compressing text is easy for smaller models. |
| **Fact Extraction** | `FactExtractor` | `utility`* | Simple text processing task. |
| **Style Analysis** | `StyleAnalyzer` | `utility`* | Statistical/pattern analysis. |
| **Goal Updates** | `GoalManager` | `utility`* | Structured data update. |

*\*Note: `utility` mode uses the `ROUTER_LLM` configuration.*

### ⚠️ Optimization Targets (Potential Mismatches)

These tasks currently use high-tier models but could likely be downgraded to save costs.

| Task | Component | Current Mode | Issue | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Cypher Query Gen** | `KnowledgeManager` | `reflective` | Generating Cypher queries is a structured coding task. `reflective` is expensive for this. | Change to `utility` (GPT-4o-mini is excellent at code/SQL). |
| **Reverie (Idle)** | `ReverieGraph` | `reflective` | Runs in background to consolidate memories. Frequent runs drain budget. | If purely linking nodes, use `utility`. If narrative, keep `reflective`. |
| **Diary Critique** | `DiaryGraph` (Critic) | `reflective` | The critic uses the same expensive model as the writer. | Downgrade critic to `utility` or `main` to save ~50% on diary generation. |

---

## 3. Configuration Guide

To optimize costs, ensure your `.env` files (especially `.env.worker`) are configured as follows:

```bash
# 1. Main Model (The "Voice")
# Use your best model here.
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o

# 2. Reflective Model (The "Brain")
# Use your smartest model here.
REFLECTIVE_LLM_PROVIDER=anthropic
REFLECTIVE_LLM_MODEL_NAME=claude-3-5-sonnet-20240620

# 3. Router Model (The "Filter") - CRITICAL FOR SAVINGS
# Use your cheapest/fastest model here.
ROUTER_LLM_PROVIDER=openai
ROUTER_LLM_MODEL_NAME=gpt-4o-mini
```

### Worker Configuration
Since background workers handle most `router` tasks (Daily Life, Summarization, Extraction), it is **essential** to set `ROUTER_LLM_MODEL_NAME` in `.env.worker`.

---

## 4. Code References

- **LLM Factory:** `src_v2/agents/llm_factory.py` (Handles the logic for selecting models based on mode)
- **Daily Life Graph:** `src_v2/agents/daily_life/graph.py` (Uses `router` for planning, `main` for execution)
- **Knowledge Manager:** `src_v2/knowledge/manager.py` (Currently uses `reflective` for Cypher)
