# check for dependencies
SHELL := /bin/bash
deps = curl jq git python3 
check_deps := $(foreach dep,$(deps), $(if $(shell which $(dep)),some string,$(error "No $(dep) in PATH!")))

# constants
packagename = mmif
generatedcode = $(packagename)/ver $(packagename)/res $(packagename)/vocabulary 
sdistname = $(packagename)-python
bdistname = $(packagename)_python
artifact = build/lib/$(packagename)
buildcaches = build/bdist* $(bdistname).egg-info __pycache__
testcaches = .hypothesis .pytest_cache .pytype coverage.xml htmlcov .coverage

.PHONY: all
.PHONY: clean
.PHONY: test
.PHONY: develop
.PHONY: publish
.PHONY: docs
.PHONY: doc
.PHONY: package
.PHONY: devversion

all: version test build

develop: devversion package test
	python3 setup.py develop --uninstall
	python3 setup.py develop

publish: distclean version package test 
	test `git branch --show-current` = "master"
	@git tag `cat VERSION` 
	@git push origin `cat VERSION`

$(generatedcode): dist/$(sdistname)*.tar.gz

docs: latest := $(shell git tag | sort -t. -k 1,1nr -k 2,2nr -k 3,3nr -k 4,4nr | head -n 1)
docs: VERSION $(generatedcode)
	rm -rf docs
	pip install --upgrade -r requirements.txt
	pip install --upgrade -r requirements.old
	sphinx-multiversion documentation docs -b html -a
	touch docs/.nojekyll
	ln -sf $(latest) docs/latest
	echo "<!DOCTYPE html> <html> <head> <title>Redirect to latest version</title> <meta charset=\"utf-8\"> <meta http-equiv=\"refresh\" content=\"0; url=./latest/index.html\"> </head> </html>" > docs/index.html

doc: VERSION $(generatedcode) # for single version sphinx - only use when developing
	rm -rf docs
	sphinx-build documentation docs -b html -a

package: VERSION dist/$(sdistname)*.tar.gz

dist/$(sdistname)*.tar.gz:
	pip install --upgrade -r requirements.dev
	python3 setup.py sdist

build: $(artifact)
$(artifact):
	python3 setup.py build

# invoking `test` without a VERSION file will generated a dev version - this ensures `make test` runs unmanned
test: devversion $(generatedcode)
	pip install --upgrade -r requirements.dev
	pip install -r requirements.txt
	pip install -r requirements.cv
	pytype $(packagename)
	python3 -m pytest --doctest-modules --cov=$(packagename) --cov-report=xml

# helper functions
e :=
space := $(e) $(e)
## handling version numbers
macro = $(word 1,$(subst .,$(space),$(1)))
micro = $(word 2,$(subst .,$(space),$(1)))
patch = $(word 3,$(subst .,$(space),$(1)))
increase_patch = $(call macro,$(1)).$(call micro,$(1)).$$(($(call patch,$(1))+1))
## handling versioning for dev version
add_dev = $(call macro,$(1)).$(call micro,$(1)).$(call patch,$(1)).dev1
split_dev = $(word 2,$(subst .dev,$(space),$(1)))
increase_dev = $(call macro,$(1)).$(call micro,$(1)).$(call patch,$(1)).dev$$(($(call split_dev,$(1))+1))

devversion: VERSION.dev VERSION; cat VERSION
version: VERSION; cat VERSION

# since the GH api will return tags in chronological order, we can just grab the last one without sorting
AUTH_ARG := $(if $(GITHUB_TOKEN),-H "Authorization: token $(GITHUB_TOKEN)")

VERSION.dev: devver := $(shell curl --silent $(AUTH_ARG) "https://api.github.com/repos/clamsproject/mmif-python/git/refs/tags" | grep '"ref":' | sed -E 's/.+refs\/tags\/([0-9.]+)",/\1/g' | tail -n 1)
VERSION.dev: specver := $(shell curl --silent $(AUTH_ARG) "https://api.github.com/repos/clamsproject/mmif/git/refs/tags" | grep '"ref":' | grep -v 'py-' | sed -E 's/.+refs\/tags\/(spec-)?([0-9.]+)",/\2/g' | tail -n 1)
VERSION.dev:
	@echo DEVVER: $(devver)
	@echo SPECVER: $(specver)
	@if [ $(call macro,$(devver)) = $(call macro,$(specver)) ] && [ $(call micro,$(devver)) = $(call micro,$(specver)) ] ; \
	then \
	if [[ $(devver) == *.dev* ]]; then echo $(call increase_dev,$(devver)) ; else echo $(call add_dev,$(call increase_patch, $(devver))); fi \
	else echo $(call add_dev,$(specver)) ; fi \
	> VERSION.dev

VERSION: version := $(shell git tag | sort -t. -k 1,1nr -k 2,2nr -k 3,3nr -k 4,4nr | head -n 1)
VERSION:
	@if [ -e VERSION.dev ] ; \
	then cp VERSION.dev VERSION; \
	else (read -p "Current version is ${version}, please enter a new version (default: increase *patch* level by 1): " new_ver; \
		[ -z $$new_ver ] && echo $(call increase_patch,$(version)) || echo $$new_ver) > VERSION; \
	fi

distclean:
	@rm -rf dist $(artifact) build/bdist*
clean: distclean
	@rm -rf VERSION VERSION.dev $(testcaches) $(buildcaches) $(generatedcode)
	@rm -rf docs
	@rm -rf .*cache
	@rm -rf .hypothesis tests/.hypothesis
	@git checkout -- documentation/target-versions.csv

