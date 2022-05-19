all: format poc

format: poc.c
	astyle --options="astyle-code-format.cfg" "poc.c*"

poc: poc.c
	gcc -O0 -o poc poc.c
