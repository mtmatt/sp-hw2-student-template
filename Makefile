sp: sp.c
	gcc -o sp sp.c

UV_DIR := $(CURDIR)/.uv-bin
UV := $(UV_DIR)/uv
VENV := $(CURDIR)/.venv
PYTHON := $(VENV)/bin/python

$(UV):
	mkdir -p $(UV_DIR)
	curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL=$(UV_DIR) sh

$(PYTHON): $(UV)
	$(UV) venv --clear --python 3.14 $(VENV)
	$(UV) pip install --python $(PYTHON) judge/python/judge_common

.PHONY: test
test: sp $(PYTHON)
	@platform=$$(judge/bin/detect-platform.sh) || exit $$?; \
	bindir="judge/bin/$$platform"; \
	if [ ! -x "$$bindir/judge" ]; then \
		echo "make test: no judge build published for platform $$platform" >&2; \
		exit 1; \
	fi; \
	work=$$(mktemp -d) || exit 1; \
	mkdir -p "$$work/submission" "$$work/scratch" "$$work/state"; \
	for entry in .[!.]* ..?* *; do \
		[ -e "$$entry" ] || continue; \
		case "$$entry" in \
			judge | tests | .venv | .uv-bin | .git) continue ;; \
		esac; \
		cp -R "$$entry" "$$work/submission/"; \
	done; \
	"$$bindir/judge" \
		--plan-root tests/public \
		--submission "$$work/submission" \
		--scratch-root "$$work/scratch" \
		--student-program sp \
		--access-token-generator "$$bindir/access-token-generator" \
		--atg-secret-key "$$work/state/atg-secret-key.hex" \
		--python $(PYTHON) \
		--logger-script judge/python/logger.py \
		--alarm-script judge/python/alarm.py \
		--server-keys-dir judge/keys \
		--encryptor "$$bindir/encryptor" \
		--format human --ui auto; \
	status=$$?; \
	rm -rf "$$work"; \
	exit $$status
