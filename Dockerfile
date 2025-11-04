FROM ghcr.io/ad-sdl/wei

# TODO: update labels, if neccessary
LABEL org.opencontainers.image.source=https://github.com/AD-SDL/bmg_module
LABEL org.opencontainers.image.description="A template python module that demonstrates basic WEI module functionality."
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

RUN mkdir -p bmg_module

COPY ./src bmg_module/src
COPY ./README.md bmg_module/README.md
COPY ./pyproject.toml bmg_module/pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    pip install ./bmg_module

# TODO: Add any device-specific container configuration/setup here

CMD ["python", "bmg_module.py"]

#########################################
