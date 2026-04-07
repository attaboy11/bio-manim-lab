# Quiz

Produce a `Quiz` JSON object with 6–10 questions covering three kinds:

- `recall`: 4 questions on parts/definitions/inputs/outputs.
- `transfer`: 2 questions that ask the learner to apply the mechanism to a
  scenario the lesson did not directly cover.
- `misconception_correction`: 2 questions that present a plausible but wrong
  claim and ask the learner to correct it.

Each question must have:
- `kind`
- `question`
- `answer`
- `distractors` (optional, only for recall)
- `explanation` (optional, used to teach back the right model)
