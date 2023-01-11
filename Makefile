DOCS_REMOTE ?= origin
DEV_CONTAINER ?= funman-dev
DEV_NAME ?= funman-dev
DEPLOY_NAME ?= funman
LOCAL_REGISTRY_PORT?=5000

LOCAL_REGISTRY=localhost:$(LOCAL_REGISTRY_PORT)
SIFT_REGISTRY_ROOT=$(LOCAL_REGISTRY)/sift/

IBEX_NAME=funman-ibex
DREAL_NAME=funman-dreal4

FUNMAN_VERSION ?= 0.0.0
CMD_UPDATE_VERSION = sed -i -E 's/^__version__ = \"[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]*)?\"/__version__ = \"${FUNMAN_VERSION}\"/g'
SHELL_GET_TARGET_ARCH := $(shell test ! -z $(TARGET_ARCH) && echo $(TARGET_ARCH) || \
	arch \
	| sed s/x86_64/amd64/g \
	| sed s/aarch64/arm64/g \
)
TARGET_OS=linux

TARGET_TAG=$(TARGET_OS)-$(SHELL_GET_TARGET_ARCH)
IBEX_TAGGED_NAME=$(IBEX_NAME):$(TARGET_TAG)
DREAL_TAGGED_NAME=$(DREAL_NAME):$(TARGET_TAG)

MULTIPLATFORM_TAG=multiplatform

.PHONY: docs

venv:
	test -d .venv || python -m venv .venv
	source .venv/bin/activate && pip install -Ur requirements-dev.txt
	source .venv/bin/activate && pip install -Ur requirements-dev-extras.txt

docs:
	sphinx-apidoc -f -o ./docs/source ./src/funman -t ./docs/apidoc_templates --no-toc  
	mkdir -p ./docs/source/_static
	mkdir -p ./docs/source/_templates
	pyreverse \
		-k \
		-d ./docs/source/_static \
		./src/funman
	cd docs && make clean html

init-pages:
	@if [ -n "$$(git ls-remote --exit-code $(DOCS_REMOTE) gh-pages)" ]; then echo "GitHub Pages already initialized"; exit 1; fi;
	git switch --orphan gh-pages
	git commit --allow-empty -m "initial pages"
	git push -u $(DOCS_REMOTE) gh-pages
	git checkout main
	git branch -D gh-pages

deploy-pages:
	mv docs/build/html www
	touch www/.nojekyll
	rm www/.buildinfo || true
	git checkout --track $(DOCS_REMOTE)/gh-pages
	rm -r docs || true
	mv www docs
	git add -f docs
	git commit -m "update pages" || true
	git push $(DOCS_REMOTE)
	git checkout main
	git branch -D gh-pages

local-registry:
	docker start local_registry \
		|| docker run -d \
			--name local_registry \
			--network host \
			registry:2

use-docker-driver: local-registry
	docker buildx use funman-builder \
		|| docker buildx create \
			--name funman-builder \
			--use \
			--driver-opt network=host

build-ibex: use-docker-driver
	DOCKER_BUILDKIT=1 docker buildx build \
		--output "type=docker" \
		--platform $(TARGET_OS)/$(SHELL_GET_TARGET_ARCH) \
		--tag $(IBEX_TAGGED_NAME) \
		-f ./ibex/Dockerfile ./ibex
	docker tag $(IBEX_TAGGED_NAME) $(SIFT_REGISTRY_ROOT)$(IBEX_TAGGED_NAME)
	docker push $(SIFT_REGISTRY_ROOT)$(IBEX_TAGGED_NAME)

multiplatform-build-ibex: use-docker-driver
	DOCKER_BUILDKIT=1 docker buildx build \
		--network=host \
		--output "type=registry" \
		--platform linux/arm64,linux/amd64 \
		--tag $(SIFT_REGISTRY_ROOT)$(IBEX_NAME):$(MULTIPLATFORM_TAG) \
		-f ./ibex/Dockerfile ./ibex

build-dreal: use-docker-driver build-ibex
	DOCKER_BUILDKIT=1 docker buildx build \
		--output "type=docker" \
		--platform $(TARGET_OS)/$(SHELL_GET_TARGET_ARCH) \
		--build-arg SIFT_REGISTRY_ROOT=$(SIFT_REGISTRY_ROOT) \
		-t $(DREAL_TAGGED_NAME) \
		-f ./Dockerfile.dreal4 .
	docker tag $(DREAL_TAGGED_NAME) $(SIFT_REGISTRY_ROOT)$(DREAL_TAGGED_NAME)
	docker push $(SIFT_REGISTRY_ROOT)$(DREAL_TAGGED_NAME)

multiplatform-build-dreal: use-docker-driver multiplatform-build-ibex
	DOCKER_BUILDKIT=1 docker buildx build \
		--network=host \
		--output "type=registry" \
		--platform linux/arm64,linux/amd64 \
		--build-arg SIFT_REGISTRY_ROOT=$(SIFT_REGISTRY_ROOT) \
		--build-arg IBEX_TAG=$(MULTIPLATFORM_TAG) \
		--tag $(SIFT_REGISTRY_ROOT)$(DREAL_NAME):$(MULTIPLATFORM_TAG) \
		-f ./Dockerfile.dreal4 .

build-docker: use-docker-driver build-dreal
	DOCKER_BUILDKIT=1 docker build \
		--build-arg UNAME=$$USER \
		--build-arg UID=$$(id -u) \
		--build-arg GID=$$(id -g) \
		-t ${DEV_NAME} -f ./Dockerfile .

multiplatform: use-docker-driver multiplatform-build-dreal
	DOCKER_BUILDKIT=1 docker buildx build \
		--network=host \
		--output "type=registry" \
		--platform linux/arm64,linux/amd64 \
		--build-arg SIFT_REGISTRY_ROOT=$(SIFT_REGISTRY_ROOT) \
		--build-arg DREAL_TAG=$(MULTIPLATFORM_TAG) \
		--tag $(SIFT_REGISTRY_ROOT)$(DEV_NAME):$(MULTIPLATFORM_TAG) \
		-f ./Dockerfile .

build: build-docker

build-for-deployment: use-docker-driver build-dreal
	DOCKER_BUILDKIT=1 docker build \
		-t ${DEPLOY_NAME} -f ./Dockerfile.deploy .

run-deployment-image:
	docker run -it --rm -p 127.0.0.1:8888:8888 ${DEPLOY_NAME}:latest

run-docker:
	docker run \
		-d \
		-it \
		--cpus=8 \
		--name ${DEV_CONTAINER} \
    -p 127.0.0.1:8888:8888 \
		-v $$PWD:/home/$$USER/funman \
		${DEV_NAME}:latest

run-docker-se:
	docker run \
		-d \
		-it \
		--cpus=8 \
		--name ${DEV_CONTAINER} \
		-p 127.0.0.1:8888:8888 \
		-v $$PWD:/home/$$USER/funman:Z \
		--userns=keep-id \
		${DEV_NAME}:latest

launch-dev-container:
	@docker container inspect ${DEV_CONTAINER} > /dev/null 2>&1 \
		|| make run-docker
	@test $(shell docker container inspect -f '{{.State.Running}}' ${DEV_CONTAINER}) == 'true' > /dev/null 2>&1 \
		|| docker start ${DEV_CONTAINER}
	@docker attach ${DEV_CONTAINER}

rm-dev-container:
	@docker container rm ${DEV_CONTAINER}

install-pre-commit-hooks:
	@pre-commit install

format:
	pycln --config pyproject.toml .
	isort --settings-path pyproject.toml .
	black --config pyproject.toml .

update-versions:
	@test "${FUNMAN_VERSION}" != "0.0.0" || (echo "ERROR: FUNMAN_VERSION must be set" && exit 1)
	@${CMD_UPDATE_VERSION} auxiliary_packages/funman_demo/src/funman_demo/_version.py
	@${CMD_UPDATE_VERSION} auxiliary_packages/funman_dreal/src/funman_dreal/_version.py
	@${CMD_UPDATE_VERSION} src/funman/_version.py

dist: update-versions
	mkdir -p dist
	mkdir -p dist.bkp
	rsync -av --ignore-existing --remove-source-files dist/ dist.bkp/
	python -m build --outdir ./dist .
	python -m build --outdir ./dist auxiliary_packages/funman_demo
	python -m build --outdir ./dist auxiliary_packages/funman_dreal

check-test-release: dist
	@echo -e "\nReleasing the following packages to TestPyPI:"
	@ls -1 dist | sed -e 's/^/    /'
	@echo -n -e "\nAre you sure? [y/N] " && read ans && [ $${ans:-N} = y ]

test-release: check-test-release
	python3 -m twine upload --repository testpypi dist/*

check-release: dist
	@echo -e "\nReleasing the following packages to PyPI:"
	@ls -1 dist | sed -e 's/^/    /'
	@echo -n -e "\nAre you sure? [y/N] " && read ans && [ $${ans:-N} = y ]

release: check-release
	python3 -m twine upload dist/*
