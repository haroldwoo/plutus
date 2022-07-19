FROM python:3.7-slim
MAINTAINER Harold Woo <hwoo@mozilla.com>

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        apt-transport-https ca-certificates build-essential curl git libpq-dev python-dev \
        default-libmysqlclient-dev gettext sqlite3 libffi-dev libsasl2-dev \
        lsb-release gnupg emacs vim && \
    CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" && \
    echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update -y && apt-get install google-cloud-sdk -y && \
    apt-get remove -y lsb-release gnupg && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


COPY . /app

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Temporarily add GCP Service Account credentials for testing, but do not commit
# ENV GOOGLE_APPLICATION_CREDENTIALS=/app/donotcommitcreds-plutus.json

ENTRYPOINT ["python", "/app/plutus/budget_manager/main.py"]
