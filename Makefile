all: clean build

build:
	python -m build -w

clean:
	rm -rf build/ dist/ merak.egg-info/

install:
	pip install setuptools build
	pip install .
