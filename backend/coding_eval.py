"""
coding_eval.py
Handles the coding round:
- Expanded problem bank (10 problems, 2 randomly selected per session)
- Runs user code safely via subprocess using sys.executable (fixes python3 not found)
- Evaluates submitted code using the Groq LLM
"""

import subprocess
import json
import tempfile
import os
import sys
import random
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Expanded problem bank (10 unique problems) ────────────────────────────────
CODING_PROBLEMS = [
    {
        "id": "two_sum",
        "title": "Two Sum",
        "description": (
            "Given an array of integers `nums` and an integer `target`, return "
            "indices of the two numbers that add up to target. Each input has exactly one solution.\n\n"
            "Example:\n  Input : nums = [2, 7, 11, 15], target = 9\n  Output: [0, 1]"
        ),
        "starter_code": (
            "def two_sum(nums, target):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(two_sum([2, 7, 11, 15], 9))   # [0, 1]\n"
            "print(two_sum([3, 2, 4], 6))         # [1, 2]\n"
            "print(two_sum([3, 3], 6))             # [0, 1]"
        ),
        "expected_idea": "Use a hashmap. For each number n, check if (target - n) is already in the map."
    },
    {
        "id": "reverse_string",
        "title": "Reverse a String",
        "description": (
            "Write a function that reverses a string in-place (return the reversed string).\n\n"
            "Example:\n  Input : 'hello'\n  Output: 'olleh'"
        ),
        "starter_code": (
            "def reverse_string(s):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(reverse_string('hello'))   # olleh\n"
            "print(reverse_string('world'))   # dlrow\n"
            "print(reverse_string('a'))       # a"
        ),
        "expected_idea": "Use slicing s[::-1] or swap with two pointers from both ends."
    },
    {
        "id": "valid_parentheses",
        "title": "Valid Parentheses",
        "description": (
            "Given a string of '(', ')', '{', '}', '[', ']' characters, "
            "determine if the string is valid (every opener is properly closed and nested).\n\n"
            "Example:\n  '()[]{}' → True\n  '([)]'  → False\n  '{[]}'  → True"
        ),
        "starter_code": (
            "def is_valid(s):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(is_valid('()[]{}'))   # True\n"
            "print(is_valid('([)]'))     # False\n"
            "print(is_valid('{[]}'))     # True\n"
            "print(is_valid('(]'))       # False"
        ),
        "expected_idea": "Use a stack. Push openers; when a closer appears, check that the stack top is its matching opener."
    },
    {
        "id": "palindrome",
        "title": "Palindrome Check",
        "description": (
            "Return True if the given string reads the same forwards and backwards, False otherwise.\n\n"
            "Example:\n  'racecar' → True\n  'hello'   → False"
        ),
        "starter_code": (
            "def is_palindrome(s):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(is_palindrome('racecar'))  # True\n"
            "print(is_palindrome('hello'))    # False\n"
            "print(is_palindrome('madam'))    # True"
        ),
        "expected_idea": "Compare s == s[::-1] or use two pointers walking inward from both ends."
    },
    {
        "id": "fizzbuzz",
        "title": "FizzBuzz",
        "description": (
            "Print numbers 1 to n. For multiples of 3 print 'Fizz', for multiples of 5 print 'Buzz', "
            "for multiples of both print 'FizzBuzz'.\n\n"
            "Example (n=15): 1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz"
        ),
        "starter_code": (
            "def fizzbuzz(n):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "fizzbuzz(15)\n"
            "fizzbuzz(5)"
        ),
        "expected_idea": "Loop 1..n. Check divisible by 15 first, then 3, then 5; otherwise print the number."
    },
    {
        "id": "max_subarray",
        "title": "Maximum Subarray Sum",
        "description": (
            "Given an integer array, find the contiguous subarray with the largest sum and return its sum.\n\n"
            "Example:\n  Input : [-2, 1, -3, 4, -1, 2, 1, -5, 4]\n  Output: 6  (subarray [4,-1,2,1])"
        ),
        "starter_code": (
            "def max_subarray(nums):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]))  # 6\n"
            "print(max_subarray([1]))                                 # 1\n"
            "print(max_subarray([-1, -2, -3]))                       # -1"
        ),
        "expected_idea": "Kadane's algorithm: track current_sum and max_sum, reset current_sum when it goes negative."
    },
    {
        "id": "count_vowels",
        "title": "Count Vowels",
        "description": (
            "Write a function that counts the number of vowels (a, e, i, o, u) in a given string (case-insensitive).\n\n"
            "Example:\n  Input : 'Hello World'\n  Output: 3"
        ),
        "starter_code": (
            "def count_vowels(s):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(count_vowels('Hello World'))   # 3\n"
            "print(count_vowels('aeiou'))         # 5\n"
            "print(count_vowels('xyz'))           # 0"
        ),
        "expected_idea": "Iterate over s.lower() and count characters that are in the set {'a','e','i','o','u'}."
    },
    {
        "id": "find_duplicates",
        "title": "Find Duplicates",
        "description": (
            "Given a list of integers, return a list of all elements that appear more than once. "
            "The result can be in any order.\n\n"
            "Example:\n  Input : [1, 2, 3, 2, 4, 3, 5]\n  Output: [2, 3]"
        ),
        "starter_code": (
            "def find_duplicates(nums):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(find_duplicates([1, 2, 3, 2, 4, 3, 5]))  # [2, 3]\n"
            "print(find_duplicates([1, 1, 1, 2]))            # [1]\n"
            "print(find_duplicates([1, 2, 3]))               # []"
        ),
        "expected_idea": "Use a Counter or a seen/duplicates set. Add to duplicates when a number is seen a second time."
    },
    {
        "id": "flatten_list",
        "title": "Flatten Nested List",
        "description": (
            "Given a list that may contain nested lists (one level deep), return a single flat list.\n\n"
            "Example:\n  Input : [[1, 2], [3, 4], [5]]\n  Output: [1, 2, 3, 4, 5]"
        ),
        "starter_code": (
            "def flatten(nested):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(flatten([[1, 2], [3, 4], [5]]))    # [1, 2, 3, 4, 5]\n"
            "print(flatten([[1], [2], [3]]))           # [1, 2, 3]\n"
            "print(flatten([[], [1, 2]]))              # [1, 2]"
        ),
        "expected_idea": "Use a list comprehension: [item for sublist in nested for item in sublist]."
    },
    {
        "id": "second_largest",
        "title": "Second Largest Number",
        "description": (
            "Return the second largest unique number in a list. "
            "Return None if there is no second largest.\n\n"
            "Example:\n  Input : [3, 1, 4, 1, 5, 9, 2, 6]\n  Output: 6"
        ),
        "starter_code": (
            "def second_largest(nums):\n"
            "    # Write your solution here\n"
            "    pass\n\n"
            "# Tests\n"
            "print(second_largest([3, 1, 4, 1, 5, 9, 2, 6]))  # 6\n"
            "print(second_largest([1, 1, 1]))                   # None\n"
            "print(second_largest([5, 3]))                      # 3"
        ),
        "expected_idea": "Convert to a sorted unique set, then pick the second-to-last element."
    },
]


# ── In-session problem cache (keyed by session_id so problems stay consistent
#    within one coding round but are re-randomised for a fresh session) ────────
_session_problems: dict = {}


def get_problems(count: int = 2, session_id: str = "") -> list:
    """
    Return 'count' randomly selected problems.
    Problems are locked to the session so refreshing the page keeps the same
    questions, but a new session always gets a fresh random pick.
    """
    if session_id and session_id in _session_problems:
        return _session_problems[session_id]

    selected = random.sample(CODING_PROBLEMS, min(count, len(CODING_PROBLEMS)))

    if session_id:
        _session_problems[session_id] = selected

    return selected


def run_code(code: str) -> dict:
    """
    Execute user-submitted Python code safely using subprocess.
    Uses sys.executable so it always calls the same Python that is running
    the Flask server (fixes 'python3 not found' errors on Windows/some Linux).
    Times out after 10 seconds to prevent infinite loops.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],   # sys.executable = current Python binary
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out (10 s limit). Check for infinite loops.",
            "success": False
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass  # Ignore cleanup errors


def evaluate_code(problem: dict, user_code: str) -> dict:
    """
    Use the Groq LLM to evaluate the user's code solution.
    Returns {"score": 0-100, "feedback": "..."}
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""You are a senior software engineer reviewing a coding solution.

Problem: {problem['title']}
Description: {problem['description']}
Expected Approach: {problem['expected_idea']}

User's Code:
```python
{user_code}
```

Evaluate on:
1. Correctness – does it solve the problem correctly?
2. Efficiency – is the time/space complexity reasonable?
3. Code quality – is it readable and clean?

Return ONLY a valid JSON object with no extra text:
{{
  "score": <integer 0-100>,
  "feedback": "<clear explanation covering correctness, efficiency, and style>"
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if the model wraps the JSON
    if "```" in raw:
        parts = raw.split("```")
        # Take the first code block content
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Last-resort: find the outermost { ... }
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)