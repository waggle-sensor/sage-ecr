start:
	docker-compose up --build -d

stop:
	docker-compose down --volumes

test:
	docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'

dbshell:
	docker-compose exec db mysql -u sage --password=test SageECR
