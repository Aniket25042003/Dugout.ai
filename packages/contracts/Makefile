# Makefile for packages/contracts

.PHONY: all generate generate-go generate-python generate-ts clean

all: generate

generate: generate-go generate-python generate-ts

generate-go:
	@echo "==> Generating Go code from protobuf..."
	mkdir -p go
	# Ensure protoc-gen-go is installed in GOPATH
	export PATH="$(PATH):/Users/aniketpatel/go/bin" && \
	if ! which protoc-gen-go >/dev/null; then \
		echo "Installing protoc-gen-go..."; \
		go install google.golang.org/protobuf/cmd/protoc-gen-go@latest; \
	fi
	export PATH="$(PATH):/Users/aniketpatel/go/bin" && \
	protoc --go_out=go --go_opt=paths=source_relative -Iproto proto/dugout/v1/*.proto

generate-python:
	@echo "==> Generating Python code from protobuf..."
	mkdir -p python/dugout/v1
	touch python/__init__.py python/dugout/__init__.py python/dugout/v1/__init__.py
	protoc --python_out=python -Iproto proto/dugout/v1/*.proto

generate-ts:
	@echo "==> Generating TypeScript code from protobuf..."
	mkdir -p ts
	# Ensure npm packages are installed in workspace root
	npm install --prefix ../..
	npx protoc --plugin=protoc-gen-ts_proto=../../node_modules/.bin/protoc-gen-ts_proto --ts_proto_out=ts --ts_proto_opt=onlyTypes=true --ts_proto_opt=outputJsonMethods=true --ts_proto_opt=exportCommonSymbols=false -Iproto proto/dugout/v1/*.proto
	# Compile TS into dist/
	npm run build

clean:
	rm -rf go python ts dist node_modules
