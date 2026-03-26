# Backend

This directory contains the cleaned backend migrated from the original workspace.

## Included

- `app/`: FastAPI application code
- `tests/`: backend test scripts
- `algorithm/GluPred/checkpoint/set2_30/`: required 30-minute prediction checkpoints
- `algorithm/GluPred/checkpoint/set2_60/`: required 60-minute prediction checkpoints
- `.env.example`: public environment template
- `requirements.txt`: Python dependency manifest

## Excluded

- `.git/`
- `.env`
- `__pycache__/`
- thesis notes, weekly notes, and other non-code markdown files
- CSV logs and temporary local files
- unused algorithm training data and historical experiment files

## Notes

- The backend depends on MySQL, MongoDB, WeChat app credentials, and an LLM API key.
- Install dependencies with `pip install -r requirements.txt` before local startup.
