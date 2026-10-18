## What and why

<!-- What does this change and which problem does it solve? Link the issue if there is one. -->

## How it was tested

- [ ] `ruff check .` and `mypy` pass
- [ ] `pytest -q` passes, new behaviour has a test that failed before
- [ ] integration tests pass (`TEST_DB_DSN=... pytest -q tests/integration`) if SQL changed
- [ ] owner-facing texts added to both `core/messages/en.py` and `core/messages/ru.py`
- [ ] new migration instead of an edited one, if the schema changed

## Exactly-once publishing

<!-- If this touches handlers/listener.py or db/publications.py: how does it keep "claim before send" and "unknown outcome stays pending"? Otherwise write "not affected". -->
