# The deployed BinderHub image, extended to run JupyterHub and the local builder in one container.
ARG BINDERHUB_IMAGE
FROM docker:29-cli AS docker-cli

FROM ${BINDERHUB_IMAGE}
# Use the host daemon through the socket; only its CLI belongs in this image.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
RUN docker --version && docker buildx version
RUN npm install -g configurable-http-proxy
# The local builder must forward per-request RDM credentials, as the Kubernetes builder does.
COPY local-build-optional-envs.patch /tmp/local-build-optional-envs.patch
RUN cd "$(python -c 'import binderhub, os; print(os.path.dirname(os.path.dirname(binderhub.__file__)))')" && patch -p1 < /tmp/local-build-optional-envs.patch && pip install dockerspawner
WORKDIR /opt/e2e
COPY jupyterhub_config.py binderhub_config.py rdm_spawner.py ./
ENTRYPOINT []
CMD ["jupyterhub", "--config=/opt/e2e/jupyterhub_config.py"]
