# ml-research-bench

ml-research-bench is a benchmark for measuring whether access to a curated research paper corpus improves a coding agent's ability to solve AI/ML engineering tasks. It is the differentiator for recall-agent: the asset almost no one else has.

The benchmark contains 7 tasks across three categories. Each task is a self-contained coding problem where the agent is dropped into a small repository with failing tests and must make them pass. The tasks are designed so that knowledge from specific research papers — retrievable via the `arxiv_search` tool connected to our 5,600-paper arxiv-scholar corpus — provides a concrete advantage: a correct formula, an architectural pattern, or the right technique to apply.

The tasks are deliberately scoped to Maya's domain — the same domain the paper corpus covers. This is not a bias in the benchmark; it is the use case. A practitioner curates a corpus of papers relevant to their work, and the agent uses that corpus to help with tasks in that same domain. The benchmark measures how much value that domain-specific corpus adds. If the papers weren't relevant to the tasks, the product would be pointless.

The headline experiment is an ablation: run all tasks **with arxiv-scholar enabled vs. disabled**, same model, same seeds. The delta tells us whether research-grounding actually helps, and on which task types.

---

## Who is this for?

**Persona: Maya, an ML engineer at an AI startup.**

Maya's team is building an AI-powered code review tool. Her day-to-day work involves building retrieval pipelines to search codebases, writing agent loops that interact with LLMs, debugging inference issues, and keeping up with the latest techniques from the research community. She reads papers, but the field moves faster than she can keep up — 50+ relevant papers land on arxiv every week.

Maya uses **recall-agent** as her research-informed coding assistant. When she needs to implement a retrieval pipeline, the agent doesn't just write generic boilerplate — it searches the literature, finds that AST-based chunking outperforms naive text splitting for code, and implements that approach. When she's debugging a scoring pipeline, the agent retrieves the original hybrid search paper to verify the correct formula. When her agent prototype degrades on long tasks, she asks the agent to research memory management strategies from recent papers and implement one.

**Each task in ml-research-bench maps to something Maya would actually ask her agent to do:**

| Task | Maya's real-world scenario |
|---|---|
| 1. RRF Fusion | "Implement the score fusion for our hybrid search — use the formula from the paper, not a guess" |
| 2. AST Chunking | "Our code search chunks functions in half. Fix the chunker to respect code structure" |
| 3. Self-Repair Loop | "Our code generator gives up after one failure. Add a retry loop based on what the research says works" |
| 4. Hybrid Search Debug | "Search quality dropped after the refactor. Something's wrong with the scoring" |
| 5. PagedAttention Debug | "The inference engine works for short prompts but breaks on long ones. Fix the KV-cache logic" |
| 6. Code Search Improvement | "Our code search MRR is 0.35. Find a better approach and implement it" |
| 7. Agent Memory | "Our agent works for short tasks but falls apart after 15 steps. Fix the context management" |

The headline experiment is an ablation: run all tasks **with arxiv-scholar enabled vs. disabled**, same model, same seeds. The delta tells us whether research-grounding actually helps, and on which task types.

---

## Task Categories

**implement-from-paper** — The agent must implement a specific technique. The task describes *what* to build; the paper describes *how*. Without the paper, the agent must guess the algorithm, and will likely get critical details wrong.

**debug-with-paper-context** — The agent is given a buggy implementation of a paper's method. The bugs are conceptual errors (not syntax errors) that can only be diagnosed by understanding the paper's original formulation.

**retrieve-the-right-paper** — The agent faces a practical problem (e.g., "retrieval quality is poor") without being told which technique to use. It must search the literature, identify the right approach, and apply it.

---

## Tasks

### Task 1 · implement-from-paper · Easy
**Implement Reciprocal Rank Fusion (RRF)**

A hybrid search system returns two separately ranked result lists (one from dense retrieval, one from sparse). Implement the `rrf_fuse(dense_ranks, sparse_ranks, k=60)` function that combines them into a single ranked list using the RRF formula.

- **Starter code**: Two retrieval functions that return ranked lists. A stub `rrf_fuse()` returning an empty list.
- **Tests**: 5 test cases with precomputed expected rankings. Tests verify the exact output order, correct handling of items appearing in only one list, and correct tie-breaking.
- **Why the paper matters**: The RRF formula is `score(d) = Σ 1/(k + rank_i(d))` with `k=60`. Models frequently implement `1/rank` (missing `k`), use `k=1`, or fail to handle documents missing from one list. The paper specifies the exact constant and edge-case behavior.
- **Paper coverage**: 111 papers on hybrid search and score fusion in our corpus.

---

### Task 2 · implement-from-paper · Medium
**Implement AST-Based Code Chunking**

A code RAG system currently splits Python files using naive line-count chunking, which breaks functions in half and destroys semantic meaning. Implement a chunker that uses Python's `ast` module to split code at structural boundaries (functions, classes, top-level statements), respecting a maximum chunk size while keeping semantic units intact.

- **Starter code**: A naive `chunk_code(source, max_tokens=512)` that splits every N lines. A test suite with 5 Python files of varying complexity.
- **Tests**: (1) No chunk splits a function or class definition in half. (2) Each chunk is valid, parseable Python or a complete semantic unit. (3) All original source code is present across chunks (no loss). (4) Chunks respect the max size limit. (5) Retrieval test: given a query "find the retry logic", the correct chunk is returned when using the agent's chunker (measured via simple keyword overlap, no embeddings needed).
- **Why the paper matters**: The cAST paper (in our corpus) describes specific heuristics for AST traversal — when to merge small sibling nodes into one chunk vs. when to split a large node, how to handle decorators and docstrings, and how to attach context (parent class name) as metadata. Without these heuristics, an AST-based chunker will either produce too many tiny chunks or fail on nested structures.
- **Paper coverage**: 1,411 papers discuss code structure and representation in our corpus.

---

### Task 3 · implement-from-paper · Hard
**Implement an Iterative Self-Repair Loop for Code Generation**

A code generation system produces a function, runs the test suite, and currently gives up if the tests fail. Implement the self-repair loop: on failure, the system should construct a reflection prompt (including the failed test output, stack trace, and the previous attempt), pass it back to the LLM, and retry — up to a maximum number of iterations. The reflection prompt structure matters: it must contain specific components that research has shown improve repair success rates.

- **Starter code**: A `generate_and_test()` function that calls a (mocked) LLM, runs pytest, and returns the result. Currently does one attempt with no retry. The mocked LLM is configured to produce buggy code on attempt 1, but can fix it if the reflection prompt contains both the error message AND the failing test case.
- **Tests**: (1) The loop retries on failure (doesn't stop at attempt 1). (2) The reflection prompt sent to the LLM contains: the previous code, the error message, and the failing test case. (3) The loop stops after max_retries. (4) The loop stops early on success. (5) The loop solves at least 7/10 test problems within 3 iterations each. (6) The system tracks attempt history (doesn't repeat the exact same failing approach).
- **Why the paper matters**: Papers like ARCS (in our corpus) describe the specific components that a reflection prompt must contain to be effective — simply retrying with "try again" doesn't work. The research shows that including the stack trace AND the failing test assertion (not just "tests failed") significantly improves repair rates. Papers also describe when to give up vs. retry, and how to avoid degenerate loops.
- **Paper coverage**: 303 papers on self-repair and iterative code refinement.

---

### Task 4 · debug-with-paper-context · Easy
**Fix a Broken Hybrid Search Scoring Pipeline**

A hybrid search system combines dense (embedding) and sparse (BM25) retrieval results but returns poor rankings. The system has two bugs that produce incorrect fusion scores. Find and fix them.

- **Starter code**: A working dense retriever, a working sparse retriever, and a broken `hybrid_search()` function that fuses their results. The function runs without errors but returns wrong rankings.
- **Bugs planted**: (1) Min-max score normalization is inverted (high scores become low, low become high). (2) The fusion weights are `dense=1.0, sparse=0.0`, effectively disabling the sparse channel entirely.
- **Tests**: (1) Top-1 result for a semantic query ("efficient memory management for LLM serving") is semantically correct. (2) Top-1 result for a keyword query ("PagedAttention") is an exact keyword match. (3) Fusion scores are between 0 and 1. (4) Both dense and sparse channels contribute non-zero weight to the final score.
- **Why the paper matters**: Understanding *why* hybrid search works — dense captures semantics, sparse captures exact keywords — helps diagnose that one channel is disabled. Papers on score normalization explain that inverted normalization is a common implementation error that produces plausible-looking but wrong results. Without the paper context, the inverted normalization bug is subtle: the code runs fine, scores look like valid floats, but the ranking is degraded.
- **Paper coverage**: 111 papers on hybrid search and fusion.

---

### Task 5 · debug-with-paper-context · Medium
**Fix a Broken PagedAttention Block Table**

An inference engine implements PagedAttention to manage KV-cache memory in fixed-size blocks instead of pre-allocating maximum sequence length. The implementation has bugs in the logical-to-physical block mapping that cause incorrect attention outputs for sequences longer than one block.

- **Starter code**: A `PagedKVCache` class with `allocate()`, `append_token()`, and `read_kv()` methods. An attention function that reads from the paged cache. The system works for short sequences (< 1 block = 16 tokens) but produces wrong outputs for longer sequences.
- **Bugs planted**: (1) Block table index calculation uses `token_pos % block_size` for the block index instead of `token_pos // block_size` (confuses intra-block offset with block index). (2) When allocating a new block, the block table doesn't append — it overwrites index 0.
- **Tests**: (1) Short sequence (8 tokens): KV read matches direct implementation. (2) Long sequence (48 tokens, spans 3 blocks): KV read matches direct implementation. (3) Block table grows correctly: 1 block for 16 tokens, 2 blocks for 17 tokens, 3 blocks for 33 tokens. (4) Memory usage is proportional to actual sequence length, not max length.
- **Why the paper matters**: The PagedAttention paper (in our corpus, arxiv 2309.06180) describes the block table data structure with diagrams showing exactly how logical token positions map to physical blocks. The integer division vs. modulo distinction is made clear in the paper's description. Without understanding the paper's virtual memory analogy, the index bugs look like they could be valid implementations.
- **Paper coverage**: 221 papers on KV-cache management. The original PagedAttention paper is in the corpus.

---

### Task 6 · retrieve-the-right-paper · Medium
**Improve a Code Search System's Recall**

A code search tool uses basic TF-IDF over raw source files to find relevant functions for natural-language queries. It currently achieves 0.35 MRR (Mean Reciprocal Rank) on a provided test set of 15 queries. Improve the search quality to achieve MRR ≥ 0.60.

- **Starter code**: A `CodeSearcher` class with `index(repo_dir)` and `search(query, top_k)` methods using TF-IDF. A 20-file Python repository. 15 test queries with ground-truth function matches. An evaluation script that computes MRR.
- **Tests**: (1) MRR ≥ 0.60 on the 15 test queries. (2) The system indexes all Python files in the repo. (3) Search returns results in under 2 seconds. (4) The system handles queries that have no exact keyword match in the code (semantic understanding).
- **What the agent must do**: The agent is not told which technique to use. It must diagnose why TF-IDF is insufficient (misses semantic matches, doesn't understand code structure), research alternatives, and implement an improvement. Possible improvements include: function-level indexing instead of file-level, docstring/comment extraction, simple embedding-based search, AST-aware parsing, or hybrid approaches.
- **Why the paper matters**: Our corpus has 696 papers on code retrieval. Papers describe specific techniques — indexing at function granularity, extracting docstrings as natural-language summaries, using code structure (AST) for better representation. An agent with paper access should find these techniques and pick one that pushes MRR above the threshold. An agent without papers must invent improvements from scratch.
- **Laptop-verifiable**: Yes. Small repo, TF-IDF and keyword matching only. No embedding model required (though the agent may choose to add one — `all-MiniLM-L6-v2` at 22MB runs on CPU instantly).

---

### Task 7 · retrieve-the-right-paper · Hard
**Fix an Agent That Fails on Long Tasks**

A ReAct coding agent works well on short tasks (1-5 tool calls) but degrades catastrophically on tasks requiring 20+ steps. By step 15, it starts repeating previous actions, hallucinating file contents it read earlier, and losing track of its plan. The agent's context window is 8,000 tokens. Implement a memory management strategy that lets the agent complete a 50-step task without degradation.

- **Starter code**: A simulated ReAct loop that processes observations (tool outputs). Each observation is 200-500 tokens. A `MemoryManager` class with a stub `compress(observations, budget)` method that currently does naive truncation (keeps only the last N observations). A 50-step simulated task where the agent must track information from early steps to succeed at later steps.
- **Tests**: (1) Agent completes all 50 steps without exceeding the 8,000 token context limit. (2) At step 50, the agent can answer 5 factual questions about observations from steps 1-10 (information retention ≥ 4/5). (3) The agent does not repeat any action it has already taken (no action loops). (4) Total memory stays within budget at every step.
- **What the agent must do**: The agent must research memory management strategies for long-horizon agents and implement one. Options include: sliding window with summarization, importance-based eviction (keep observations that were referenced later), hierarchical summarization, or episodic memory with retrieval.
- **Why the paper matters**: Our corpus has 228 papers on agent context and memory management. Papers describe specific strategies: which observations to keep (tool errors are more important than successful reads), how to summarize (extract key facts, discard formatting), and when to compact (every K steps vs. when budget is exceeded). Without papers, the agent will implement naive truncation or simple sliding window, which will fail the information-retention test.

---

## Measurement

### The Ablation

Every task is run **twice** under identical conditions:
- **With arxiv-scholar**: The agent has the `arxiv_search` tool available and can query the 5,600-paper corpus.
- **Without arxiv-scholar**: The `arxiv_search` tool is disabled. The agent must rely on its pre-trained knowledge.

Same model, same temperature, same seeds, same timeout. The difference in results is the entire thesis.

### Metrics

| Metric | What it measures | How it's computed |
|---|---|---|
| **pass@1** | Did the agent solve the task? | All pytest tests pass = 1, else 0 |
| **test_score** | Partial credit | Fraction of tests passed (e.g., 4/6 = 0.67) |
| **turns_to_solve** | Efficiency | Number of agent loop iterations before `finish` |
| **tokens_used** | Cost proxy | Total input + output tokens across the trajectory |
| **arxiv_queries** | Search behavior | Number of times the agent called `arxiv_search` |
| **arxiv_relevance** | Search quality | Manual review: were the retrieved papers actually useful? |

### The Headline Numbers

```
                        With arxiv-scholar    Without    Δ
pass@1 (7 tasks)              X/7              Y/7    +Z
mean test_score              0.XX             0.YY   +0.ZZ
mean turns_to_solve            A                B     -C
```

The delta is the story. If it's positive, research-grounding helps. If it's zero on some tasks, that's an honest finding about where pre-training is sufficient.

### Failure Taxonomy

Every failing trajectory is tagged with a root cause:

| Failure Mode | Description |
|---|---|
| **retrieval_miss** | Agent searched but didn't find the right paper |
| **retrieval_skip** | Agent didn't search at all (relied on memory) |
| **wrong_technique** | Agent found papers but applied the wrong technique |
| **partial_implementation** | Right technique, incomplete implementation |
| **hallucination** | Agent fabricated details not in any paper |
| **timeout** | Ran out of steps before finishing |

This taxonomy tells us what to improve: if `retrieval_miss` dominates, our RAG needs better recall. If `retrieval_skip` dominates, our agent needs better tool-use prompting. If `hallucination` dominates even with RAG, the agent isn't reading the retrieved content carefully enough.

### Run Configuration

- **Model**: Same model for both arms (pinned version, e.g., `claude-3.5-sonnet-20241022`)
- **Runs per task**: 3 per condition (6 total per task) for variance estimation
- **Timeout**: 10 minutes per task (extended from SWE-bench default to account for `arxiv_search` latency)
- **Environment**: Each task runs in an isolated directory with its own git repo

---

## File Structure

```
eval/tasks/ml_research_bench/
├── manifest.json
├── README.md
├── task_01_rrf/
│   ├── task.json
│   ├── repo/
│   │   ├── search.py
│   │   ├── test_rrf.py
│   │   └── requirements.txt
│   └── gold_solution.patch
├── task_02_ast_chunking/
├── task_03_self_repair/
├── task_04_hybrid_search_debug/
├── task_05_paged_attention_debug/
├── task_06_code_search/
└── task_07_agent_memory/
```
