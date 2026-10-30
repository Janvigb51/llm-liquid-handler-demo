| Metric | Result |
|---|---|
| Executable requests: calls pass validation | 15/16 (94%) |
| Executable requests: correct final deck state | 13/16 (81%) |
| Impossible/ambiguous requests handled safely | 10/10 (100%) |
| - of which blocked only by the validator | 0 |
| Executable requests: simulated without errors | 15/15 (100%) |

Failure/outcome breakdown:

- correct: 13
- declined: 10
- valid but wrong outcome: 2
- no tool calls: 1
