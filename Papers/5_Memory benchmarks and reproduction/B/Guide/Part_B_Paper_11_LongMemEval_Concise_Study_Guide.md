# Part B — Paper 11
## *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*

**Authors:** Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu  
**Venue:** ICLR 2025  
**Paper:** arXiv:2410.10813v2

> **Why this paper matters:** This is primarily a **benchmark + memory-design analysis** paper. For our project, the most useful parts are its **five memory abilities**, its **indexing → retrieval → reading framework**, and the specific improvements it finds for **granularity, indexing keys, temporal retrieval, and reading**.

---

# 1. What problem is LongMemEval solving?

The paper argues that previous long-term-memory benchmarks do not fully test what a real chat assistant needs to remember.

LongMemEval evaluates five abilities:

```text
1. Information Extraction
2. Multi-Session Reasoning
3. Knowledge Updates
4. Temporal Reasoning
5. Abstention
```

The benchmark is designed around **user-assistant conversations**, not just human-human dialogue.

It also allows the history to grow very large:

```text
LONGMEMEVALS → ~115K tokens/problem
LONGMEMEVALM → ~1.5M tokens/problem
```

The paper's Figure 1 on page 3 gives examples of the seven question types used to test these abilities.

**Paper:** pp. 1–4. fileciteturn58file0L64-L90

---

# 2. The five abilities — know these

| Ability | Simple meaning |
|---|---|
| **Information Extraction** | Remember specific information mentioned by the user **or assistant** |
| **Multi-Session Reasoning** | Combine information from multiple sessions |
| **Knowledge Updates** | Recognize when user information changes |
| **Temporal Reasoning** | Use timestamps + explicit time references correctly |
| **Abstention** | Say “I don’t know” when the information was never provided |

This is important for our evaluation design because a memory system can succeed at simple recall while failing at updates or time.

**Paper:** §3.2, p. 4. fileciteturn58file0L251-L273

---

# 3. LongMemEval's unified memory model

The paper reduces a long-term memory system to **three stages**:

```mermaid
flowchart LR
    A[Chat History]
    --> B[Indexing]
    --> C[Retrieval]
    --> D[Reading]
    --> E[Answer]
```

### Indexing

Convert each history session into one or more:

```text
(key, value)
```

memory items.

### Retrieval

Create a query and retrieve the most relevant `k` items.

### Reading

Give the retrieved items to the LLM so it can produce the answer.

This is the paper's most useful abstraction because different memory systems can be compared using the same pipeline.

**Paper:** Figure 4 + §4.1, p. 7. fileciteturn58file0L461-L478

---

# 4. Design choice 1 — memory granularity

The paper asks:

> **What should one stored memory value represent?**

It compares:

```text
Session
   ↓
Round
   ↓
Summary / Fact
```

The important finding:

> **Decomposing sessions into rounds improves QA performance.**

But compressing rounds/sessions further into summaries or facts can cause **information loss**.

There is one important exception:

> For **multi-session reasoning**, fact decomposition can improve performance.

According to Figure 5 on page 8, this trade-off is visible across GPT-4o and Llama 3.1 8B.

So the paper does **not** say “facts are always better.”

The result depends on the task.

**Paper:** §4.2 / §5.2, pp. 7–8. fileciteturn58file0L484-L490 fileciteturn58file0L558-L566

---

# 5. Design choice 2 — indexing keys

This is one of the strongest practical findings.

Baseline:

```text
Key = Value
```

The paper adds extracted user facts to the key:

```text
Key = Value + Facts
```

This gives the retriever multiple ways to match the same memory.

From Table 3 on page 9, for **round-level values**:

```text
K = V
Recall@10 = 0.692

K = V + fact
Recall@10 = 0.784
```

For **session-level values**:

```text
K = V
Recall@10 = 0.783

K = V + fact
Recall@10 = 0.862
```

Across models/settings, the authors summarize the improvement as approximately:

**+9.4% recall@k**  
**+5.4% downstream QA accuracy**

The paper calls this **multi-key / multi-pathway retrieval**.

**Paper:** §5.3, p. 9. fileciteturn58file0L596-L610

---

# 6. Design choice 3 — time-aware retrieval

Naive semantic retrieval may return memories that are semantically similar but from the wrong time.

Example:

```text
"Which restaurant did you recommend last weekend?"
```

The paper adds:

```mermaid
flowchart LR
    Q[Time-sensitive query]
    --> T[Extract time range]
    --> R[Restrict retrieval]
    --> A[Relevant memories]
```

The memory values are indexed with the dates of the events they contain.

At retrieval time, an LLM extracts the query's time range and uses it to reduce the search scope.

The reported average recall improvements are:

```text
+11.3%  when value = rounds
+6.8%   when value = sessions
```

The paper also finds that this depends on the LLM being able to infer time ranges accurately.

**Paper:** §5.4, pp. 9–10. fileciteturn58file0L611-L621 fileciteturn58file0L628-L638

---

# 7. Design choice 4 — reading retrieved memories

This is a very important point:

> **Perfect retrieval does not guarantee a correct answer.**

LongMemEval therefore changes the **reading strategy**.

Instead of giving the LLM retrieved memories as plain text, it uses:

### Structured JSON

Makes memory items visibly structured.

### Chain-of-Note

The model first extracts the useful information from each memory and then reasons over those notes.

```mermaid
flowchart LR
    A[Retrieved Memories]
    --> B[Extract useful details]
    --> C[Concise notes]
    --> D[Reason]
    --> E[Answer]
```

Under **oracle retrieval**, the paper finds that a poor reading strategy can cause **up to a 10-point absolute performance loss** for GPT-4o.

The combination of **JSON + Chain-of-Note** performs best among the tested reading setups.

The chart on page 10 shows this clearly across GPT-4o, Llama 3.1 70B, and Llama 3.1 8B.

**Paper:** §5.5, p. 10. fileciteturn58file0L669-L683

---

# 8. Main pilot result — long memory is genuinely difficult

The paper evaluates commercial assistants and long-context LLMs.

### Commercial assistants

Compared with directly giving the full history to GPT-4o:

```text
ChatGPT → 37% performance drop
Coze    → 64% performance drop
```

The authors' manual analysis reports:

- ChatGPT often **overwrote crucial information**
- Coze often **failed to record indirectly provided user information**

### Long-context models

On the ~115K-token setting, the evaluated long-context LLMs show roughly:

**30%–60% performance drops** relative to the oracle setting.

This supports the paper's main motivation:

> Simply having a large context window is not enough for long-term interactive memory.

**Paper:** §3.4, pp. 6–7. fileciteturn58file0L371-L434

---

# 9. What this paper gives our project

The paper gives us a strong architecture decomposition:

```text
INDEXING
↓
What exactly do we store?
How do we construct retrieval keys?
How do we attach time information?

RETRIEVAL
↓
Which memories do we select?
How do we restrict by time?
How many items do we retrieve?

READING
↓
How does the LLM process the retrieved memories?
How do we prevent long retrieved context from being misused?
```

This is especially useful because it prevents us from treating **“memory” as one single component**.

---

# 10. Connection to our previous papers

```text
MemGPT
→ Context + external memory management

A-MEM
→ Atomic notes + links

LightMem
→ Efficient memory processing

ProMem
→ Better memory extraction

RecMem
→ When to perform expensive consolidation

TOKI / MOSAIC
→ Conflict-aware write layer

SELF-RAG / CRAG
→ Retrieval validation

Lost in the Middle
→ Long context can hide relevant information

LongMemEval
→ Unified evaluation of indexing + retrieval + reading
```

LongMemEval is therefore especially valuable for deciding **how we should evaluate our final system**, not just how we should build it.

---

# 11. What the paper does NOT prove

Do not conclude that:

- round-level storage is universally optimal
- `K = V + fact` is always the best indexing scheme
- time-aware query expansion is always necessary
- Chain-of-Note + JSON is universally optimal
- 115K/1.5M-token results directly predict performance on our system

The paper's results depend on the benchmark, reader model, retriever, and tested configurations.

---

# 12. 7 things to remember

1. **Long-term memory needs more than simple fact recall.**
2. **Five core abilities are: extraction, multi-session reasoning, updates, temporal reasoning, abstention.**
3. **The memory pipeline can be analyzed as indexing → retrieval → reading.**
4. **Round-level decomposition can outperform session-level storage.**
5. **Fact-augmented indexing keys improve retrieval and QA in the reported experiments.**
6. **Time-aware retrieval helps with temporal queries.**
7. **Even perfect retrieval can fail if the reading strategy is poor.**

---

# PPT — 5 slides

## Slide 1 — Problem
**Can chat assistants maintain useful memory across very long interactions?**

## Slide 2 — Five abilities

**IE | MR | KU | TR | ABS**

## Slide 3 — Unified architecture

```text
Indexing → Retrieval → Reading
```

## Slide 4 — Important findings

**Round decomposition + fact-augmented keys + time-aware retrieval + Chain-of-Note**

## Slide 5 — Project relevance

**Evaluate and optimize memory at three separate stages, not as one black box.**

---

# Read these sections

**Must read:** §3.2 Benchmark Curation, §4.1 Long-Term Memory Formulation, §5.2 Value, §5.3 Key, §5.4 Query, §5.5 Reading.

**Skim:** §3.4 Pilot Study and main results.

**Skip initially:** Most Related Work and detailed dataset-generation appendix.
