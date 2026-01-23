FROM ubuntu:20.04

RUN apt-get -y update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
  locales build-essential git wget rsync \
  python2 python2-dev python-tk python-pil python-pil.imagetk \
        tcl-dev tk-dev python-gi \
	pstoedit x11-utils x11-xserver-utils && \
  wget http://archive.ubuntu.com/ubuntu/pool/universe/p/pygtk/python-gtk2_2.24.0-5.1ubuntu2_amd64.deb && \
  apt-get install -y ./python-gtk2_2.24.0-5.1ubuntu2_amd64.deb && \
  rm -rf /var/cache/apt /var/lib/apt/lists ./python-gtk2_2.24.0-5.1ubuntu2_amd64.deb

# Generate locales
ARG LOCALES="en_US.UTF-8 en_GB.UTF-8 fi_FI.UTF-8"
# Actually used locales are controlled by etc/default/locale
RUN locale-gen $LOCALES && echo -e "LANG=en_US.UTF-8\nLC_NUMERIC=C\nLC_TIME=en_GB.UTF-8" > /etc/default/locale

WORKDIR /skdev
