start:
	docker-compose up --build -d

stop:
	docker-compose down --volumes

initdb:
	@docker-compose exec sage-ecr python3 -c 'from ecrdb import EcrDB; db = EcrDB(); db.initdb()'

# TODO(sean) eventually the unit tests can setup their own test database and will run initdb automatically as part of the test suite.
# for now, we just ensure it's run before running the test suite.
test: initdb
	@docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v; coverage report -m; coverage html'

# TODO(sean) unify this with make test so it's oblivious to whether it has a tty or not.
test-no-tty: initdb
	@docker-compose exec -T sage-ecr /bin/ash -c 'coverage run -m pytest -v; coverage report -m; coverage html'

dbshell:
	@docker-compose exec db mysql -u sage --password=test SageECR

registryshell:
	@docker-compose exec registry sh
