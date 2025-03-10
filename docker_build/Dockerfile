FROM python:3.10
WORKDIR /tmp

COPY requirements.txt /tmp/
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

COPY *.py /tmp/
COPY .secret/ /tmp/
COPY .secret/config.json /tmp/.secret/

ENTRYPOINT [ "python3", "/tmp/main.py" ]
