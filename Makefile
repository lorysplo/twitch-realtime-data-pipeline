.PHONY: help install test lint dbt-build snapshot replay deploy-dashboards

REGION ?= ap-northeast-1
CH     ?= chat_forsen.jsonl

help:  ## show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n",$$1,$$2}'

install:  ## install python dependencies
	pip install -r requirements.txt

test:  ## run unit tests (pytest)
	pytest -q

lint:  ## lint python (non-blocking)
	-flake8 scripts glue_jobs tests --max-line-length=120

dbt-build:  ## build + test Silver + Gold in Redshift (dbt)
	cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir .

snapshot:  ## refresh the BI snapshot from the Gold tables
	python scripts/build_snapshot_redshift.py

replay:  ## replay chat to Kinesis  (override: make replay CH=chat_lirik.jsonl)
	python scripts/replay.py $(CH) --to-kinesis --stream twitch-chat-stream --region $(REGION) --loop

deploy-dashboards:  ## push the latest snapshot into the offline BI Lambda
	cd dashboards && zip -q /tmp/off.zip offline_dashboard_lambda.py ../results/dashboard_snapshot.json \
	  && aws lambda update-function-code --function-name twitch-offline-dashboard \
	     --zip-file fileb:///tmp/off.zip --region $(REGION)
