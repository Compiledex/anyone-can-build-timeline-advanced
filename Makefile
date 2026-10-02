# Timeline: short commands for this project. Type `make help` to see them.

.PHONY: help run test reset seed welcome pictures

help:
	@echo "make run    start the server (with-backend version), then open http://localhost:8010"
	@echo "make test   run the checks in with-backend/test_server.py"
	@echo "make reset  delete the database and the uploaded pictures, so the timeline starts empty"
	@echo "make seed   fill an empty timeline with made-up people and posts (make reset seed)"
	@echo "make welcome NAME=Alex   give your own account made-up notifications, messages and bookmarks"
	@echo "make pictures  add the drawings to the made-up posts of a timeline filled before"

run:
	cd with-backend && python3 server.py

test:
	cd with-backend && python3 -m unittest -v

reset:
	rm -rf with-backend/timeline.db with-backend/uploads

seed:
	cd with-backend && python3 seed.py

welcome:
	@test -n "$(NAME)" || (echo "Say whose account: make welcome NAME=YourName" && false)
	cd with-backend && python3 seed.py --welcome "$(NAME)"

pictures:
	cd with-backend && python3 seed.py --pictures
