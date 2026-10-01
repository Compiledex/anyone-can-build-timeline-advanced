# Timeline: short commands for this project. Type `make help` to see them.

.PHONY: help run test reset

help:
	@echo "make run    start the server (with-backend version), then open http://localhost:8009"
	@echo "make test   run the checks in with-backend/test_server.py"
	@echo "make reset  delete with-backend/timeline.db, so the timeline starts empty"

run:
	cd with-backend && python3 server.py

test:
	cd with-backend && python3 -m unittest -v

reset:
	rm -f with-backend/timeline.db
