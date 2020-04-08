clean:
	rm -rf dist vdf2json.egg-info vdf2json/*.pyc

dist: clean
	python setup.py sdist

upload: dist
	python setup.py register -r pypi
	twine upload -r pypi dist/*
