# Makefile for TensorGuard Benchmarks

.PHONY: bench clean reports

bench:
	@echo "--- Running Microbenchmarks ---"
	python -m tensorguard.bench.cli micro
	@echo "--- Running Privacy Eval ---"
	python -m tensorguard.bench.cli privacy
	@echo "--- Running Robustness Tests ---"
	python -m tensorguard.bench.cli robustness
	@echo "--- Generating Evidence ---"
	python -m tensorguard.bench.cli evidence
	@echo "--- Generating Report ---"
	python -m tensorguard.bench.cli report

clean:
	rm -rf artifacts/metrics
	rm -rf artifacts/privacy
	rm -rf artifacts/robustness
	rm -rf artifacts/evidence_pack
	rm -f artifacts/report.html
