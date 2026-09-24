import sys

content = open('makefile').read()
content = content.replace('all: $(OUT_DIR)/libpolydim.so $(OUT_DIR)/test_suite', 'all: $(OUT_DIR)/libpolydim.so')
open('makefile', 'w').write(content)
