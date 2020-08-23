sdistname = mmif-python
bdistname = mmif_python
deps = curl jq git python3 pytype pytest
check_deps := $(foreach dep,$(deps), $(if $(shell which $(dep)),some string,$(error "No $(dep) in PATH!")))
comma := ,
empty := 
space := $(empty) $(empty)
macro = $(word 1,$(subst .,$(space),$(1)))
micro = $(word 2,$(subst .,$(space),$(1)))
patch = $(word 3,$(subst .,$(space),$(1)))
inc_patch = $(call macro,$(1)).$(call micro,$(1)).$$(($(call patch,$(1))+1))
splt_dev = $(word 2,$(subst .dev,$(space),$(1)))
inc_dev = $(call macro,$(1)).$(call micro,$(1)).$(call patch,$(1)).dev$$(($(call splt_dev,$(1))+1))
add_dev = $(call macro,$(1)).$(call micro,$(1)).$(call patch,$(1)).dev1
artifact = build/lib/mmif

.PHONY: all clean test develop publish sdist version devversion

all: VERSION test build

sdist: dist/$(sdistname)-*.tar.gz
dist/$(sdistname)-*.dev*.tar.gz: devversion dist/$(sdistname)-*.tar.gz
dist/$(sdistname)-*.tar.gz: VERSION; python3 setup.py sdist

develop: clean devversion test dist/$(sdistname)-*.dev*.tar.gz
	python3 setup.py develop --uninstall
	python3 setup.py develop
	twine upload --repository-url http://morbius.cs-i.brandeis.edu:8081/repository/pypi-develop/ \
		-u clamsuploader -p $$CLAMSUPLOADERPASSWORD dist/$(sdistname)-`cat VERSION`.tar.gz

publish: test sdist
	twine upload -u __token__ -p $$PYPITOKEN dist/$(sdistname)-`cat VERSION`.tar.gz

build: $(artifact)

$(artifact):
	python3 setup.py build

# invoking `test` without a VERSION file will generated a dev version - this ensures `make test` runs unmanned
test: devversion build
	pytype mmif/
	python3 -m pytest --doctest-modules --cov=mmif

devversion: VERSION.dev VERSION; cat VERSION
version: VERSION; cat VERSION

VERSION.dev: upstreamver := $(shell curl -s -X GET 'http://morbius.cs-i.brandeis.edu:8081/service/rest/v1/search?name=$(sdistname)' | jq '. | .items[].version' -r | sort | tail -n 1)
VERSION.dev:
	@if [[ $(upstreamver) == *.dev* ]]; then echo $(call inc_dev,$(upstreamver)) ; else echo $(call add_dev,$(call inc_patch, $(upstreamver))); fi > VERSION.dev

VERSION: version := $(shell git tag | grep py- | cut -d'-' -f 2 | sort -r | head -n 1)
VERSION:
	@if [ -e VERSION.dev ] ; \
	then cp VERSION.dev VERSION; \
	else (read -p "Current version is ${version}, please enter a new version (default: increase *patch* level by 1): " new_ver; \
		[ -z $$new_ver ] && echo $(call inc_patch,$(version)) || echo $$new_ver) > VERSION; \
	fi

clean: 
	@rm -rf VERSION VERSION.dev $(artifact) dist $(bdistname).egg-info mmif/res mmif/ver mmif/vocabulary