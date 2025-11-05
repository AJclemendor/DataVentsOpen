PKG=datavents
PY?=python

.PHONY: build clean check publish publish-test

build:
	$(PY) -m pip install --upgrade build >/dev/null
	$(PY) -m build

clean:
	rm -rf dist build *.egg-info

check:
	$(PY) -m pip install --upgrade twine >/dev/null
	$(PY) -m twine check dist/*

publish-test: build check
	$(PY) -m twine upload --repository testpypi dist/*

publish: build check
	$(PY) -m twine upload dist/*
