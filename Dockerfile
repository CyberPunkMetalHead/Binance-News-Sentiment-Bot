FROM python:3.9-alpine as building

RUN /usr/local/bin/python -m pip install --upgrade pip && \
    apk add --update --no-cache gcc g++ musl-dev libffi-dev openssl-dev python3-dev

COPY requirements.txt /requirements.txt

RUN apk add curl && curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable && source $HOME/.cargo/env

RUN source $HOME/.cargo/env && pip install -r /requirements.txt --no-cache-dir --prefer-binary

RUN python -m nltk.downloader vader_lexicon


FROM python:3.9-alpine as final

RUN apk add --update --no-cache g++

COPY --from=building /root/nltk_data /usr/local/share/nltk_data
COPY --from=building /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY * /

ENTRYPOINT ["python", "news-analysis.py"]
