# Part B — Paper 13
## *RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation*

**Authors:** Fengji Zhang, Bei Chen, Yue Zhang, Jacky Keung, Jin Liu, Daoguang Zan, Yi Mao, Jian-Guang Lou, Weizhu Chen  
**Venue:** EMNLP 2023  
**Paper:** arXiv:2303.12570v3

> **Project relevance:** This is **not a memory-system paper**. Its useful contribution for our research is a retrieval pattern: **use the model's previous output to improve the next retrieval query** instead of relying on the original query alone.

---

# 1. The core problem

Standard retrieval-augmented code completion does:

```text
Incomplete code
     ↓
Retrieve related repository code
     ↓
Generate completion
```

The paper identifies a mismatch:

```text
Retrieval query
= unfinished code

But the retrieval target
= information needed for the intended completion
```

The unfinished code may be too weak to retrieve the exact information needed.

The paper's Figure 2 shows this with an API example: the first completion predicts incorrect API parameters; using that generated completion for another retrieval step finds the correct API signature.

**Paper:** pp. 1–2. fileciteturn61file0L69-L87

---

# 2. RepoCoder's core idea

RepoCoder makes retrieval and generation **iterative**.

```mermaid
flowchart LR
    A[Initial context]
    --> B[Retrieve]
    --> C[Generate]

    C --> D[Previous prediction]
    D --> B

    B --> E[Better retrieval]
    E --> C
```

### Iteration 1

```text
X
 ↓
Retrieve R(Crepo, X)
 ↓
Generate Y₁
```

### Iteration 2+

```text
X + previous prediction Y₁
 ↓
Retrieve R(Crepo, X, Y₁)
 ↓
Generate Y₂
```

The same retriever and generator are reused; their parameters are not changed between iterations.

**Paper:** §2.1, pp. 2–3. fileciteturn61file0L131-L160

---

# 3. How the retrieval query changes

The initial query uses the last `Sw` lines of unfinished code.

For later iterations, RepoCoder concatenates:

```text
last (Sw − Ss) lines of unfinished code
+
first Ss lines of previous prediction
```

So the generated prediction becomes **additional retrieval evidence**.

```text
Original context
       +
Model hypothesis
       ↓
More targeted retrieval
```

Important caveat from the paper:

> The generated completion may itself be incorrect.

The method works by using that prediction as **supplementary retrieval information**, not by assuming it is ground truth.

**Paper:** §2.2, pp. 3–4. fileciteturn61file0L163-L206

---

# 4. Why this matters beyond code completion

This is the most useful transferable idea:

```text
Query
 ↓
Retrieve
 ↓
Model forms a hypothesis / partial answer
 ↓
Use that output to refine retrieval
 ↓
Retrieve again
 ↓
Answer
```

For a memory system, the analogous pattern could be:

```mermaid
flowchart LR
    Q[User query]
    --> R1[Memory retrieval]
    --> A1[Initial reasoning]
    --> Q2[Refined retrieval query]
    --> R2[Memory retrieval]
    --> A2[Final reasoning]
```

This is a **project-level application of RepoCoder's retrieval-generation loop**; the paper itself evaluates repository code completion.

---

# 5. Retrieval database construction

RepoCoder builds a retrieval database by using a **sliding window over repository files**.

Each window contains contiguous lines:

```text
File
 ↓
Sliding window (Sw)
 ↓
Code snippet
```

The window moves by a fixed **sliding size (Ss)**.

At generation time, the retrieved snippets are inserted into the prompt together with the unfinished code.

The prompt includes each snippet's **original file path**, and at most `K` snippets are included depending on prompt length.

**Paper:** §2.2–2.3, pp. 3–4. fileciteturn61file0L163-L180 fileciteturn61file0L240-L251

---

# 6. Main experimental result

The paper creates **RepoEval**, covering:

```text
1. Line completion
2. API invocation completion
3. Function body completion
```

The first two are evaluated with:

**Exact Match (EM) + Edit Similarity (ES)**

Function completion uses repository **unit tests** and reports **Pass Rate (PR)**.

RepoCoder consistently improves over the In-File baseline.

For line completion with GPT-3.5-Turbo:

```text
In-File EM     = 40.56%
RepoCoder-2    = 56.81%
RepoCoder-3    = 57.00%
```

For API invocation completion:

```text
In-File EM     = 34.06%
RepoCoder-2    = 49.19%
RepoCoder-3    = 49.44%
```

The paper reports that with **two or more iterations**, RepoCoder consistently outperforms vanilla RAG across the tested language models.

**Paper:** Tables 2a/2b + §5.1, pp. 6–7. fileciteturn61file0L383-L417 fileciteturn61file0L426-L462

---

# 7. Retrieval quality is strongly connected to performance

The paper explicitly analyzes retrieved-code quality.

It finds that helpful snippets often:

- resemble the target completion
- contain examples of the target API usage

In a separate oracle-style analysis, RepoCoder's second iteration retrieves ground-truth API invocation examples more often than its first iteration.

The paper uses this to support its central claim:

> **The generated prediction can improve retrieval because it gives the retriever information closer to the intended target.**

**Paper:** §6.1, pp. 7–8. fileciteturn61file0L494-L542

---

# 8. There is a stopping problem

RepoCoder has an important limitation:

```text
Iteration 1
   ↓
Iteration 2
   ↓
Iteration 3
   ↓
?
```

The paper reports that:

- two iterations outperform vanilla RAG
- later iterations can become unstable
- finding the best stopping point automatically remains difficult

So the principle is **iterative retrieval**, not **retrieve indefinitely**.

This connects with other papers we read that found “more retrieval” is not automatically better.

**Paper:** Limitations, p. 9. fileciteturn61file0L631-L650

---

# 9. Another limitation: retrieval may have nothing useful to find

RepoCoder can provide little benefit when the repository has **few duplicated or related code patterns**.

Then:

```text
Better query
   ↓
Still no sufficiently relevant repository evidence
```

The paper therefore does not claim that iterative retrieval can create information that does not exist in the source repository.

**Paper:** p. 9. fileciteturn61file0L631-L637

---

# 10. What this gives our project

The most useful architecture idea is:

### Query refinement through intermediate reasoning

Instead of:

```text
Query → Retrieve once → Answer
```

consider testing:

```text
Query
 ↓
Retrieve
 ↓
Initial interpretation / hypothesis
 ↓
Refined query
 ↓
Retrieve again
 ↓
Final answer
```

This could be useful when the initial user query is:

- ambiguous
- underspecified
- semantically far from the relevant memory
- missing the exact terms used in stored memory

The paper does not test these memory scenarios; this is the architectural analogy we can take from the work.

---

# 11. Connection to previous papers

```text
CRAG
→ Evaluate whether retrieval is trustworthy.

SELF-RAG
→ Decide when to retrieve + critique retrieved evidence.

Lost in the Middle
→ Too much retrieved context can hurt.

LongMemEval
→ Improve indexing, query construction, and reading.

RepoCoder
→ Use the model's intermediate output to refine retrieval.
```

So RepoCoder mainly adds **iterative retrieval-query refinement**.

---

# 12. 6 things to remember

1. **A single retrieval query may not express the information needed for the final task.**
2. **An intermediate model prediction can provide a better retrieval signal.**
3. **RepoCoder repeatedly performs retrieval → generation.**
4. **The retriever and generator themselves remain unchanged.**
5. **Two iterations helped in the reported experiments, while more iterations can become unstable.**
6. **For our project, iterative memory retrieval is worth considering when the initial query is insufficient.**

---

# PPT — 5 slides

## Slide 1 — Problem
**Initial query may not match the information needed from the repository.**

## Slide 2 — RepoCoder

```text
Retrieve → Generate
      ↑       |
      |_______|
```

## Slide 3 — Query refinement

```text
Original context
+
Previous prediction
→ better retrieval query
```

## Slide 4 — Results
**RepoCoder improves over In-File and vanilla RAG in the reported experiments.**

## Slide 5 — Project relevance
**Retrieve → reason → refine query → retrieve again**

---

# Read these sections

**Must read:** §2.1 Overall Framework, §2.2 Code Retrieval, §5.1 Results, §6.1 Retrieval Quality.

**Skim:** §2.3 Code Generation.

**Skip initially:** Most benchmark-construction details, Related Work, and appendix.
