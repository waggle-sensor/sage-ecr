# sage-ecr
SAGE Edge Code Repository




# testing

```bash
docker-compose build

docker-compose run --rm  sage-ecr  pytest -v
```


# debugging

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
