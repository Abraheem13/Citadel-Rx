# One-command entry points. Every target is resumable.
#   make laptop   environment + tests + laptop part of the revision campaign + push (MacBook)
#   make cloud    cloud part of the revision campaign (4-core Linux machine)
#   make report   statistics, figures and tables from all pushed records (docs/REV_*.md)
#   make paper    every number, table and figure from the records, then paper/main.pdf (journal
#                 version) and paper/extended/main_extended.pdf (extended version, every result and proof)
#   make test     unit tests
PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: laptop cloud report paper test dry

laptop:
	bash scripts/run_laptop.sh

cloud:
	$(PY) scripts/revision_fast.py --shard cloud --workers 4

report:
	$(PY) scripts/revision_report.py

paper:
	$(PY) scripts/revision_numbers.py
	$(PY) scripts/revision_figures.py
	$(PY) scripts/paper_figures.py
	$(PY) scripts/paired_disp.py results/rev_p4_paired --clean results/rev_clean_cloud $(wildcard results/rev_clean_pool*) --out docs/figures/fig_rev_p4_paired
	$(PY) scripts/fill_response.py
	cd paper && pdflatex -interaction=nonstopmode main.tex >/dev/null && pdflatex -interaction=nonstopmode main.tex | tail -2
	cd paper/extended && pdflatex -interaction=nonstopmode main_extended.tex >/dev/null && pdflatex -interaction=nonstopmode main_extended.tex | tail -2

test:
	$(PY) -m pytest tests -q

dry:
	$(PY) scripts/revision_fast.py --dry

submission: paper
	bash scripts/make_submission.sh
