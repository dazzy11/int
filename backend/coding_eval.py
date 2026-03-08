"""
coding_eval.py
Handles the coding round:
- Provides coding problems
- Runs user code safely via Python subprocess
- Evaluates submitted code using the Groq LLM
"""

import subprocess
import json
import tempfile
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Coding problems available in the round
CODING_PROBLEMS = [
    {
        "id": "two_sum",
        "title": "Two Sum",
        "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to target.\n\nExample:\nInput: nums = [2, 7, 11, 15], target = 9\nOutput: [0, 1]",
        "starter_code": "def two_sum(nums, target):\n    # Write your solution here\n    pass\n\n# Test\nprint(two_sum([2, 7, 11, 15], 9))\nprint(two_sum([3, 2, 4], 6))",
        "expected_idea": "Use a hashmap to store visited numbers. For each number, check if (target - number) exists in the hashmap."
    },
    {
        "id": "reverse_string",
        "title": "Reverse a String",
        "description": "Write a function that reverses a string.\n\nExample:\nInput: 'hello'\nOutput: 'olleh'",
        "starter_code": "def reverse_string(s):\n    # Write your solution here\n    pass\n\n# Test\nprint(reverse_string('hello'))\nprint(reverse_string('world'))",
        "expected_idea": "Use slicing s[::-1] or iterate backwards through the string."
    },
    {
        "id": "valid_parentheses",
        "title": "Valid Parentheses",
        "description": "Given a string containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nExample:\nInput: '()[]{}'\nOutput: True\nInput: '([)]'\nOutput: False",
        "starter_code": "def is_valid(s):\n    # Write your solution here\n    pass\n\n# Test\nprint(is_valid('()[]{}}'))\nprint(is_valid('([)]'))\nprint(is_valid('{[]}'))",
        "expected_idea": "Use a stack. Push opening brackets. When a closing bracket appears, check if the stack top matches."
    },
    {
        "id": "palindrome",
        "title": "Palindrome Check",
        "description": "Write a function to check if a string is a palindrome (reads the same forwards and backwards).\n\nExample:\nInput: 'racecar'\nOutput: True\nInput: 'hello'\nOutput: False",
        "starter_code": "def is_palindrome(s):\n    # Write your solution here\n    pass\n\n# Test\nprint(is_palindrome('racecar'))\nprint(is_palindrome('hello'))\nprint(is_palindrome('madam'))",
        "expected_idea": "Compare the string with its reverse, or use two pointers from both ends."
    }
]


def get_problems(count: int = 2) -> list:
    """
    Return a subset of coding problems for the round.
    Returns 'count' problems (default 2).
    """
    import random
    return random.sample(CODING_PROBLEMS, min(count, len(CODING_PROBLEMS)))


def run_code(code: str) -> dict:
    """
    Execute user-submitted Python code safely using subprocess.
    Returns stdout output and any errors.
    Times out after 10 seconds to prevent infinite loops.
    """
    # Write code to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=10  # Kill after 10 seconds
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out (10s limit)",
            "success": False
        }
    finally:
        os.unlink(tmp_path)  # Clean up temp file


def evaluate_code(problem: dict, user_code: str) -> dict:
    """
    Use the Groq LLM to evaluate the user's code solution.
    Returns a score (0-100) and feedback string.
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

Evaluate this solution on:
1. Correctness - Does it solve the problem?
2. Efficiency - Is the time/space complexity reasonable?
3. Code quality - Is it readable and clean?

Return ONLY a valid JSON object in this exact format, no extra text:
{{
  "score": <integer 0-100>,
  "feedback": "<detailed explanation of what's good and what could be improved>"
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)
