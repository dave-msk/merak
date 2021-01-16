all: dev

build: clean
	python setup.py bdist_wheel

dev: clean
	python setup.py develop

clean:
	pip uninstall merak -y
	rm -rf build dist merak.egg-info
