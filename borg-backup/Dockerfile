ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Setup base
ENV LANG=C.UTF-8

RUN apk add --no-cache \
        borgbackup \
        openssh-keygen \
        openssh-client \
        jq \
        pigz \
        python3 \
        py3-pip \
	py3-psutil \
    && pip3 install --no-cache-dir \
        psutil \
        requests

# Home Assistant CLI
ARG BUILD_ARCH
ARG CLI_VERSION
RUN curl -Lso /usr/bin/ha \
        "https://github.com/home-assistant/cli/releases/download/${CLI_VERSION}/ha_${BUILD_ARCH}" \
    && chmod a+x /usr/bin/ha 

# Copy required data for add-on
COPY run.py backup.py restore.py common.py /
COPY rootfs /
RUN chmod a+x /run.py \
    && chmod a+x /etc/services.d/borg-backup/run \
    && chmod a+x /etc/services.d/borg-backup/finish

CMD []
