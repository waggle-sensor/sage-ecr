start:
	docker-compose up --build -d

stop:
	docker-compose down --volumes

test:
	docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v && coverage report -m'

testx:
	docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v -x'

dbshell:
	docker-compose exec db mysql -u sage --password=test SageECR

registryshell:
	docker-compose exec registry sh
