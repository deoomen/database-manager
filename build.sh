#!/bin/bash
set -eo pipefail

DOCKER_CONTEXT=${CI_PROJECT_DIR}
DOCKERFILE_DIR=${CI_PROJECT_DIR}
DOCKERFILE_PATH="Dockerfile"  # https://github.com/moby/buildkit/issues/684#issuecomment-429576268
DOCKER_CACHE_IMAGE="${CI_REGISTRY_IMAGE}/buildkitcache/${IMAGE_NAME}"

PUSH_IMAGES="*${IMAGE_VERSION},*latest"
PUSH_IMAGES=$(echo "${PUSH_IMAGES}" | sed -e "s@/@-@g" | sed -e "s@\*@${CI_REGISTRY_IMAGE}/${IMAGE_NAME}:@g")

export BUILDCTL_CONNECT_RETRIES_MAX=42  # workaround for timeout problem
mkdir -p ~/.docker
echo '{}' > ~/.docker/config.json

# GitLab CI login
cat ~/.docker/config.json | \
jq ".auths += {\"${CI_REGISTRY}\": { \
auth: \"$(echo -n "${CI_REGISTRY_USER}:${CI_REGISTRY_PASSWORD}" | base64)\" \
}}" | sponge ~/.docker/config.json

BUILDKIT_CACHE_ARGS="--export-cache type=registry,mode=max,ref=${DOCKER_CACHE_IMAGE} --import-cache type=registry,ref=${DOCKER_CACHE_IMAGE}"
BUILDKIT_ARGS="${BUILDKIT_ARGS} --opt filename=${DOCKERFILE_PATH}"
BUILDKIT_ARGS="${BUILDKIT_ARGS} --output type=image,\"name=${PUSH_IMAGES}\",push=true"

# Show what you've got
echo "Docker Context: ${DOCKER_CONTEXT}"
echo "Dockerfile directory: ${DOCKERFILE_DIR}"
echo "Dockerfile: ${DOCKERFILE_PATH}"
echo "Cache arguments: ${BUILDKIT_CACHE_ARGS}"
echo "Images to push: ${PUSH_IMAGES}"
echo "Authenticated registries:" $(jq ".auths | keys" ~/.docker/config.json)
echo "Buildkit arguments: ${BUILDKIT_ARGS}"

# Build!
buildctl-daemonless.sh build --progress=plain \
--frontend=dockerfile.v0 \
--local context="${DOCKER_CONTEXT}" \
--local dockerfile="${DOCKERFILE_DIR}" \
${BUILDKIT_CACHE_ARGS} \
${BUILDKIT_ARGS}
