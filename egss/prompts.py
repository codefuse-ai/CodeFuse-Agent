judge_scalar_prompt = """# Role
Please act as an impartial judge to **verify** the patch provided by assistant to the user's task below.

# Instruction
- User will provide you with a response and the corresponding task, and your task is to verify its rationality with the rubric given below.
- Base your decision solely on how well the response addresses the user’s question and adheres to the assistant instructions.
- You can use the available tools to assess the provided rubric
- **Important**, If there are anything wrong with the provided response, **do not** try to fix it!

# Rubric
Your evaluation should focus on the following criteria:
<rubric>
**1. Requirement Relevance**
**Definition:** How completely and precisely the patch satisfies **all** functional and non-functional requirements expressed or implied in the user’s task.
| Score | Criteria |
|-------|----------|
| **0** | **Severely Off-Topic** – Patch addresses the wrong problem or introduces unrelated changes. |
| **1** | **Partial Coverage** – Core functionality implemented, but one or more explicit constraints (performance, boundary conditions, error handling, etc.) ignored. |
| **2** | **Highly Relevant** – All explicit requirements satisfied; implicit expectations (style, extensibility) may be incomplete. |
| **3** | **Perfect Alignment** – Every explicit and implicit requirement is met flawlessly. |

---

**2. Code Accuracy**
**Definition:** Apply available tools to run the code and check for any compilation errors.
| Score | Criteria |
|-------|----------|
| **0** | **Broken** – Compilation or runtime failure; severe logical errors prevent any correct behavior. |
| **1** | **Flawed** – Works in trivial cases only; contains non-critical bugs, unhandled boundary conditions, or latent defects. |
| **2** | **Correct** – No syntax errors; all requested core behaviors work; does not break existing functionality. |
| **3** | **Robust & Accurate** – Fully correct, gracefully handles edge cases and errors; no regressions. |

---

**3. Change Precision**
**Definition:** How accurately the patch targets **only** the code that must change, avoiding extraneous edits.
| Score | Criteria |
|-------|----------|
| **0** | **Mis-targeted** – Edits the wrong files/functions or completely misses required changes. |
| **1** | **Imprecise** – Correct general location but includes redundant edits or omits a few critical lines. |
| **2** | **Accurate** – Every necessary line is touched; no omissions. |
| **3** | **Minimal & Exact** – Same as 2, plus **zero** gratuitous changes (whitespace, formatting, unrelated code). |

---

**4. Dependency & Context Awareness**
**Definition:** Awareness of upstream/downstream dependencies and the completeness of associated updates (imports, call sites, configs, external contracts, backward compatibility).
| Score | Criteria |
|-------|----------|
| **0** | **Breaking Change** – Alters interfaces/data structures without updating all affected consumers, causing compile-time or runtime failures. |
| **1** | **Partial Awareness** – Core change correct, but misses obvious direct dependencies (e.g., one call site, missing import, config entry). |
| **2** | **Internally Consistent** – All **direct** internal dependencies updated; integrates cleanly within the repository. |
| **3** | **System-Wide Vision** – Same as 2, plus considers **indirect** or external impacts (performance, backward compatibility, deprecation warnings, migration guides). |

---

**5. Code Quality**
**Definition:** Adherence to project style guides, language idioms, readability, and maintainability.
| Score | Criteria |
|-------|----------|
| **0** | **Poor** – Gross violations of syntax or project conventions; unreadable or unmaintainable. |
| **1** | **Inconsistent Style** – Functional but visibly inconsistent with surrounding codebase. |
| **2** | **Clean & Conformant** – Follows language rules and project style; easy to read and maintain. |
| **3** | **Exemplary** – Idiomatic, elegant, self-documenting; serves as a reference implementation. |

---

**6. Functionality Validation (Gating Criterion)**
**Definition:** The patch must be accompanied by a self-contained, runnable test file and must not break existing tests.
**Mandatory agent workflow: **
    1. Generate / complete a test file named test_<original_file>_<issue>.py
    2. Execute the test file
    3. Run the full existing test suite; confirm zero regressions.
    4. only if pass all test, proceed to score dimensions 1–5; otherwise Total Score = 0.

| Score | Criteria |
|-------|----------|
| **0** | **Any Failure** – The patch fail to pass the unit test|
| **3** | **Comprehensive & Robust** – All tests pass. New tests are thorough, covering not only success paths but also failure modes, boundary conditions, and integration points. The test suite serves as a strong regression guard. |

Usage Notes
-----------
- Score each dimension 0–3.
- The full score is 18 points.
- Dimension 6 is a gating criterion:
    – If any test (new or existing) fails will result in Total Score = 0, stop.
    – Only if all tests pass (exit code 0) continue scoring dimensions 1–5.
- To assess dimension 6, you must generate a runnable test file and execute them!
- You may assess each dimension by writing and running test cases
    - Always apply given tools to verify the assistant response
    - Some response may include test case but it doesn't mean it is sufficient and runnable
    - Please ensure perform comprehensive and meticulous testing and debugging.
- **Important: **Your scoring criteria should be **stricter**. It's better to flag something incorrectly than to miss a real issue.
- Sum or weight the scores as appropriate for your evaluation workflow.
</rubric>

# Output format
**IMPORTANT**
Your final reply must be structured in the Json format consist of one args
- critique, required, str
- scalar, required, str, this is a fractional string where the numerator represents the score and the denominator is the total possible score from the rubric.

Here is an example of the output
```json
{
    "critique": "xxxx",
    "scalar": "a/b"
}
```

# User Task:
<task>
{task}
</task>

# Assistant response
**Important**: Do not try to fix the code issue in assistant response!!!
<patch>
{response}
</patch>

# Output
Now it's your turn.
"""

judge_cls_prompt = """
"""

judge_preference_prompt = """# ROLE:
Act as an expert code selector. Given a codebase, an github issue and N candidate patches proposed by your colleagues, your responsibility is to select the correct one to solve the issue.

# Instruction
- Understand the Issue and Codebase: Carefully read the issue description to comprehend the problem. You may need to examine the codebase for context, including: (1) Code referenced in the issue description; (2) The original code modified by each patch; (3) Unchanged parts of the same file; (4) Related files, functions, or modules that interact with the affected code.
- Analyze the Candidate Patches: For each patch, analyze its logic and intended fix. Consider whether the changes align with the issue description and coding conventions.
- verify its rationality with the rubric given below.
- The candidate patches have not yet applied to the repository, apply first before validate the patch

# Rubric
Your evaluation should focus on the following criteria:
<rubric>
**1. Requirement Relevance**
**Definition:** How completely and precisely the patch satisfies **all** functional and non-functional requirements expressed or implied in the user’s task.
| Score | Criteria |
|-------|----------|
| **0** | **Severely Off-Topic** – Patch addresses the wrong problem or introduces unrelated changes. |
| **1** | **Partial Coverage** – Core functionality implemented, but one or more explicit constraints (performance, boundary conditions, error handling, etc.) ignored. |
| **2** | **Highly Relevant** – All explicit requirements satisfied; implicit expectations (style, extensibility) may be incomplete. |
| **3** | **Perfect Alignment** – Every explicit and implicit requirement is met flawlessly. |

---

**2. Code Accuracy**
**Definition:** Apply available tools to run the code and check for any compilation errors.
| Score | Criteria |
|-------|----------|
| **0** | **Broken** – Compilation or runtime failure; severe logical errors prevent any correct behavior. |
| **1** | **Flawed** – Works in trivial cases only; contains non-critical bugs, unhandled boundary conditions, or latent defects. |
| **2** | **Correct** – No syntax errors; all requested core behaviors work; does not break existing functionality. |
| **3** | **Robust & Accurate** – Fully correct, gracefully handles edge cases and errors; no regressions. |

---

**3. Change Precision**
**Definition:** How accurately the patch targets **only** the code that must change, avoiding extraneous edits.
| Score | Criteria |
|-------|----------|
| **0** | **Mis-targeted** – Edits the wrong files/functions or completely misses required changes. |
| **1** | **Imprecise** – Correct general location but includes redundant edits or omits a few critical lines. |
| **2** | **Accurate** – Every necessary line is touched; no omissions. |
| **3** | **Minimal & Exact** – Same as 2, plus **zero** gratuitous changes (whitespace, formatting, unrelated code). |

---

**4. Dependency & Context Awareness**
**Definition:** Awareness of upstream/downstream dependencies and the completeness of associated updates (imports, call sites, configs, external contracts, backward compatibility).
| Score | Criteria |
|-------|----------|
| **0** | **Breaking Change** – Alters interfaces/data structures without updating all affected consumers, causing compile-time or runtime failures. |
| **1** | **Partial Awareness** – Core change correct, but misses obvious direct dependencies (e.g., one call site, missing import, config entry). |
| **2** | **Internally Consistent** – All **direct** internal dependencies updated; integrates cleanly within the repository. |
| **3** | **System-Wide Vision** – Same as 2, plus considers **indirect** or external impacts (performance, backward compatibility, deprecation warnings, migration guides). |

---

**5. Code Quality**
**Definition:** Adherence to project style guides, language idioms, readability, and maintainability.
| Score | Criteria |
|-------|----------|
| **0** | **Poor** – Gross violations of syntax or project conventions; unreadable or unmaintainable. |
| **1** | **Inconsistent Style** – Functional but visibly inconsistent with surrounding codebase. |
| **2** | **Clean & Conformant** – Follows language rules and project style; easy to read and maintain. |
| **3** | **Exemplary** – Idiomatic, elegant, self-documenting; serves as a reference implementation. |

---

**6. Functionality Validation (Gating Criterion)**
**Definition:** The patch must be accompanied by a self-contained, runnable test file and must not break existing tests.
**Mandatory agent workflow: **
    1. Generate / complete a test file named test_<original_file>_<issue>.py
    2. Execute the test file
    3. Run the full existing test suite; confirm zero regressions.
    4. only if pass all test, proceed to score dimensions 1–5; otherwise Total Score = 0.

| Score | Criteria |
|-------|----------|
| **0** | **Any Failure** – The patch fail to pass the unit test|
| **3** | **Comprehensive & Robust** – All tests pass. New tests are thorough, covering not only success paths but also failure modes, boundary conditions, and integration points. The test suite serves as a strong regression guard. |

Usage Notes
-----------
- Score each dimension 0–3.
- The full score is 18 points.
- Dimension 6 is a gating criterion:
    – If any test (new or existing) fails will result in Total Score = 0, stop.
    – Only if all tests pass (exit code 0) continue scoring dimensions 1–5.
- To assess dimension 6, you must generate a runnable test file and execute them!
- You may assess each dimension by writing and running test cases
    - Always apply given tools to verify the assistant response
    - Some response may include test case but it doesn't mean it is sufficient and runnable
    - Please ensure perform comprehensive and meticulous testing and debugging.
- **Important: **Your scoring criteria should be **stricter**. It's better to flag something incorrectly than to miss a real issue.
- Sum or weight the scores as appropriate for your evaluation workflow.
</rubric>


# FINAL REPORT:
If you have successfully selected the correct patch, submit your answer in the following format, [**IMPORTANT**: In Result section, output the patch id in json format between ```json and ```]:
### Status: succeed
### Result:
```json
{"result": "x" // id of the patch}
```
### Analysis: [Explain why Patch-x is correct.]

# Issues:
<task>
{task}
</task>

# Assistant Response
**Important**: Do not try to fix the code issue in assistant response!!!
{responses}

# Output
Now it's your turn.
"""

judge_trae_selector_prompt = """# ROLE:
Act as an expert code selector. Given a codebase, an github issue and N candidate patches proposed by your colleagues, your responsibility is to select the correct one to solve the issue. 

# WORK PROCESS:
You are given a software issue and multiple candidate patches. Your goal is to identify the patch that correctly resolves the issue. Follow these steps methodically:
1. Understand the Issue and Codebase: Carefully read the issue description to comprehend the problem. You may need to examine the codebase for context, including: 
(1) Code referenced in the issue description; 
(2) The original code modified by each patch; 
(3) Unchanged parts of the same file; 
(4) Related files, functions, or modules that interact with the affected code. 

2. Analyze the Candidate Patches: For each patch, analyze its logic and intended fix. Consider whether the
changes align with the issue description and coding conventions. 

3. Validate Functionality (Optional but Recommended): If needed, write and run unit tests to evaluate the
correctness and potential side effects of each patch. 

4. Select the Best Patch: Choose the patch that best resolves the issue with minimal risk of introducing new problems. 

# FINAL REPORT:
If you have successfully selected the correct patch, submit your answer in the following format:
### Status: succeed 

### Result: 
<!-- formatting into json format (put the dict between ```json and ```), example like: -->
```json
{"result": "x" // id of the patch}
```

### Analysis:
<!-- Explain why Patch-x is correct. -->

# Issues:
<task>
{task}
</task>

# Candidate Patches
{responses}

# Output
Now it's your turn.
"""


judge_extract_test_case_prompt = """# ROLE:
Act as an expert of programming tester, given a codebase、an issue and trajectories generated by different code agent, you need to generate **a single test file** that can be used to validate the patch generated.

# WORK PROCESS:
1. Understand the Issue and Codebase: Carefully read the issue description to comprehend the problem. You may need to examine the codebase for context, including: 
    (1) Code referenced in the issue description; 
    (2) The original code modified by each patch; 
    (3) Unchanged parts of the same file; 
    (4) Related files, functions, or modules that interact with the affected code.
    (5) regression tests in codebase that are closely related to the current issue.
2. Analyze the given trajectory: For each trajectory, analyze the test case and debug code the agent writing down, considering whether the test case written are sufficient for current issue.
3. From every dimension, including edge cases, regression test, assessing whether the current test coverage is sufficient; if it is not, add the missing test scenarios to the test file.
4. Consolidate all test cases across all dimensions and integrate them into the root-level test file named `test_current_issue.py`. The test contents should be derived from the following sources:
    (1) Provided reference trajectories
    (2) Newly designed test scenarios developed as part of this effort
    (3) Existing regression tests within the codebase.
5. Since the generated code has not been applied to the codebase, it is expected that running test_current_issue.py will contain failed cases. Your primary responsibility is to ensure that test_current_issue.py compiles without any errors.

# Requirement for the TEST FILE:
- You MUST write down the test content into a local file located in the root directory called `test_current_issue.py`
- the test file can be used to provide a **comprehensive** validation to current issue
- **IMPORTANT**: the test file can be executed with pytest, and will report the total test case resolved ratio
- **IMPORTANT && NECESSARY**: You must write the test content you have integrated into a **single** test file located in the root directory, named `test_current_issue.py`.

# Issue
<task>
{task}
</task>
{current_test_case}
# Trajectory
Trajectories sampled from different code agent with only edit related tools
{trajectories}
"""

test_content_prompt = """
# Current Test Case
We found that `test_current_issue.py` already exists in the project root and contains unit tests for the current issue. 
**IMPORTANT**: Check the file content first!
Therefore, the focus now is to examine what additional, distinct unit-test cases the provided trajectory can offer, and append those cases to `test_current_issue.py`.

"""


judge_tester_prompt = """# ROLE:
Act as an expert of programming tester, given a codebase、an issue、an output patch generated by a code agent, you need to validate the code with the given test file located in the root directory called `test_current_issue.py`.

# WORK PROCESS:
1. Understand the Issue and Codebase: Carefully read the issue description to comprehend the problem. You may need to examine the codebase for context, including: 
    (1) Code referenced in the issue description;
    (2) The original code modified by each patch; 
    (3) Unchanged parts of the same file; 
    (4) Related files, functions, or modules that interact with the affected code. 
2. Analyze the patch generated by the code agent, and the test file to see if the current test are sufficient for current issue
3. Execute the test file with `python test_current_issue.py`, and output the number of test cases solved in `test_current_issue.py`.
4. If there are compilation errors in the test files that are due to reasons other than the generated patch, you may fix the test files so they compile without errors. **NOTICE**: You can only fix the test file - `test_current_issue.py`

# Requirement:
- **IMPORTANT**: Do not attempt to fix the code so that it resolves the current issue, whatever number of test cases the existing code passes is the final count.
- **IMPORTANT**: You are only allowed to edit the test file - `test_current_issue.py`, do not edit any other file!
- **IMPORTANT**: You are only allowed to execute the test file - `test_current_issue.py`

# Issue
<task>
{task}
</task>

# Test File Content
```python:test_current_issue
{test_content}
```

# Candidate Patch
<patch>
{patch}
</patch>

# Output format
**IMPORTANT**
Your final reply must be structured in the Json format consist of three args:
- passed, int, the passed case,
- failed, int, the failed case,
- error, int, the error case,
- total, int, the total test case,

Here is an example of the output
```json
{"passed": x, "failed": x, "error": x, "total": x}
```

# Output
Now it's your turn.
"""


judge_preference_tester_prompt = """# ROLE:
Act as an expert of programming tester, given a codebase、an issue、several candidate code patch generated by a code agent, you need to validate the code patch with the given test file located in the root directory called `test_current_issue.py`, and select the best candidate patch

# WORK PROCESS:
1. Understand the Issue and Codebase: Carefully read the issue description to comprehend the problem. You may need to examine the codebase for context, including: 
    (1) Code referenced in the issue description;
    (2) The original code modified by each patch; 
    (3) Unchanged parts of the same file; 
    (4) Related files, functions, or modules that interact with the affected code. 
2. Analyze the patch generated by the code agent, and the test file to see if the current test are sufficient for current issue
3. Apply each candidate patch to the code repository in sequence, run the test file - `test_current_issue.py`, and observe the output.
4. If there are compilation errors in the test files that are due to reasons other than the generated patch, you may fix the test files so they compile without errors. **NOTICE**: You can only fix the test file - `test_current_issue.py`
5. Select the best candidate patch according to the output of the execution result of the test file.

# Requirement:
- **IMPORTANT**: Do not attempt to fix the code so that it resolves the current issue, whatever number of test cases the existing code passes is the final count.
- **IMPORTANT**: You are only allowed to edit the test file - `test_current_issue.py`, do not edit any other file!
- **IMPORTANT**: You are only allowed to execute the test file - `test_current_issue.py`

# Issue
<task>
{task}
</task>

# Test File Content
```python:test_current_issue.py
{test_content}
```

# Candidate Patch
{patches}

# FINAL REPORT:
If you have successfully selected the correct patch, submit your answer in the following format:
### Result: [**IMPORTANT**: output the patch id in json format between ```json and ```]
```json
{"result": "x" // id of the patch}
```
### Analysis: [Explain why Patch-x is correct.]

# Output
Now it's your turn.
"""