.PHONY: build clean stop up

help:
	@echo "The list of commands for local development:\n"
	@echo "  build      Builds the docker images for the docker-compose setup"
	@echo "  clean      Stops and removes all docker containers"
	@echo "  up         Runs the mysql and statsd containers for testing"
	@echo "  stop       Stops the docker containers"

build:
	docker-compose build

clean:	stop
	docker-compose rm -f
	rm -rf logs/*

stop:
	docker-compose down
	docker-compose stop

up:
	docker-compose up db statsd

