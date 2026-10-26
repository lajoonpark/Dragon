# Dragon — build the core, the dev loop, the tests and the web host.
#
#   make assets     regenerate the embedded art from assets/*.txt
#   make native     build the Linux dev loop (platform/null)
#   make test       run the test suite
#   make web        build the WASM host into dist/
#   make stills     render review stills into out/proto/
#   make all

CC      ?= gcc
EMCC    ?= emcc
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra
INCS     = -Icore/include -Icore/src
CORE     = $(wildcard core/src/*.c)

DIST     = dist
OUT      = out/proto

.PHONY: all assets native test web stills clean

all: native test web

assets:
	python3 tools/pipeline/export_assets.py
	python3 tools/pipeline/export_emitters.py
	python3 tools/embed_assets.py

# The Linux dev loop: no platform APIs, writes PPM, prints the ambience delta.
native: $(DIST)
	$(CC) $(CFLAGS) -o $(DIST)/render_seq $(INCS) $(CORE) platform/null/render_seq.c -lm

$(DIST):
	mkdir -p $(DIST)

test: $(DIST)
	$(CC) $(CFLAGS) -o $(DIST)/test_dragon $(INCS) $(CORE) tests/test_dragon.c -lm
	./$(DIST)/test_dragon

web: $(DIST)
	$(EMCC) -std=c99 -O2 $(INCS) $(CORE) platform/web/shim.c \
	  -s EXPORTED_FUNCTIONS='["_dragon_boot","_dragon_step","_dragon_frame_ptr","_dragon_set_view","_dragon_set_pan_paused","_dragon_free","_dragon_timer_begin","_dragon_timer_left","_dragon_timer_st","_dragon_timer_ph","_malloc","_free"]' \
	  -s EXPORTED_RUNTIME_METHODS='["HEAPU8"]' \
	  -s ALLOW_MEMORY_GROWTH=0 -s TOTAL_STACK=1048576 -s INITIAL_MEMORY=33554432 \
	  -s ENVIRONMENT=web -o $(DIST)/dragon.js
	cp platform/web/shell.html $(DIST)/index.html
	cp platform/web/wallpaper.html $(DIST)/wallpaper.html
	@echo "web host: $(DIST)/index.html (timer) and $(DIST)/wallpaper.html (background only)"

serve: web
	@echo "http://127.0.0.1:8171/"
	python3 -m http.server 8171 --directory $(DIST)

stills: native
	python3 tools/stills.py

clean:
	rm -rf $(DIST) $(OUT)
