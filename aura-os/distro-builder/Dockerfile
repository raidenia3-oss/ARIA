FROM alpine:3.18

# Set locale
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# Install build deps + runtime
RUN apk add --no-cache \
    # Base
    alpine-base \
    linux-hardened \
    busybox \
    \
    # Hyprland & graphics
    hyprland \
    hyprpaper \
    hyprlock \
    xwayland \
    waybar \
    mako \
    alacritty \
    \
    # Go + Ruby + tools
    go \
    ruby \
    ruby-dev \
    \
    # Build tools
    build-base \
    gcc \
    g++ \
    make \
    git \
    curl \
    wget \
    \
    # Networking
    net-tools \
    bind-tools \
    ncat \
    openssh \
    openssh-client \
    openssh-server \
    openssl \
    \
    # Security & monitoring
    htop \
    tmux \
    vim \
    nano \
    less \
    file \
    strings \
    strace \
    \
    # Python (for AURA backend)
    python3 \
    python3-dev \
    py3-pip \
    \
    # Additional
    sudo \
    shadow \
    tzdata \
    bash

# Create aura user
RUN addgroup -g 1000 aura && \
    adduser -D -u 1000 -G aura -s /bin/bash aura && \
    echo "aura ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Create directories
RUN mkdir -p /home/aura/.config/hyprland && \
    mkdir -p /opt/aura/{go-tools,ruby-tools,backend} && \
    chown -R aura:aura /home/aura /opt/aura

# Build Go tools from source so a clean checkout can build the image.
COPY --chown=aura:aura aura-os/go-tools/ /tmp/go-tools/
RUN cd /tmp/go-tools && make build && \
    cp bin/* /opt/aura/go-tools/ && \
    chmod +x /opt/aura/go-tools/* && \
    ln -s /opt/aura/go-tools/* /usr/local/bin/

# Copy Ruby tools
COPY --chown=aura:aura aura-os/ruby-tools/ /opt/aura/ruby-tools/
RUN cd /opt/aura/ruby-tools && \
    bundle config set --local path vendor/bundle && \
    bundle install && \
    chmod +x bin/* && \
    ln -s bin/* /usr/local/bin/

# Copy AURA backend
COPY --chown=aura:aura backend/ /opt/aura/backend/
RUN cd /opt/aura/backend && \
    pip install -r requirements.txt && \
    find . -name '*.py' -print0 | xargs -0 -n1 python -m py_compile

# Hyprland config
COPY --chown=aura:aura aura-os/hyprland.conf /home/aura/.config/hyprland/hyprland.conf
COPY --chown=aura:aura aura-os/waybar.conf /home/aura/.config/waybar/config

# Entry point
COPY --chown=aura:aura aura-os/entrypoint.sh /opt/aura/entrypoint.sh
RUN chmod +x /opt/aura/entrypoint.sh

WORKDIR /home/aura
USER aura

ENTRYPOINT ["/opt/aura/entrypoint.sh"]
CMD ["/bin/bash"]
