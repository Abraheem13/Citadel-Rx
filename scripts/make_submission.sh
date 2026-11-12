#!/usr/bin/env bash
# Standalone LaTeX package of the manuscript for submission or Overleaf: main.tex (figure path set to
# figures/), numbers.tex, tables/, the figures it includes and IEEEtran.cls; compiled once as a check.
#   bash scripts/make_submission.sh      # -> submission/Citadel-Rx_latex.zip, submission/Citadel-Rx_paper.pdf
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=submission; TMP=$(mktemp -d); D=$TMP/citadel_rx_latex
mkdir -p "$D/tables" "$D/figures" "$OUT"
cp paper/numbers.tex "$D/"; cp paper/tables/*.tex "$D/tables/"
sed 's#\\graphicspath{{../docs/figures/}}#\\graphicspath{{figures/}}#' paper/main.tex > "$D/main.tex"
for f in $(grep -oP '\\includegraphics(\[[^]]*\])?\{\K[^}]+' paper/main.tex); do cp "docs/figures/$f.pdf" "$D/figures/"; done
C=$(kpsewhich IEEEtran.cls || true); [ -n "$C" ] && cp "$C" "$D/"
printf 'Citadel-Rx, revised manuscript (IEEE TWC).\nCompile: pdflatex main && pdflatex main (or upload this folder to Overleaf).\nnumbers.tex (every result number) and tables/ are generated from the run records by `make paper`\nin https://github.com/abraheemrashid99-sys/Citradel-Rx; edit the text, not those files.\n' > "$D/README.txt"
(cd "$D" && pdflatex -interaction=nonstopmode main >/dev/null && pdflatex -interaction=nonstopmode main | grep "Output written")
cp "$D/main.pdf" "$OUT/Citadel-Rx_paper.pdf"; rm -f "$D"/main.{aux,log,out,pdf}
(cd "$TMP" && zip -qr citadel_rx_latex.zip citadel_rx_latex) && mv "$TMP/citadel_rx_latex.zip" "$OUT/Citadel-Rx_latex.zip"
rm -rf "$TMP"; ls -la "$OUT"
