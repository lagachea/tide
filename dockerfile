FROM ghcr.io/astral-sh/uv:alpine

ENV MUSL_LOCALE_DEPS cmake make musl-dev gcc gettext-dev libintl
ENV MUSL_LOCPATH /usr/share/i18n/locales/musl

RUN apk add --no-cache \
    $MUSL_LOCALE_DEPS \
    && wget https://gitlab.com/rilian-la-te/musl-locales/-/archive/master/musl-locales-master.zip \
    && unzip musl-locales-master.zip \
      && cd musl-locales-master \
      && cmake -DLOCALE_PROFILE=OFF -D CMAKE_INSTALL_PREFIX:PATH=/usr . && make && make install \
      && cd .. && rm -r musl-locales-master

EXPOSE 5000

ENV LANG fr_FR.UTF-8

ENV LANGUAGE fr_FR.UTF-8

ENV LC_ALL fr_FR.UTF-8

ENV PATH="/app/.venv/bin:$PATH"

RUN apk add --no-cache python3~=3.12

WORKDIR /app

ADD requirements.txt .

RUN uv venv

RUN uv pip install -r requirements.txt

ADD . /app

CMD [ "flask", "--app", "maree", "run", "--host", "0.0.0.0" ]
