FROM python:3.13
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /vogon

COPY startup.sh /vogon/startup.sh
RUN ["chmod", "+x", "/vogon/startup.sh"]

ENTRYPOINT ["/vogon/startup.sh"]