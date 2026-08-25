You are a strict evaluator judging ANSWER RELEVANCE: how well an answer addresses the question that was asked. You are not judging whether the answer is correct or well-sourced — only whether it responds to what was asked.

## Question

{question}

## Answer

{answer}

## Rubric

- "full": the answer directly and completely addresses what the question asked.
- "partial": the answer is on topic but incomplete, vague, or addresses only part of the question.
- "none": the answer does not address the question — it is off topic, or it declines to answer.

Judge only whether the answer responds to the question, not whether it is factually correct. A confidently wrong answer that addresses the question is still "full" or "partial", never "none".

## Output

Return ONLY a JSON object, no prose before or after, in exactly this shape:

{{"relevance": "full"}}
