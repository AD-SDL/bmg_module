FROM ghcr.io/ad-sdl/wei

# TODO: update labels, if neccessary
LABEL org.opencontainers.image.source=https://github.com/AD-SDL/python_template_module
LABEL org.opencontainers.image.description="A template python module that demonstrates basic WEI module functionality."
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

RUN mkdir -p python_template_module

COPY ./src python_template_module/src
COPY ./README.md python_template_module/README.md
COPY ./pyproject.toml python_template_module/pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    pip install ./python_template_module

# TODO: Add any device-specific container configuration/setup here

CMD ["python", "python_template_module.py"]

#########################################
