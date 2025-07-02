.PHONY: test-step0 test-step1 verify-step1 test

# Run Step 0 tests
test-step0:
	pytest -q tests/step0/

# Run Step 1 verification tests
test-step1:
	pytest -q tests/step1/test_step1_verification.py

# Alias for test-step1
verify-step1: test-step1

# Run all tests
test:
	pytest tests/
