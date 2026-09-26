# aura-os/go-tools/Makefile

.PHONY: build install clean help c2 c2-agent c2-server c2-client

BINDIR := bin
LDFLAGS := -ldflags="-s -w"

help:
	@echo "AURA Go Tools - Build Targets"
	@echo ""
	@echo "  make build        Build all tools (scanner, resolver, enum, c2)"
	@echo "  make scanner      Build port scanner"
	@echo "  make resolver     Build DNS resolver"
	@echo "  make enum         Build subdomain enumerator"
	@echo "  make c2           Build all C2 tools (agent, server, client)"
	@echo "  make c2-agent     Build C2 agent"
	@echo "  make c2-server    Build C2 server"
	@echo "  make c2-client    Build C2 client"
	@echo "  make install      Install tools to /usr/local/bin"
	@echo "  make clean        Remove build artifacts"
	@echo ""

build: scanner resolver enum c2
	@echo "[+] All tools built"

scanner:
	@echo "[*] Building aura-scanner..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-scanner cmd/aura-scanner/main.go
	@echo "[+] Built: $(BINDIR)/aura-scanner"

resolver:
	@echo "[*] Building aura-resolver..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-resolver cmd/aura-resolver/main.go
	@echo "[+] Built: $(BINDIR)/aura-resolver"

enum:
	@echo "[*] Building aura-enum..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-enum cmd/aura-enum/main.go
	@echo "[+] Built: $(BINDIR)/aura-enum"

c2-agent:
	@echo "[*] Building aura-c2-agent..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-c2-agent cmd/aura-c2-agent/main.go
	@echo "[+] Built: $(BINDIR)/aura-c2-agent"

c2-server:
	@echo "[*] Building aura-c2-server..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-c2-server cmd/aura-c2-server/main.go
	@echo "[+] Built: $(BINDIR)/aura-c2-server"

c2-client:
	@echo "[*] Building aura-c2-client..."
	mkdir -p $(BINDIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINDIR)/aura-c2-client cmd/aura-c2-client/main.go
	@echo "[+] Built: $(BINDIR)/aura-c2-client"

c2: c2-agent c2-server c2-client
	@echo "[+] C2 framework built"

install: build
	@echo "[*] Installing tools..."
	sudo cp $(BINDIR)/aura-scanner /usr/local/bin/
	sudo cp $(BINDIR)/aura-resolver /usr/local/bin/
	sudo cp $(BINDIR)/aura-enum /usr/local/bin/
	sudo cp $(BINDIR)/aura-c2-agent /usr/local/bin/
	sudo cp $(BINDIR)/aura-c2-server /usr/local/bin/
	sudo cp $(BINDIR)/aura-c2-client /usr/local/bin/
	sudo chmod +x /usr/local/bin/aura-*
	@echo "[+] Tools installed to /usr/local/bin"

clean:
	@echo "[*] Cleaning build artifacts..."
	rm -rf $(BINDIR)
	go clean
	@echo "[+] Clean complete"
