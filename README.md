# sage-ecr
SAGE Edge Code Repository




# testing

```bash
docker-compose build

docker-compose up -d 

until curl -s http://localhost:5000/ ; do echo "no connection..." ; sleep 1 ; done

docker exec -ti sage-ecr_sage-ecr_1 pytest -v
```

or (works on laptop, not for Github Actions)
```bash
docker-compose build

docker-compose run --rm  sage-ecr  pytest -v
```


# debugging

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
