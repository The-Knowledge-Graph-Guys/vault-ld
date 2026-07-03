# Vault-LD roundtrip test flow (SPEC §5.6):
#
#   make export      "Vault-LD Example"  -> build/            (vault -> RDF)
#   make rehydrate   build/ + contexts   -> rehydratedVault/  (RDF -> vault)
#   make rebuild     rehydratedVault/    -> rehydratedVaultBuild/
#   make compare     build/ vs rehydratedVaultBuild/ -> graph diff
#
#   make roundtrip   runs all four in order
#   make clean       removes venv-independent outputs

VENV  := venv
PY    := $(VENV)/bin/python
VAULT := Vault-LD Example

BUILD      := build
REHYDRATED := rehydratedVault
REBUILD    := rehydratedVaultBuild

.PHONY: venv export rehydrate rebuild compare roundtrip clean

$(PY): scripts/requirements.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r scripts/requirements.txt
	touch $(PY)

venv: $(PY)

export: venv
	$(PY) scripts/vault_to_rdf.py "$(VAULT)" --out-dir $(BUILD)

rehydrate: venv
	rm -rf $(REHYDRATED)
	$(PY) scripts/rdf_to_vault.py $(REHYDRATED) $(BUILD)/schema.ttl $(BUILD)/data.ttl --context "$(VAULT)/context.jsonld"

rebuild: venv
	$(PY) scripts/vault_to_rdf.py $(REHYDRATED) --out-dir $(REBUILD)

compare: venv
	$(PY) scripts/compare_builds.py $(BUILD) $(REBUILD)

roundtrip: export rehydrate rebuild compare

clean:
	rm -rf $(BUILD) $(REHYDRATED) $(REBUILD)
