sp: sp.c
	gcc -o sp sp.c

.PHONY: clean
clean:
	rm -f sp

# Copy the student files (everything except judge/, tests/ and .git) into a
# temp submission dir so the judge sees only the submission. The globs
# `.[!.]* ..?* *` match all dotfiles and regular names except `.` and `..`.
.PHONY: test
test: sp
	@platform=$$(judge/bin/detect-platform.sh) || exit $$?; \
	bindir="judge/bin/$$platform"; \
	if [ ! -x "$$bindir/judge" ]; then \
		echo "make test: no judge build published for platform $$platform" >&2; \
		exit 1; \
	fi; \
	work=$$(mktemp -d) || exit 1; \
	mkdir -p "$$work/submission" "$$work/scratch"; \
	for entry in .[!.]* ..?* *; do \
		[ -e "$$entry" ] || continue; \
		case "$$entry" in \
			judge | tests | .git) continue ;; \
		esac; \
		cp -R "$$entry" "$$work/submission/"; \
	done; \
	"$$bindir/judge" \
		--plan-root tests/public \
		--submission "$$work/submission" \
		--scratch-root "$$work/scratch" \
		--student-program sp \
		--consultant "$$bindir/consultant" \
		--format human --ui auto; \
	status=$$?; \
	rm -rf "$$work"; \
	exit $$status
