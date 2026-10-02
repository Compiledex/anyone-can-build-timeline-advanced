# Timeline: short commands for this project. Type `make help` to see them.

.PHONY: help run test reset seed

help:
	@echo "make run    start the server (with-backend version), then open http://localhost:8010"
	@echo "make test   run the checks in with-backend/test_server.py"
	@echo "make reset  delete with-backend/timeline.db, so the timeline starts empty"
	@echo "make seed   fill an empty timeline with made-up people and posts (make reset seed)"

run:
	cd with-backend && python3 server.py

test:
	cd with-backend && python3 -m unittest -v

reset:
	rm -f with-backend/timeline.db

seed:
	cd with-backend && python3 seed.py
