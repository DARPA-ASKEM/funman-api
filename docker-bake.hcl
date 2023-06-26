variable "DOCKER_REGISTRY" {
  default = "ghcr.io"
}
variable "DOCKER_ORG" {
  default = "darpa-askem"
}
variable "VERSION" {
  default = "local"
}
variable "IBEX_BRANCH" {
  default = "ibex-2.8.5_using_mathlib-2.1.1"
}
variable "DEBUG_IBEX" {
  default = "no"
}
variable "BAZEL_VERSION" {
  default = "6.0.0"
}
variable "DREAL_REPO_URL" {
  default = "https://github.com/danbryce/dreal4.git"
}
variable "DREAL_COMMIT_TAG" {
  default = "39b0822d90b277331c08ade4e68a51ec3b814fb4"
}
variable "AUTOMATES_COMMIT_TAG" {
  default = "e5fb635757aa57007615a75371f55dd4a24851e0"
}
variable "FUNMAN_DEV_UNAME" {
  default = "funman"
}
variable "FUNMAN_DEV_UID" {
  default = "1000"
}
variable "FUNMAN_DEV_GID" {
  default = "1000"
}

# ----------------------------------------------------------------------------------------------------------------------

function "tag" {
  params = [image_name, prefix, suffix]
  result = [ "${DOCKER_REGISTRY}/${DOCKER_ORG}/${image_name}:${check_prefix(prefix)}${VERSION}${check_suffix(suffix)}" ]
}

function "check_prefix" {
  params = [tag]
  result = notequal("",tag) ? "${tag}-": ""
}

function "check_suffix" {
  params = [tag]
  result = notequal("",tag) ? "-${tag}": ""
}

function "compose_registry" {
  params = [registry, org]
  result = notequal("localhost", registry) ? "${registry}/${org}/" : "${registry}/${org}/"
}

# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------

target "_platforms" {
  platforms = ["linux/amd64", "linux/arm64"]
}

target "funman-ibex" {
  context = "./docker/ibex"
  args = {
    IBEX_BRANCH = "${IBEX_BRANCH}"
    ENABLE_DEBUG = "${DEBUG_IBEX}"
  }
  dockerfile = "Dockerfile"
  tags = tag("funman-ibex", "", "${IBEX_BRANCH}")
}

target "funman-dreal4" {
  context = "./docker/dreal4"
  contexts = {
    baseapp = "target:funman-ibex"
  }
  args = {
    SIFT_REGISTRY_ROOT = compose_registry("${DOCKER_REGISTRY}","${DOCKER_ORG}")
    IBEX_TAG = "${VERSION}-${IBEX_BRANCH}"
    BAZEL_VERSION = "${BAZEL_VERSION}" 
    DREAL_REPO_URL = "${DREAL_REPO_URL}"
    DREAL_COMMIT_TAG = "${DREAL_COMMIT_TAG}"
  }
  dockerfile = "Dockerfile.dreal4"
  tags = tag("funman-dreal4", "", "${DREAL_COMMIT_TAG}")
}

target "funman-base" {
  context = "./docker/base"
  contexts = {
    baseapp = "target:funman-dreal4"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    DREAL_TAG = "${VERSION}-${DREAL_COMMIT_TAG}"
    AUTOMATES_COMMIT_TAG = "${AUTOMATES_COMMIT_TAG}"
  }
  dockerfile = "Dockerfile"
  tags = tag("funman-base", "", "${AUTOMATES_COMMIT_TAG}")
}

target "funman-pypi" {
  context = "./docker/pypi"
  contexts = {
    baseapp = "target:funman-base"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    FROM_TAG = "${VERSION}-${AUTOMATES_COMMIT_TAG}"
  }
  dockerfile = "Dockerfile"
  tags = tag("funman-pypi", "", "")
}

target "funman-git" {
  context = "."
  contexts = {
    baseapp = "target:funman-base"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    FROM_TAG = "${VERSION}-${AUTOMATES_COMMIT_TAG}"
  }
  dockerfile = "./docker/git/Dockerfile"
  tags = tag("funman-git", "", "")
}

target "funman-api" {
  context = "./docker/api"
  contexts = {
    baseapp = "target:funman-git"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    FROM_IMAGE = "funman-git"
    FROM_TAG = "${VERSION}"
  }
  dockerfile = "Dockerfile"
  tags = tag("funman-api", "", "")
}

target "funman-dev" {
  context = "."
  contexts = {
    baseapp = "target:funman-dreal4"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    DREAL_TAG = "${VERSION}-${DREAL_COMMIT_TAG}"
    UNAME = "${FUNMAN_DEV_UNAME}"
    UID = "${FUNMAN_DEV_UID}"
    GID = "${FUNMAN_DEV_GID}"
  }
  dockerfile = "./docker/dev/user/Dockerfile"
  tags = tag("funman-dev", "", "latest")
}

target "funman-dev-as-root" {
  context = "."
  contexts = {
    baseapp = "target:funman-dreal4"
  }
  args = {
    SIFT_REGISTRY_ROOT = "${DOCKER_REGISTRY}/${DOCKER_ORG}/"
    DREAL_TAG = "${VERSION}-${DREAL_COMMIT_TAG}"
  }
  dockerfile = "./docker/dev/root/Dockerfile.root"
  tags = tag("funman-dev", "", "latest")
}

target "funman-ibex-multiplatform" {
  inherits = ["_platforms", "funman-ibex"]
}
target "funman-dreal4-multiplatform" {
  inherits = ["_platforms", "funman-dreal4"]
}
target "funman-base-multiplatform" {
  inherits = ["_platforms", "funman-base"]
}
target "funman-git-multiplatform" {
  inherits = ["_platforms", "funman-git"]
}
target "funman-api-multiplatform" {
  inherits = ["_platforms", "funman-api"]
}
