start:
	docker-compose up --build -d

stop:
	docker-compose down --volumes

test:
	@docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v && coverage report -m'

testx:
	@docker-compose exec sage-ecr /bin/ash -c 'coverage run -m pytest -v -x'

dbshell:
	@docker-compose exec db mysql -u sage --password=test SageECR

registryshell:
	@docker-compose exec registry sh

# jenkins tokens consist of a two character version and 32 hex character value
# sample: 11eb0150869e432c1d6ebb21af93f65511
#         ^                   ^
#      two byte version + 32 character hex
jenkinstoken:
	@python3 -c 'from secrets import token_hex; version = 11; token = token_hex(16); print(f"{version}{token}")'
