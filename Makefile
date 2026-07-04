# Vault-LD roundtrip test flow (SPEC §5.6):
#
#   make export      "Vault-LD Example"  -> build/            (vault -> RDF)
#   make rehydrate   build/ + contexts   -> rehydratedVault/  (RDF -> vault)
#   make rebuild     rehydratedVault/    -> rehydratedVaultBuild/
#   make compare     build/ vs rehydratedVaultBuild/ -> graph diff
#
#   make roundtrip   runs all four in order
#   make test        security regression suite (scripts/test_security.py)
#   make clean       removes venv-independent outputs
#
# The roundtrip targets export with --source (the placement triples that make
# the .ttl a roundtrip face); plain `make query` produces the default lean,
# query-only output.

VENV  := venv
VAULT := Vault-LD Example

# venv layout and interpreter name differ per OS: Scripts/ under Windows
# (native make / Git Bash), bin/ everywhere else.
ifeq ($(OS),Windows_NT)
VENVBIN := $(VENV)/Scripts
SYSPY   := python
else
VENVBIN := $(VENV)/bin
SYSPY   := python3
endif
PY := $(VENVBIN)/python

BUILD      := build
REHYDRATED := rehydratedVault
REBUILD    := rehydratedVaultBuild

.PHONY: venv export query rehydrate rebuild compare roundtrip test clean

$(PY): scripts/requirements.txt
	$(SYSPY) -m venv $(VENV)
	$(VENVBIN)/pip install -r scripts/requirements.txt
	touch "$(PY)"

venv: $(PY)

export: venv
	$(PY) scripts/vault_to_rdf.py "$(VAULT)" --source --out-dir $(BUILD)

query: venv
	$(PY) scripts/vault_to_rdf.py "$(VAULT)" --out-dir $(BUILD)

rehydrate: venv
	rm -rf $(REHYDRATED)
	$(PY) scripts/rdf_to_vault.py $(REHYDRATED) $(BUILD)/schema.ttl $(BUILD)/data.ttl --context "$(VAULT)/context.jsonld"

rebuild: venv
	$(PY) scripts/vault_to_rdf.py $(REHYDRATED) --source --out-dir $(REBUILD)

compare: venv
	$(PY) scripts/compare_builds.py $(BUILD) $(REBUILD)

roundtrip: export rehydrate rebuild compare

# Every guarantee in SECURITY.md is pinned as a test: a PR that weakens a
# security patch fails here before it fails a human review.
test: venv
	$(PY) -m unittest discover -s scripts -p "test_*.py" -v

clean:
	rm -rf $(BUILD) $(REHYDRATED) $(REBUILD)
